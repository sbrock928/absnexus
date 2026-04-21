"""DAG execution engine — builds context, topo-sort, evaluate, write trace."""

from decimal import Decimal
import networkx as nx
from sqlalchemy.orm import Session

from app.models.dag import DagNode, DagEdge, DagVersion
from app.models.deal import Deal
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep
from app.formulas.engine import FormulaEngine
from app.services.prior_month_service import PriorMonthService
from app.tranches.service import TrancheService
from app.utils.period_dates import compute_period_dates


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
        # Defaults load first as a base layer (bootstrapping first-run
        # rollforward checks). Then any actual prior-run execution results
        # override. This means a "stub" prior-run with no ExecutionSteps
        # (like the day-count anchor stubs seeded per deal) doesn't wipe out
        # the defaults.
        prior_svc = PriorMonthService(self.db)
        prior_run = prior_svc.find_prior_run(run.deal_id, run.report_period)
        context: dict[str, Decimal] = {}

        context.update(prior_svc.get_default_priors(run.deal_id))
        if prior_run:
            run.prior_run_id = prior_run.id
            context.update(prior_svc.build_prior_context(prior_run.id))

        # 3. Source 2: Tape values
        extracted = self.db.query(ExtractedValue).filter(ExtractedValue.run_id == run.id).all()
        for ev in extracted:
            if ev.parsed_value is not None:
                context[ev.variable_name] = ev.parsed_value

        # 4. Source 3: Tranche context
        tranche_ctx = TrancheService(self.db).build_tranche_context(
            run.deal_id, run.report_period, self._prior_period(run.report_period)
        )
        context.update(tranche_ctx)

        # 5. Source 4: Deal-level static + period-computed values
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        if deal is not None:
            prior_dist = prior_run.distribution_date if prior_run else None
            pd = compute_period_dates(deal, run.report_period, prior_dist)
            # Persist onto the run for reporting/export use
            run.distribution_date = pd.distribution_date
            run.determination_date = pd.determination_date
            run.days_in_period_actual = pd.days_in_period_actual
            run.days_in_period_30_360 = pd.days_in_period_30_360
            # Inject numeric values into the formula context (reserved names)
            if pd.days_in_period_actual is not None:
                context["period_days_in_period_actual"] = Decimal(pd.days_in_period_actual)
            if pd.days_in_period_30_360 is not None:
                context["period_days_in_period_30_360"] = Decimal(pd.days_in_period_30_360)
            if deal.cutoff_pool_balance is not None:
                context["deal_cutoff_pool_balance"] = Decimal(deal.cutoff_pool_balance)
            if deal.distribution_day_of_month is not None:
                context["deal_distribution_day_of_month"] = Decimal(deal.distribution_day_of_month)
            if deal.determination_business_days_before is not None:
                context["deal_determination_days_before"] = Decimal(
                    deal.determination_business_days_before
                )
            # Deal-level numeric constants — fees, OC, reserve
            for attr, key in (
                ("servicing_fee_pct", "deal_servicing_fee_pct"),
                ("backup_servicing_fee_pct", "deal_backup_servicing_fee_pct"),
                ("trustee_fee_monthly", "deal_trustee_fee_monthly"),
                ("target_oc_pct", "deal_target_oc_pct"),
                ("target_oc_floor_pct", "deal_target_oc_floor_pct"),
                ("target_oc_floor_amount", "deal_target_oc_floor_amount"),
                ("reserve_required_pct", "deal_reserve_required_pct"),
            ):
                val = getattr(deal, attr)
                if val is not None:
                    context[key] = Decimal(val)

        # 5. Topo-sort and execute — distribution stream first, then validation.
        #    (Distribution node → validation node comparisons are resolved via
        #    "comparison forwarding" below: we evaluate the validation's formula
        #    on the fly against the current context, which works because a
        #    validation's formula is typically just a reference to an already-
        #    computed calc node.)
        raw_order = list(nx.topological_sort(g))
        dist_order = [nid for nid in raw_order if node_map[nid].stream == "distribution"]
        val_order = [nid for nid in raw_order if node_map[nid].stream == "validation"]
        order = dist_order + val_order
        step_num = 0

        # Quick lookup: node key → node object, used by _resolve_comparison.
        node_by_key = {n.key: n for n in nodes}

        def _resolve_comparison(comp_key: str) -> Decimal | None:
            """Look up the comparison value for `comp_key` against the current context.

            First tries the plain context (works for tape variables, input nodes,
            and any node that has already executed). Falls back to evaluating a
            calculation or validation node's formula on the fly so distributions
            can compare against nodes that haven't run yet in topological order.
            """
            val = context.get(comp_key)
            if val is not None:
                return val
            ref_node = node_by_key.get(comp_key)
            if (
                ref_node is not None
                and ref_node.node_type in ("calculation", "validation")
                and ref_node.formula
            ):
                try:
                    return self.engine.execute(ref_node.formula, context)
                except Exception:
                    return None
            return None

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
                # Input nodes fall into three cases:
                #   1. formula set      → evaluate it (static literal like "2500",
                #                          or a small expression over deal constants
                #                          / other ambient context values)
                #   2. variable lookup  → read context[node.key] (tape variables are
                #                          ambient; no placeholder needed)
                #   3. "_in" fallback   → strip suffix for legacy placeholder nodes
                if node.formula:
                    try:
                        step.result = self.engine.execute(node.formula, context)
                        step.resolved_formula = self.engine.resolve_formula(
                            node.formula, context
                        )
                    except Exception as e:
                        step.result = Decimal("0")
                        result.errors.append(f"Input '{node.key}': {e}")
                else:
                    val = context.get(node.key)
                    if val is None and node.key.endswith("_in"):
                        val = context.get(node.key[:-3])
                    step.result = val if val is not None else Decimal("0")

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
                    # Compare against the configured target if set. This may be
                    # a tape variable, another node's key, or a validation node
                    # (resolved via comparison-forwarding on the validation's formula).
                    if node.comparison_variable:
                        comp_val = _resolve_comparison(node.comparison_variable)
                        if comp_val is not None:
                            step.comparison_value = comp_val
                            step.difference = abs((step.result or Decimal("0")) - comp_val)
                            step.tolerance = Decimal("0.01")
                            step.tolerance_type = "absolute"
                            step.passed = 1 if step.difference <= step.tolerance else 0

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

                    # Compare to tape value (or another node, via the same
                    # forwarding helper used for distributions).
                    resolved = (
                        _resolve_comparison(node.comparison_variable)
                        if node.comparison_variable
                        else None
                    )
                    comp_val = resolved if resolved is not None else Decimal("0")
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
        """Get ancestor execution steps for a node (for lineage drilldown).

        Walks **formula references** recursively (rather than DAG edges), so
        lineage still works after we dropped the placeholder `*_in` input
        nodes. Tape variables, deal constants, and period-computed values
        don't have a DagNode / ExecutionStep — the router's
        `_build_synthetic_lineage` handles them as leaves when the user
        drills into one directly.
        """
        run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
        if not run or not run.dag_version_id:
            return []

        nodes_by_key = {
            n.key: n
            for n in self.db.query(DagNode)
            .filter(DagNode.dag_version_id == run.dag_version_id)
            .all()
        }
        steps_by_key = {
            s.node_key: s
            for s in self.db.query(ExecutionStep)
            .filter(ExecutionStep.run_id == run_id)
            .all()
        }

        if node_key not in nodes_by_key and node_key not in steps_by_key:
            return []

        visited: set[str] = set()
        order: list[str] = []

        def walk(key: str) -> None:
            if key in visited:
                return
            visited.add(key)
            node = nodes_by_key.get(key)
            if node and node.formula:
                for ref in self.engine.extract_variable_refs(node.formula):
                    # Strip the `_prior` suffix introduced by PRIOR() desugaring
                    # so we recurse into the live-month node, not a ghost.
                    base = ref[:-6] if ref.endswith("_prior") else ref
                    if base in nodes_by_key or base in steps_by_key:
                        walk(base)
            order.append(key)

        walk(node_key)
        return [steps_by_key[k] for k in order if k in steps_by_key]

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
