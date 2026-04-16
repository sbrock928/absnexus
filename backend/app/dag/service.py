"""DAG service — save with versioning, revert, deactivate."""

import json
import os
from datetime import datetime
from decimal import Decimal

import networkx as nx
from sqlalchemy.orm import Session

from app.core import settings
from app.dag.dao import DagDAO
from app.formulas.engine import FormulaEngine
from app.models.dag import DagVersion, DagNode, DagEdge
from app.models.deal import Deal
from app.schemas.dag import DagNodeCreate, DagEdgeCreate


class DagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = DagDAO(db)

    def save(
        self,
        deal_id: int,
        nodes: list[DagNodeCreate],
        edges: list[DagEdgeCreate],
        created_by: str,
        description: str | None = None,
    ) -> DagVersion:
        """Save creates a new version snapshot."""
        current = self.dao.get_current_version(deal_id)
        next_num = (current.version_number + 1) if current else 1
        version = self.dao.create_version(deal_id, next_num, created_by, description)

        # Create nodes
        key_to_id: dict[str, int] = {}
        for n in nodes:
            node = self.dao.add_node(
                version.id,
                deal_id,
                key=n.key,
                name=n.name,
                node_type=n.node_type,
                stream=n.stream,
                formula=n.formula,
                description=n.description,
                input_source=n.input_source,
                variable_id=n.variable_id,
                payment_type=n.payment_type,
                export_field=n.export_field,
                tolerance=n.tolerance,
                tolerance_type=n.tolerance_type,
                comparison_variable=n.comparison_variable,
                default_prior_value=n.default_prior_value,
                waterfall_order=n.waterfall_order,
                position_x=n.position_x,
                position_y=n.position_y,
            )
            key_to_id[n.key] = node.id

        # Create edges
        for e in edges:
            src_id = key_to_id.get(e.source_key)
            tgt_id = key_to_id.get(e.target_key)
            if src_id and tgt_id:
                self.dao.add_edge(version.id, src_id, tgt_id)

        # Internal regulatory policy: every version must have a physical file artifact.
        self._dump_version_file(deal_id, version, nodes, edges)

        return version

    def _dump_version_file(
        self,
        deal_id: int,
        version: DagVersion,
        nodes: list[DagNodeCreate],
        edges: list[DagEdgeCreate],
    ) -> str | None:
        """Write a JSON snapshot of the version to disk. Returns the file path."""
        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        base_dir = (
            deal.dag_archive_directory_override if deal else None
        ) or settings.dag_archive_directory
        dest_dir = os.path.join(base_dir, str(deal_id))
        try:
            os.makedirs(dest_dir, exist_ok=True)
            file_path = os.path.join(dest_dir, f"v{version.version_number}.json")
            payload = {
                "deal_id": deal_id,
                "version_number": version.version_number,
                "description": version.description,
                "created_by": version.created_by,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "nodes": [_node_to_dict(n) for n in nodes],
                "edges": [{"source_key": e.source_key, "target_key": e.target_key} for e in edges],
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=_json_default)
            return file_path
        except OSError:
            # Don't fail the save if the archive directory is unwritable; the DB version is the source of truth.
            return None

    def import_from_file(
        self,
        deal_id: int,
        payload: dict,
        created_by: str,
    ) -> DagVersion:
        """Create a new version from an exported JSON payload."""
        raw_nodes = payload.get("nodes") or []
        raw_edges = payload.get("edges") or []
        node_creates = [_dict_to_node_create(n) for n in raw_nodes]
        edge_creates = [
            DagEdgeCreate(source_key=e["source_key"], target_key=e["target_key"])
            for e in raw_edges
            if "source_key" in e and "target_key" in e
        ]
        src_version = payload.get("version_number")
        desc = f"Imported from v{src_version}.json" if src_version else "Imported from file"
        return self.save(deal_id, node_creates, edge_creates, created_by, desc)

    def load(self, deal_id: int, version_id: int | None = None):
        """Load DAG — current version or specific version."""
        if version_id:
            version = self.dao.get_version(version_id)
        else:
            version = self.dao.get_current_version(deal_id)
        if not version:
            return None
        nodes = self.dao.get_nodes(version.id)
        edges = self.dao.get_edges(version.id)
        return {"version": version, "nodes": nodes, "edges": edges}

    def revert(self, deal_id: int, version_id: int, created_by: str) -> DagVersion:
        """Revert by copying old version's nodes/edges into a new version."""
        old_version = self.dao.get_version(version_id)
        if not old_version or old_version.deal_id != deal_id:
            raise ValueError("Version not found")

        old_nodes = self.dao.get_nodes(version_id)
        old_edges = self.dao.get_edges(version_id)

        # Convert to create schemas
        node_creates = []
        for n in old_nodes:
            node_creates.append(
                DagNodeCreate(
                    key=n.key,
                    name=n.name,
                    node_type=n.node_type,
                    stream=n.stream,
                    formula=n.formula,
                    description=n.description,
                    input_source=n.input_source,
                    variable_id=n.variable_id,
                    payment_type=n.payment_type,
                    export_field=n.export_field,
                    tolerance=n.tolerance,
                    tolerance_type=n.tolerance_type,
                    comparison_variable=n.comparison_variable,
                    default_prior_value=n.default_prior_value,
                    waterfall_order=n.waterfall_order,
                    position_x=n.position_x,
                    position_y=n.position_y,
                )
            )

        # Build key mapping from old node IDs
        old_id_to_key = {n.id: n.key for n in old_nodes}
        edge_creates = []
        for e in old_edges:
            src_key = old_id_to_key.get(e.source_node_id)
            tgt_key = old_id_to_key.get(e.target_node_id)
            if src_key and tgt_key:
                edge_creates.append(DagEdgeCreate(source_key=src_key, target_key=tgt_key))

        return self.save(
            deal_id,
            node_creates,
            edge_creates,
            created_by,
            f"Reverted to v{old_version.version_number}",
        )

    # ── Single-node / edge CRUD on the current version ──

    def create_node(self, deal_id: int, fields: dict) -> DagNode:
        """Create a single node in the current DAG version.

        Auto-creates a v1 version if none exists. If a formula is supplied,
        incoming edges are inferred from the node-key references inside it.
        """
        version = self.dao.get_current_version(deal_id)
        if version is None:
            version = self.dao.create_version(deal_id, 1, fields.pop("created_by", "system"))

        # Normalize key aliases from the frontend (node_key → key, etc.)
        if "node_key" in fields and "key" not in fields:
            fields["key"] = fields.pop("node_key")
        if "comparison_var" in fields and "comparison_variable" not in fields:
            fields["comparison_variable"] = fields.pop("comparison_var")

        # Drop keys that aren't columns on the model.
        allowed = set(_NODE_FIELDS) | {"is_active"}
        cleaned = {k: v for k, v in fields.items() if k in allowed}

        node = self.dao.add_node(version.id, deal_id, **cleaned)
        if node.formula:
            self._sync_edges_from_formula(node)
        return node

    def update_node(self, node_id: int, fields: dict) -> DagNode | None:
        node = self.db.query(DagNode).filter(DagNode.id == node_id).first()
        if node is None:
            return None
        allowed = set(_NODE_FIELDS) | {"is_active"}
        formula_changed = False
        for k, v in fields.items():
            if k == "node_key":
                k = "key"
            if k == "comparison_var":
                k = "comparison_variable"
            if k not in allowed:
                continue
            if k == "formula":
                formula_changed = True
            setattr(node, k, v)
        self.db.flush()
        if formula_changed:
            self._sync_edges_from_formula(node)
        return node

    def delete_node(self, node_id: int) -> bool:
        node = self.db.query(DagNode).filter(DagNode.id == node_id).first()
        if node is None:
            return False
        # Remove edges that reference this node.
        self.db.query(DagEdge).filter(
            (DagEdge.source_node_id == node_id) | (DagEdge.target_node_id == node_id)
        ).delete(synchronize_session=False)
        self.db.delete(node)
        self.db.flush()
        return True

    def create_edge(
        self, deal_id: int, source_node_id: int, target_node_id: int
    ) -> DagEdge | None:
        version = self.dao.get_current_version(deal_id)
        if version is None:
            return None
        # De-dupe.
        existing = (
            self.db.query(DagEdge)
            .filter(
                DagEdge.dag_version_id == version.id,
                DagEdge.source_node_id == source_node_id,
                DagEdge.target_node_id == target_node_id,
            )
            .first()
        )
        if existing:
            return existing
        return self.dao.add_edge(version.id, source_node_id, target_node_id)

    def delete_edge(self, edge_id: int) -> bool:
        edge = self.db.query(DagEdge).filter(DagEdge.id == edge_id).first()
        if edge is None:
            return False
        self.db.delete(edge)
        self.db.flush()
        return True

    def _sync_edges_from_formula(self, node: DagNode) -> None:
        """Reconcile incoming edges so every node-key referenced in the formula
        has a source→target edge, and any stale ones are removed.

        Variables (non-node identifiers) are ignored — they're inputs, not DAG
        nodes. Only identifiers matching another node's key in the same version
        become edges.
        """
        if not node.formula:
            desired_sources: set[int] = set()
        else:
            refs = set(FormulaEngine().extract_variable_refs(node.formula))
            version_nodes = self.dao.get_nodes(node.dag_version_id)
            key_to_id = {n.key: n.id for n in version_nodes if n.id != node.id}
            desired_sources = {key_to_id[r] for r in refs if r in key_to_id}

        existing_edges = (
            self.db.query(DagEdge)
            .filter(
                DagEdge.dag_version_id == node.dag_version_id, DagEdge.target_node_id == node.id
            )
            .all()
        )
        existing_sources = {e.source_node_id: e for e in existing_edges}

        # Remove edges whose source is no longer referenced.
        for src_id, edge in existing_sources.items():
            if src_id not in desired_sources:
                self.db.delete(edge)

        # Add edges for newly-referenced sources.
        for src_id in desired_sources - set(existing_sources.keys()):
            self.dao.add_edge(node.dag_version_id, src_id, node.id)

        self.db.flush()

    def deactivate_node(self, node_id: int) -> None:
        node = self.db.query(DagNode).filter(DagNode.id == node_id).first()
        if node:
            node.is_active = False
            self.db.flush()

    def reactivate_node(self, node_id: int) -> None:
        node = self.db.query(DagNode).filter(DagNode.id == node_id).first()
        if node:
            node.is_active = True
            self.db.flush()

    def validate_dag(self, deal_id: int) -> list[str]:
        """Validate current DAG — check for cycles, unresolved refs, etc."""
        data = self.load(deal_id)
        if not data:
            return ["No DAG found for this deal"]

        errors: list[str] = []
        nodes = data["nodes"]
        edges = data["edges"]

        # Build networkx graph
        g = nx.DiGraph()
        id_to_node = {}
        for n in nodes:
            if not n.is_active:
                continue
            g.add_node(n.id)
            id_to_node[n.id] = n

        for e in edges:
            if e.source_node_id in id_to_node and e.target_node_id in id_to_node:
                g.add_edge(e.source_node_id, e.target_node_id)

        # Check cycles
        if not nx.is_directed_acyclic_graph(g):
            errors.append("DAG contains cycles")

        # Check stream isolation — allow distribution → validation (read-only dependency)
        for e in edges:
            src = id_to_node.get(e.source_node_id)
            tgt = id_to_node.get(e.target_node_id)
            if src and tgt and src.stream != tgt.stream:
                # Allow distribution → validation (validation reads distribution results)
                if src.stream == "distribution" and tgt.stream == "validation":
                    continue
                errors.append(
                    f"Cross-stream edge: {src.key} ({src.stream}) -> {tgt.key} ({tgt.stream})"
                )

        # Check nodes have required fields
        for n in nodes:
            if not n.is_active:
                continue
            if n.node_type == "input_value" and not n.input_source:
                errors.append(f"Input node '{n.key}' missing input_source")
            if n.node_type in ("calculation", "distribution", "validation") and not n.formula:
                errors.append(f"Node '{n.key}' missing formula")
            if n.node_type == "distribution" and not n.export_field:
                errors.append(f"Distribution node '{n.key}' missing export_field")
            if n.node_type == "validation" and not n.comparison_variable:
                errors.append(f"Validation node '{n.key}' missing comparison_variable")

        return errors


_NODE_FIELDS = [
    "key",
    "name",
    "node_type",
    "stream",
    "formula",
    "description",
    "input_source",
    "variable_id",
    "payment_type",
    "export_field",
    "tolerance",
    "tolerance_type",
    "comparison_variable",
    "default_prior_value",
    "waterfall_order",
    "position_x",
    "position_y",
]


def _node_to_dict(n: DagNodeCreate) -> dict:
    return {f: getattr(n, f) for f in _NODE_FIELDS}


def _dict_to_node_create(d: dict) -> DagNodeCreate:
    # Accept a subset — unknown keys are ignored, missing keys use schema defaults.
    kwargs = {f: d.get(f) for f in _NODE_FIELDS if d.get(f) is not None}
    return DagNodeCreate(**kwargs)


def _json_default(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
