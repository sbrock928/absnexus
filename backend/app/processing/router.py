"""Processing endpoints — full workflow orchestration."""

import os
import tempfile
import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role, require_processable_deal
from app.models.deal import Deal
from app.models.user import User
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep
from app.models.dag import DagNode
from app.services.tape_extractor import TapeExtractor
from app.services.dag_executor import DagExecutor
from app.services.clone_service import CloneService
from app.processing.service import ProcessingService
from app.utils.file_manager import FileManager

router = APIRouter()


# ── Processing Run CRUD ──


@router.get("/{deal_id}/runs")
def list_runs(deal_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ProcessingRun)
        .filter(ProcessingRun.deal_id == deal_id)
        .order_by(ProcessingRun.created_at.desc())
        .all()
    )


@router.get("/{deal_id}/runs/{run_id}")
def get_run(deal_id: int, run_id: int, db: Session = Depends(get_db)):
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")
    return run


# ── Step 1: Create run + upload tape ──

import re


class CreateRunRequest(BaseModel):
    report_period: str  # YYYY-MM

    @property
    def validated_period(self) -> str:
        if not re.match(r"^\d{4}-\d{2}$", self.report_period):
            raise ValueError(f"Invalid period format: '{self.report_period}'. Expected YYYY-MM.")
        return self.report_period


@router.post("/{deal_id}/runs", status_code=201)
def create_run(
    deal_id: int,
    body: CreateRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _deal: Deal = Depends(require_processable_deal),
):
    if not re.match(r"^\d{4}-\d{2}$", body.report_period):
        raise HTTPException(
            400, f"Invalid period format: '{body.report_period}'. Expected YYYY-MM (e.g. 2026-04)."
        )
    run = ProcessingRun(
        deal_id=deal_id,
        report_period=body.report_period,
        status="pending",
        created_by=user.username,
    )
    db.add(run)
    db.flush()
    return run


@router.post("/{deal_id}/runs/{run_id}/upload")
def upload_tape(
    deal_id: int,
    run_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _deal: Deal = Depends(require_processable_deal),
):
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    fm = FileManager()
    stored = fm.store_upload(deal_id, file.filename or "tape.xlsx", tmp_path)
    os.unlink(tmp_path)

    run.tape_file_path = stored
    run.tape_file_hash = hashlib.sha256(content).hexdigest()
    db.flush()
    return {"file_path": stored, "hash": run.tape_file_hash}


# ── Step 2: Extract variables ──


@router.get("/{deal_id}/runs/{run_id}/extracted")
def get_extracted(deal_id: int, run_id: int, db: Session = Depends(get_db)):
    """Read-only — return previously extracted values for a run."""
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")
    rows = (
        db.query(ExtractedValue)
        .filter(ExtractedValue.run_id == run_id)
        .order_by(ExtractedValue.id)
        .all()
    )
    return {
        "extracted": len(rows),
        "warnings": sum(1 for r in rows if r.warning),
        "values": [
            {
                "variable_id": r.variable_id,
                "variable": r.variable_name,
                "cell": r.cell_ref,
                "sheet": r.sheet_name,
                "raw": r.raw_value,
                "parsed": str(r.parsed_value) if r.parsed_value is not None else None,
                "prior": str(r.prior_value) if r.prior_value is not None else None,
                "pct_change": str(r.pct_change) if r.pct_change is not None else None,
                "warning": r.warning,
                "data_type": r.data_type,
            }
            for r in rows
        ],
    }


@router.post("/{deal_id}/runs/{run_id}/extract")
def extract_variables(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    _deal: Deal = Depends(require_processable_deal),
):
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")
    if not run.tape_file_path:
        raise HTTPException(400, "No tape uploaded")

    # Clean up previous extraction if re-extracting
    db.query(ExtractedValue).filter(ExtractedValue.run_id == run.id).delete()
    db.flush()

    run.status = "extracting"
    extractor = TapeExtractor(db)
    results = extractor.extract_all(run, run.tape_file_path)
    run.status = "extracted"
    db.flush()

    warnings = [r for r in results if r.warning]
    return {
        "extracted": len(results),
        "warnings": len(warnings),
        "values": [
            {
                "variable_id": r.variable_id,
                "variable": r.variable_name,
                "cell": r.cell_ref,
                "sheet": r.sheet_name,
                "raw": r.raw_value,
                "parsed": str(r.parsed_value) if r.parsed_value is not None else None,
                "prior": str(r.prior_value) if r.prior_value is not None else None,
                "pct_change": str(r.pct_change) if r.pct_change is not None else None,
                "warning": r.warning,
                "data_type": r.data_type,
            }
            for r in results
        ],
    }


# ── Step 3: Execute DAG ──


@router.post("/{deal_id}/runs/{run_id}/execute")
def execute_dag(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    _deal: Deal = Depends(require_processable_deal),
):
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")

    # Clean up previous execution if re-executing
    db.query(ExecutionStep).filter(ExecutionStep.run_id == run.id).delete()
    db.flush()

    run.status = "executing"
    executor = DagExecutor(db)
    result = executor.execute(run)

    if result.errors:
        run.status = "failed"
        run.error_message = "; ".join(result.errors[:5])
    else:
        run.status = "executed"

    run.total_distribution = result.distribution_total
    run.validations_passed = result.validations_passed
    run.validations_total = result.validations_total
    db.flush()

    comp_var_by_node = {
        n.id: n.comparison_variable
        for n in db.query(DagNode).filter(
            DagNode.id.in_([s.node_id for s in result.steps])
        ).all()
    }

    return {
        "status": run.status,
        "total_distribution": str(result.distribution_total),
        "validations_passed": result.validations_passed,
        "validations_total": result.validations_total,
        "errors": result.errors,
        "steps": [
            {
                "order": s.step_order,
                "key": s.node_key,
                "name": s.node_name,
                "type": s.node_type,
                "stream": s.stream,
                "formula": s.formula,
                "resolved": s.resolved_formula,
                "result": str(s.result) if s.result is not None else None,
                "export_field": s.export_field,
                "payment_type": s.payment_type,
                "comparison_value": (
                    str(s.comparison_value) if s.comparison_value is not None else None
                ),
                "comparison_variable": comp_var_by_node.get(s.node_id),
                "tolerance": str(s.tolerance) if s.tolerance is not None else None,
                "tolerance_type": s.tolerance_type,
                "passed": s.passed,
                "difference": str(s.difference) if s.difference is not None else None,
            }
            for s in result.steps
        ],
    }


# ── Step 4: Get execution trace + lineage ──


@router.get("/{deal_id}/runs/{run_id}/trace")
def get_trace(deal_id: int, run_id: int, db: Session = Depends(get_db)):
    steps = (
        db.query(ExecutionStep)
        .filter(ExecutionStep.run_id == run_id)
        .order_by(ExecutionStep.step_order)
        .all()
    )
    return [
        {
            "order": s.step_order,
            "key": s.node_key,
            "name": s.node_name,
            "type": s.node_type,
            "stream": s.stream,
            "formula": s.formula,
            "resolved": s.resolved_formula,
            "result": str(s.result) if s.result is not None else None,
            "export_field": s.export_field,
            "payment_type": s.payment_type,
            "comparison_value": (
                str(s.comparison_value) if s.comparison_value is not None else None
            ),
            "tolerance": str(s.tolerance) if s.tolerance is not None else None,
            "tolerance_type": s.tolerance_type,
            "difference": str(s.difference) if s.difference is not None else None,
            "passed": s.passed,
        }
        for s in steps
    ]


@router.get("/{deal_id}/runs/{run_id}/lineage/{node_key}")
def get_lineage(deal_id: int, run_id: int, node_key: str, db: Session = Depends(get_db)):
    executor = DagExecutor(db)
    steps = executor.get_lineage(run_id, node_key)
    if not steps:
        # Not a real DagNode — may be an injected context variable
        # (period-date computed values, deal constants, or extracted tape vars).
        synthetic = _build_synthetic_lineage(db, deal_id, run_id, node_key)
        if synthetic is not None:
            return synthetic
        raise HTTPException(404, "Node not found in lineage")

    # Build richer response for the lineage drilldown UI
    target_step = steps[-1]  # Last in topo order is the target
    step_keys = {s.node_key for s in steps}
    nodes = []
    for s in steps:
        # Upstream = every formula ref that resolved to another step in the
        # ancestry, stripping the `_prior` suffix that PRIOR() desugars to so
        # the frontend graph draws edges to the live-month node.
        upstream = []
        if s.formula:
            for ref in executor.engine.extract_variable_refs(s.formula):
                base = ref[:-6] if ref.endswith("_prior") else ref
                if base in step_keys and base != s.node_key:
                    upstream.append(base)

        nodes.append(
            {
                "node_key": s.node_key,
                "node_name": s.node_name,
                "node_type": s.node_type,
                "stream": s.stream,
                "execution_order": s.step_order,
                "formula": s.formula,
                "formula_resolved": s.resolved_formula,
                "result": str(s.result) if s.result is not None else None,
                "prior_value": None,
                "delta_pct": None,
                "is_suspect": False,
                "suspect_reason": None,
                "upstream_keys": upstream,
                "comparison_value": str(s.comparison_value) if s.comparison_value is not None else None,
                "difference": str(s.difference) if s.difference is not None else None,
                "tolerance": str(s.tolerance) if s.tolerance is not None else None,
                "validation_passed": True if s.passed == 1 else (False if s.passed == 0 else None),
                "input_source": None,
                "cell_ref": s.node_key,
            }
        )

    return {
        "target_node_key": target_step.node_key,
        "target_node_name": target_step.node_name,
        "target_node_type": target_step.node_type,
        "target_result": str(target_step.result) if target_step.result is not None else None,
        "lineage_count": len(nodes),
        "nodes": nodes,
    }


# ── Step 5: Waterfall reconciliation ──


@router.get("/{deal_id}/runs/{run_id}/waterfall")
def get_waterfall(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the waterfall balance trace for a completed run."""
    try:
        return ProcessingService(db).get_waterfall(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{deal_id}/runs/{run_id}/waterfall/pdf")
def waterfall_pdf(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a print-friendly HTML waterfall comparison report."""
    from fastapi.responses import HTMLResponse
    from app.processing.waterfall_pdf import render_waterfall_html

    try:
        data = ProcessingService(db).get_waterfall(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HTMLResponse(content=render_waterfall_html(data))


# ── Single-variable re-extract (used after cell remap) ──


@router.post("/{deal_id}/runs/{run_id}/reextract-variable/{variable_id}")
def reextract_variable(
    deal_id: int,
    run_id: int,
    variable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-read a single variable from the tape (used after remapping a cell)."""
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")
    try:
        ev = ProcessingService(db).reextract_variable(run_id, variable_id)
        return {
            "variable_id": ev.variable_id,
            "variable": ev.variable_name,
            "cell": ev.cell_ref,
            "sheet": ev.sheet_name,
            "raw": ev.raw_value,
            "parsed": str(ev.parsed_value) if ev.parsed_value is not None else None,
            "prior": str(ev.prior_value) if ev.prior_value is not None else None,
            "pct_change": str(ev.pct_change) if ev.pct_change is not None else None,
            "warning": ev.warning,
            "data_type": ev.data_type,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Step 6: Export ──


@router.post("/{deal_id}/runs/{run_id}/export")
def export_csv(
    deal_id: int,
    run_id: int,
    template_id: int = 1,
    db: Session = Depends(get_db),
    _deal: Deal = Depends(require_processable_deal),
):
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if not run or run.deal_id != deal_id:
        raise HTTPException(404, "Run not found")

    from app.global_export.service import GlobalExportService

    svc = GlobalExportService(db)
    try:
        path, file_hash = svc.generate_csv(run, template_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    run.status = "completed"
    run.completed_at = datetime.utcnow()
    db.flush()
    return {"file_path": path, "hash": file_hash, "status": "completed"}



# ── Deal cloning ──


class CloneRequest(BaseModel):
    new_name: str
    clone_dag: bool = True
    clone_mappings: bool = True
    clone_tranches: bool = True


@router.post("/{deal_id}/clone", status_code=201)
def clone_deal(
    deal_id: int,
    body: CloneRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    svc = CloneService(db)
    new_deal = svc.clone_deal(
        deal_id,
        body.new_name,
        user.username,
        clone_dag=body.clone_dag,
        clone_mappings=body.clone_mappings,
        clone_tranches=body.clone_tranches,
    )
    return {"id": new_deal.id, "name": new_deal.name, "cloned_from_id": deal_id}


def _build_synthetic_lineage(
    db: Session, deal_id: int, run_id: int, node_key: str
) -> dict | None:
    """Fallback lineage builder for values that aren't real DagNodes.

    Covers three classes of executor-injected context variables:
      - Period-computed day counts (period_days_in_period_*)
      - Deal-level numeric constants (deal_*)
      - Extracted tape variables (anything with a mapped ExtractedValue)
    """
    run = db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
    if run is None or run.deal_id != deal_id:
        return None
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if deal is None:
        return None

    def _envelope(target_name: str, target_type: str, target_result, nodes: list) -> dict:
        return {
            "target_node_key": node_key,
            "target_node_name": target_name,
            "target_node_type": target_type,
            "target_result": (str(target_result) if target_result is not None else None),
            "lineage_count": len(nodes),
            "nodes": nodes,
        }

    # 1. Period-computed day counts — show anchor + distribution + formula
    if node_key in ("period_days_in_period_30_360", "period_days_in_period_actual"):
        prior_run = (
            db.query(ProcessingRun)
            .filter(ProcessingRun.id == run.prior_run_id)
            .first()
            if run.prior_run_id
            else None
        )
        anchor_date = (
            prior_run.distribution_date
            if prior_run and prior_run.distribution_date
            else deal.initial_cutoff_date
        )
        anchor_source = (
            "prior_run"
            if prior_run and prior_run.distribution_date
            else ("initial_cutoff" if deal.initial_cutoff_date else "none")
        )
        is_30_360 = node_key == "period_days_in_period_30_360"
        result_val = (
            run.days_in_period_30_360 if is_30_360 else run.days_in_period_actual
        )
        display_name = (
            "Days in period (30/360)" if is_30_360 else "Days in period (actual)"
        )
        convention = "30/360" if is_30_360 else "actual/365"
        formula_str = (
            f"{convention}({anchor_date} → {run.distribution_date})"
            if run.distribution_date and anchor_date
            else "—"
        )

        anc_nodes = []
        if anchor_date:
            anc_nodes.append(
                {
                    "node_key": "anchor_date",
                    "node_name": f"Anchor date ({anchor_source})",
                    "node_type": "input_value",
                    "stream": "period",
                    "execution_order": 1,
                    "formula": None,
                    "formula_resolved": None,
                    "result": anchor_date.isoformat(),
                    "prior_value": None,
                    "delta_pct": None,
                    "is_suspect": False,
                    "suspect_reason": None,
                    "upstream_keys": [],
                    "comparison_value": None,
                    "difference": None,
                    "tolerance": None,
                    "validation_passed": None,
                    "input_source": anchor_source,
                    "cell_ref": None,
                }
            )
        if run.distribution_date:
            anc_nodes.append(
                {
                    "node_key": "distribution_date",
                    "node_name": "Distribution date",
                    "node_type": "input_value",
                    "stream": "period",
                    "execution_order": 2,
                    "formula": None,
                    "formula_resolved": None,
                    "result": run.distribution_date.isoformat(),
                    "prior_value": None,
                    "delta_pct": None,
                    "is_suspect": False,
                    "suspect_reason": None,
                    "upstream_keys": [],
                    "comparison_value": None,
                    "difference": None,
                    "tolerance": None,
                    "validation_passed": None,
                    "input_source": None,
                    "cell_ref": None,
                }
            )
        anc_nodes.append(
            {
                "node_key": node_key,
                "node_name": display_name,
                "node_type": "calculation",
                "stream": "period",
                "execution_order": 3,
                "formula": formula_str,
                "formula_resolved": f"= {result_val}" if result_val is not None else None,
                "result": str(result_val) if result_val is not None else None,
                "prior_value": None,
                "delta_pct": None,
                "is_suspect": False,
                "suspect_reason": (
                    f"Day-count convention: {convention}. "
                    f"Anchor is {anchor_source.replace('_', ' ')} "
                    f"({anchor_date.isoformat() if anchor_date else 'missing'}). "
                    "Check that the anchor date matches what the servicer used."
                ),
                "upstream_keys": [
                    k for k in ("anchor_date", "distribution_date")
                    if any(n["node_key"] == k for n in anc_nodes)
                ],
                "comparison_value": None,
                "difference": None,
                "tolerance": None,
                "validation_passed": None,
                "input_source": "period_computation",
                "cell_ref": None,
            }
        )
        return _envelope(display_name, "calculation", result_val, anc_nodes)

    # 2. Deal-level constants
    deal_const_map = {
        "deal_cutoff_pool_balance": ("Cutoff pool balance", deal.cutoff_pool_balance),
        "deal_distribution_day_of_month": (
            "Distribution day of month", deal.distribution_day_of_month,
        ),
        "deal_determination_days_before": (
            "Determination days before", deal.determination_business_days_before,
        ),
        "deal_servicing_fee_pct": ("Servicing fee %", deal.servicing_fee_pct),
        "deal_backup_servicing_fee_pct": (
            "Backup servicing fee %", deal.backup_servicing_fee_pct,
        ),
        "deal_trustee_fee_monthly": ("Trustee fee (monthly)", deal.trustee_fee_monthly),
        "deal_target_oc_pct": ("Target OC %", deal.target_oc_pct),
        "deal_target_oc_floor_pct": ("Target OC floor %", deal.target_oc_floor_pct),
        "deal_target_oc_floor_amount": (
            "Target OC floor $", deal.target_oc_floor_amount,
        ),
        "deal_reserve_required_pct": ("Reserve required %", deal.reserve_required_pct),
    }
    if node_key in deal_const_map:
        name, val = deal_const_map[node_key]
        node = {
            "node_key": node_key,
            "node_name": name,
            "node_type": "input_value",
            "stream": "deal",
            "execution_order": 1,
            "formula": None,
            "formula_resolved": None,
            "result": str(val) if val is not None else None,
            "prior_value": None,
            "delta_pct": None,
            "is_suspect": False,
            "suspect_reason": "Set on the Deal record. Edit via Deal → Info.",
            "upstream_keys": [],
            "comparison_value": None,
            "difference": None,
            "tolerance": None,
            "validation_passed": None,
            "input_source": "deal_record",
            "cell_ref": None,
        }
        return _envelope(name, "input_value", val, [node])

    # 3. Extracted tape variable
    ev = (
        db.query(ExtractedValue)
        .filter(
            ExtractedValue.run_id == run_id, ExtractedValue.variable_name == node_key
        )
        .first()
    )
    if ev is not None:
        node = {
            "node_key": node_key,
            "node_name": node_key,
            "node_type": "input_value",
            "stream": "tape",
            "execution_order": 1,
            "formula": None,
            "formula_resolved": None,
            "result": str(ev.parsed_value) if ev.parsed_value is not None else None,
            "prior_value": str(ev.prior_value) if ev.prior_value is not None else None,
            "delta_pct": str(ev.pct_change) if ev.pct_change is not None else None,
            "is_suspect": False,
            "suspect_reason": (
                f"Extracted from tape cell {ev.sheet_name}!{ev.cell_ref} "
                f"(raw: {ev.raw_value!r})."
            ),
            "upstream_keys": [],
            "comparison_value": None,
            "difference": None,
            "tolerance": None,
            "validation_passed": None,
            "input_source": "tape",
            "cell_ref": f"{ev.sheet_name}!{ev.cell_ref}",
        }
        return _envelope(node_key, "input_value", ev.parsed_value, [node])

    return None
