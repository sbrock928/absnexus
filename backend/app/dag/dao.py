"""DAG data access."""
from sqlalchemy.orm import Session
from app.models.dag import DagNode, DagEdge, DagVersion


class DagDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_version(self, deal_id: int) -> DagVersion | None:
        return (
            self.db.query(DagVersion)
            .filter(DagVersion.deal_id == deal_id, DagVersion.is_current == 1)
            .first()
        )

    def get_version(self, version_id: int) -> DagVersion | None:
        return self.db.query(DagVersion).filter(DagVersion.id == version_id).first()

    def list_versions(self, deal_id: int) -> list[DagVersion]:
        return (
            self.db.query(DagVersion)
            .filter(DagVersion.deal_id == deal_id)
            .order_by(DagVersion.version_number.desc())
            .all()
        )

    def create_version(self, deal_id: int, version_number: int, created_by: str, description: str | None = None) -> DagVersion:
        # Mark old versions as not current
        self.db.query(DagVersion).filter(
            DagVersion.deal_id == deal_id, DagVersion.is_current == 1
        ).update({"is_current": 0})
        v = DagVersion(
            deal_id=deal_id,
            version_number=version_number,
            created_by=created_by,
            description=description,
        )
        self.db.add(v)
        self.db.flush()
        return v

    def get_nodes(self, version_id: int) -> list[DagNode]:
        return (
            self.db.query(DagNode)
            .filter(DagNode.dag_version_id == version_id)
            .order_by(DagNode.id)
            .all()
        )

    def get_edges(self, version_id: int) -> list[DagEdge]:
        return (
            self.db.query(DagEdge)
            .filter(DagEdge.dag_version_id == version_id)
            .all()
        )

    def add_node(self, version_id: int, deal_id: int, **kwargs) -> DagNode:
        node = DagNode(dag_version_id=version_id, deal_id=deal_id, **kwargs)
        self.db.add(node)
        self.db.flush()
        return node

    def add_edge(self, version_id: int, source_id: int, target_id: int) -> DagEdge:
        edge = DagEdge(dag_version_id=version_id, source_node_id=source_id, target_node_id=target_id)
        self.db.add(edge)
        self.db.flush()
        return edge
