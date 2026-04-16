"""Export — HTTP routing layer."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role, require_editable_deal
from app.models.deal import Deal
from app.export.service import PRESETS, ExportColumnService
from app.models.export import ExportColumn
from app.models.processing import ProcessingRun
from app.models.user import User
from app.services.deal_service import DealService
from app.schemas.export import (
    ColumnCreate, ColumnResponse, ColumnUpdate,
    CopyPresetRequest, PresetInfo, PreviewResponse, ReorderRequest,
)

router = APIRouter()


# ── Presets ───────────────────────────────────────────────────

@router.get("/export-presets", response_model=list[PresetInfo])
def list_presets(current_user: User = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "key": key,
            "name": p["name"],
            "description": p["description"],
            "column_count": len(p["columns"]),
        }
        for key, p in PRESETS.items()
    ]


# ── Columns CRUD ──────────────────────────────────────────────

@router.get("/deals/{deal_id}/export-columns", response_model=list[ColumnResponse])
def list_columns(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExportColumn]:
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found.")
    return ExportColumnService(db).list_columns(deal_id)


@router.post("/deals/{deal_id}/export-columns", response_model=ColumnResponse, status_code=201)
def create_column(
    deal_id: int,
    payload: ColumnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
) -> ExportColumn:
    return ExportColumnService(db).create_column(deal_id=deal_id, **payload.model_dump())


@router.patch("/export-columns/{column_id}", response_model=ColumnResponse)
def update_column(
    column_id: int,
    payload: ColumnUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
) -> ExportColumn:
    svc = ExportColumnService(db)
    col = svc.get_column(column_id)
    if col is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    deal = DealService(db).get(col.deal_id)
    if deal and deal.status == "archived":
        raise HTTPException(status_code=403, detail="Deal is archived. Reactivate before editing.")
    return svc.update_column(col, **payload.model_dump(exclude_unset=True))


@router.delete("/export-columns/{column_id}", status_code=204)
def delete_column(
    column_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
) -> None:
    svc = ExportColumnService(db)
    col = svc.get_column(column_id)
    if col is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    deal = DealService(db).get(col.deal_id)
    if deal and deal.status == "archived":
        raise HTTPException(status_code=403, detail="Deal is archived. Reactivate before editing.")
    svc.delete_column(col)


@router.post("/deals/{deal_id}/export-columns/reorder", response_model=list[ColumnResponse])
def reorder_columns(
    deal_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
) -> list[ExportColumn]:
    return ExportColumnService(db).reorder_columns(deal_id, payload.ordered_column_ids)


@router.post("/deals/{deal_id}/export-columns/copy-preset", response_model=list[ColumnResponse])
def copy_preset(
    deal_id: int,
    payload: CopyPresetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
) -> list[ExportColumn]:
    try:
        return ExportColumnService(db).copy_preset(deal_id, payload.preset_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Preview ───────────────────────────────────────────────────

@router.get("/deals/{deal_id}/export-preview", response_model=PreviewResponse)
def preview_export(
    deal_id: int,
    run_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    csv_text = ExportColumnService(db).preview(deal_id, run_id)
    row_count = max(0, len(csv_text.strip().split("\n")) - 1)
    return {"csv": csv_text, "row_count": row_count}


# ── Generate + download ──────────────────────────────────────

@router.post("/deals/{deal_id}/runs/{run_id}/export-columns")
def export_csv(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    run = db.query(ProcessingRun).filter(
        ProcessingRun.id == run_id, ProcessingRun.deal_id == deal_id,
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    try:
        file_path, file_hash = ExportColumnService(db).generate_csv(run)
        return {"file_path": file_path, "hash": file_hash, "status": "completed"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/deals/{deal_id}/runs/{run_id}/export-columns/file")
def download_export(
    deal_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    run = db.query(ProcessingRun).filter(
        ProcessingRun.id == run_id, ProcessingRun.deal_id == deal_id,
    ).first()
    if run is None or not run.export_file_path:
        raise HTTPException(status_code=404, detail="No export file available.")
    return FileResponse(
        path=run.export_file_path,
        media_type="text/csv",
        filename=run.export_file_path.split("/")[-1],
    )
