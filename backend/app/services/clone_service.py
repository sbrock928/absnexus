"""Deal cloning service."""

from sqlalchemy.orm import Session
from app.models.deal import Deal
from app.models.variable_mapping import VariableMapping
from app.models.tranche import DealTranche
from app.models.dag import DagNode, DagEdge, DagVersion
from app.models.export import ExportFieldMapping
from app.models.variable import VariableDefinition


class CloneService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def clone_deal(
        self,
        source_id: int,
        new_name: str,
        created_by: str,
        clone_dag: bool = True,
        clone_mappings: bool = True,
        clone_exports: bool = True,
        clone_tranches: bool = True,
    ) -> Deal:
        source = self.db.query(Deal).filter(Deal.id == source_id).first()
        if not source:
            raise ValueError("Source deal not found")

        new_deal = Deal(
            name=new_name,
            servicer_id=source.servicer_id,
            product_type=source.product_type,
            status="draft",
            cloned_from_id=source.id,
            created_by=created_by,
        )
        self.db.add(new_deal)
        self.db.flush()

        # Clone deal-scoped variables
        deal_vars = (
            self.db.query(VariableDefinition)
            .filter(VariableDefinition.scope == "deal", VariableDefinition.deal_id == source.id)
            .all()
        )
        old_var_to_new: dict[int, int] = {}
        for v in deal_vars:
            nv = VariableDefinition(
                name=v.name,
                display_name=v.display_name,
                data_type=v.data_type,
                scope="deal",
                deal_id=new_deal.id,
                description=v.description,
            )
            self.db.add(nv)
            self.db.flush()
            old_var_to_new[v.id] = nv.id

        # Clone tranches
        if clone_tranches:
            for t in self.db.query(DealTranche).filter(DealTranche.deal_id == source.id).all():
                self.db.add(
                    DealTranche(
                        deal_id=new_deal.id,
                        class_label=t.class_label,
                        cusip=t.cusip,
                        regulation_type=t.regulation_type,
                        note_rate=t.note_rate,
                        original_balance=t.original_balance,
                        maturity_date=t.maturity_date,
                    )
                )

        # Clone mappings
        if clone_mappings:
            for m in (
                self.db.query(VariableMapping).filter(VariableMapping.deal_id == source.id).all()
            ):
                new_var_id = old_var_to_new.get(m.variable_id, m.variable_id)
                self.db.add(
                    VariableMapping(
                        deal_id=new_deal.id,
                        variable_id=new_var_id,
                        sheet_name=m.sheet_name,
                        column_letter=m.column_letter,
                        row_number=m.row_number,
                        tape_label=m.tape_label,
                    )
                )

        # Clone DAG
        if clone_dag:
            current_version = (
                self.db.query(DagVersion)
                .filter(DagVersion.deal_id == source.id, DagVersion.is_current == 1)
                .first()
            )
            if current_version:
                new_version = DagVersion(
                    deal_id=new_deal.id,
                    version_number=1,
                    created_by=created_by,
                    description=f"Cloned from {source.name}",
                )
                self.db.add(new_version)
                self.db.flush()

                old_nodes = (
                    self.db.query(DagNode)
                    .filter(DagNode.dag_version_id == current_version.id)
                    .all()
                )
                old_id_to_new: dict[int, int] = {}
                for n in old_nodes:
                    new_var_id: int | None = (
                        old_var_to_new.get(n.variable_id) if n.variable_id else n.variable_id
                    )
                    nn = DagNode(
                        deal_id=new_deal.id,
                        dag_version_id=new_version.id,
                        key=n.key,
                        name=n.name,
                        node_type=n.node_type,
                        stream=n.stream,
                        formula=n.formula,
                        description=n.description,
                        input_source=n.input_source,
                        variable_id=new_var_id,
                        payment_type=n.payment_type,
                        export_field=n.export_field,
                        tolerance=n.tolerance,
                        tolerance_type=n.tolerance_type,
                        comparison_variable=n.comparison_variable,
                        default_prior_value=n.default_prior_value,
                        position_x=n.position_x,
                        position_y=n.position_y,
                        is_active=n.is_active,
                    )
                    self.db.add(nn)
                    self.db.flush()
                    old_id_to_new[n.id] = nn.id

                old_edges = (
                    self.db.query(DagEdge)
                    .filter(DagEdge.dag_version_id == current_version.id)
                    .all()
                )
                for e in old_edges:
                    src = old_id_to_new.get(e.source_node_id)
                    tgt = old_id_to_new.get(e.target_node_id)
                    if src and tgt:
                        self.db.add(
                            DagEdge(
                                dag_version_id=new_version.id,
                                source_node_id=src,
                                target_node_id=tgt,
                            )
                        )

        # Clone export mappings
        if clone_exports:
            for em in (
                self.db.query(ExportFieldMapping)
                .filter(ExportFieldMapping.deal_id == source.id)
                .all()
            ):
                self.db.add(
                    ExportFieldMapping(
                        deal_id=new_deal.id,
                        template_id=em.template_id,
                        node_key=em.node_key,
                        field_code=em.field_code,
                        payment_type=em.payment_type,
                        tranche_class=em.tranche_class,
                        prorate_type=em.prorate_type,
                    )
                )

        self.db.flush()
        return new_deal
