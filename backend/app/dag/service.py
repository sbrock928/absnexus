"""DAG service — save with versioning, revert, deactivate."""
import networkx as nx
from sqlalchemy.orm import Session

from app.dag.dao import DagDAO
from app.models.dag import DagVersion, DagNode, DagEdge
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
                version.id, deal_id,
                key=n.key, name=n.name, node_type=n.node_type, stream=n.stream,
                formula=n.formula, description=n.description,
                input_source=n.input_source, variable_id=n.variable_id,
                payment_type=n.payment_type, export_field=n.export_field,
                tolerance=n.tolerance, tolerance_type=n.tolerance_type,
                comparison_variable=n.comparison_variable,
                default_prior_value=n.default_prior_value,
                waterfall_order=n.waterfall_order,
                position_x=n.position_x, position_y=n.position_y,
            )
            key_to_id[n.key] = node.id

        # Create edges
        for e in edges:
            src_id = key_to_id.get(e.source_key)
            tgt_id = key_to_id.get(e.target_key)
            if src_id and tgt_id:
                self.dao.add_edge(version.id, src_id, tgt_id)

        return version

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
            node_creates.append(DagNodeCreate(
                key=n.key, name=n.name, node_type=n.node_type, stream=n.stream,
                formula=n.formula, description=n.description,
                input_source=n.input_source, variable_id=n.variable_id,
                payment_type=n.payment_type, export_field=n.export_field,
                tolerance=n.tolerance, tolerance_type=n.tolerance_type,
                comparison_variable=n.comparison_variable,
                default_prior_value=n.default_prior_value,
                waterfall_order=n.waterfall_order,
                position_x=n.position_x, position_y=n.position_y,
            ))

        # Build key mapping from old node IDs
        old_id_to_key = {n.id: n.key for n in old_nodes}
        edge_creates = []
        for e in old_edges:
            src_key = old_id_to_key.get(e.source_node_id)
            tgt_key = old_id_to_key.get(e.target_node_id)
            if src_key and tgt_key:
                edge_creates.append(DagEdgeCreate(source_key=src_key, target_key=tgt_key))

        return self.save(deal_id, node_creates, edge_creates, created_by, f"Reverted to v{old_version.version_number}")

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
