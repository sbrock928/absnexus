"""DAG execution engine — builds context, topo-sort, evaluate, write trace."""
import json
from decimal import Decimal
import networkx as nx
from sqlalchemy.orm import Session

from app.models.dag import DagNode, DagEdge, DagVersion
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep
from app.formulas.engine import FormulaEngine
from app.services.prior_month_service import PriorMonthService
from app.tranches.service import TrancheService


class ExecutionResult:
    def __init__(self) -> None:
        self.steps: list[ExecutionStep] = []
        self.distribution_total: Decimal = Decimal("0")
        self.validations_passed: int = 0
        self.validations_total: int = 0
        self.errors: list[str] = []


class DagExecutor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.engine = FormulaEngine()

    def execute(self, run: ProcessingRun) -> ExecutionResult:
        """Full DAG execution with 5-source context assembly."""
        result = ExecutionResult()

        # 1. Load current DAG version
        version = (
            self.db.query(DagVersion)
            .filter(DagVersion.deal_id == run.deal_id, DagVersion.is_current == 1)
            .first()
        )
        if not version:
            result.errors.append("No DAG version found")
            return result

        run.dag_version_id = version.id

        nodes = (
            self.db.query(DagNode)
            .filter(DagNode.dag_version_id == version.id, DagNode.is_active == 1)
            .all()
        )
        edges = self.db.query(DagEdge).filter(DagEdge.dag_version_id == version.id).all()

        # Build networkx graph
        g = nx.DiGraph()
        node_map: dict[int, DagNode] = {}
        key_to_id: dict[str, int] = {}
        for n in nodes:
            g.add_node(n.id)
            node_map[n.id] = n
            key_to_id[n.key] = n.id

        for e in edges:
            if e.source_node_id in node_map and e.target_node_id in node_map:
                g.add_edge(e.source_node_id, e.target_node_id)

        if not nx.is_directed_acyclic_graph(g):
            result.errors.append("DAG contains cycles")
            return result

        # 2. Assemble context — Source 1: Prior month
        prior_svc = PriorMonthService(self.db)
        prior_run = prior_svc.find_prior_run(run.deal_id, run.report_period)
        context: dict[str, Decimal] = {}

        if prior_run:
            run.prior_run_id = prior_run.id
            context.update(prior_svc.build_prior_context(prior_run.id))
        else:
            context.update(prior_svc.get_default_priors(run.deal_id))

        # 3. Source 2: Tape values
        extracted = (
            self.db.query(ExtractedValue)
            .filter(ExtractedValue.run_id == run.id)
            .all()
        )
        for ev in extracted:
            if ev.parsed_value is not None:
                context[ev.variable_name] = ev.parsed_value

        # 4. Source 3: Tranche context
        tranche_ctx = TrancheService(self.db).build_tranche_context(
            run.deal_id, run.report_period,
            self._prior_period(run.report_period)
        )
        context.update(tranche_ctx)
        run.tranche_snapshot = json.dumps({k: str(v) for k, v in tranche_ctx.items()})

        # 5. Topo-sort and execute
        order = list(nx.topological_sort(g))
        step_num = 0

        for node_id in order:
            node = node_map[node_id]
            step_num += 1

            step = ExecutionStep(
                run_id=run.id,
                step_order=step_num,
                node_id=node.id,
                node_key=node.key,
                node_name=node.name,
                node_type=node.node_type,
                stream=node.stream,
                formula=node.formula,
                export_field=node.export_field,
                payment_type=node.payment_type,
            )

            if node.node_type == "input_value":
                # Input nodes just read from context
                step.result = context.get(node.key, Decimal("0"))

            elif node.node_type in ("calculation", "distribution"):
                if node.formula:
                    try:
                        val = self.engine.execute(node.formula, context)
                        step.result = val
                        step.resolved_formula = self.engine.resolve_formula(node.formula, context)
                    except Exception as e:
                        step.result = Decimal("0")
                        result.errors.append(f"Node '{node.key}': {e}")
                else:
                    step.result = Decimal("0")

                if node.node_type == "distribution":
                    result.distribution_total += step.result or Decimal("0")

            elif node.node_type == "validation":
                result.validations_total += 1
                if node.formula:
                    try:
                        calculated = self.engine.execute(node.formula, context)
                        step.result = calculated
                        step.resolved_formula = self.engine.resolve_formula(node.formula, context)
                    except Exception as e:
                        step.result = Decimal("0")
                        result.errors.append(f"Validation '{node.key}': {e}")

                    # Compare to tape value
                    comp_val = context.get(node.comparison_variable, Decimal("0")) if node.comparison_variable else Decimal("0")
                    step.comparison_value = comp_val
                    step.tolerance = node.tolerance or Decimal("0.01")
                    step.tolerance_type = node.tolerance_type or "absolute"

                    diff = abs(calculated - comp_val)
                    step.difference = diff

                    if step.tolerance_type == "percentage" and comp_val != 0:
                        pct_diff = diff / abs(comp_val) * 100
                        step.passed = 1 if pct_diff <= (step.tolerance or Decimal("0")) else 0
                    else:
                        step.passed = 1 if diff <= (step.tolerance or Decimal("0.01")) else 0

                    if step.passed:
                        result.validations_passed += 1

            # Add result to context for downstream nodes
            if step.result is not None:
                context[node.key] = step.result

            self.db.add(step)
            result.steps.append(step)

        self.db.flush()
        return result

    def get_lineage(self, run_id: int, node_key: str) -> list[ExecutionStep]:
        """Get ancestor execution steps for a node (for lineage drilldown)."""
        run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
        if not run or not run.dag_version_id:
            return []

        nodes = self.db.query(DagNode).filter(DagNode.dag_version_id == run.dag_version_id).all()
        edges = self.db.query(DagEdge).filter(DagEdge.dag_version_id == run.dag_version_id).all()

        g = nx.DiGraph()
        key_to_nid: dict[str, int] = {}
        for n in nodes:
            g.add_node(n.id)
            key_to_nid[n.key] = n.id
        for e in edges:
            g.add_edge(e.source_node_id, e.target_node_id)

        target_nid = key_to_nid.get(node_key)
        if target_nid is None:
            return []

        ancestors = nx.ancestors(g, target_nid) | {target_nid}
        subgraph = g.subgraph(ancestors)
        ancestor_order = list(nx.topological_sort(subgraph))

        # Fetch steps for these nodes
        steps = (
            self.db.query(ExecutionStep)
            .filter(ExecutionStep.run_id == run_id, ExecutionStep.node_id.in_(ancestor_order))
            .all()
        )
        step_map = {s.node_id: s for s in steps}
        return [step_map[nid] for nid in ancestor_order if nid in step_map]

    def _prior_period(self, period: str) -> str:
        if not period or len(period) < 7 or "-" not in period:
            return "1970-01"
        try:
            year, month = int(period[:4]), int(period[5:7])
        except ValueError:
            return "1970-01"
        if month == 1:
            return f"{year - 1}-12"
        return f"{year}-{month - 1:02d}"
