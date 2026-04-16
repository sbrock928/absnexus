"""Global export templates — HTTP routing layer."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role, require_editable_deal
from app.global_export.dao import GlobalExportDAO
from app.global_export.service import GlobalExportService
from app.models.deal import Deal
from app.models.user import User
from app.schemas.global_export import (
    DealExportConfigResponse,
    DealExportConfigSave,
    GlobalColumnCreate,
    GlobalColumnResponse,
    GlobalColumnUpdate,
    GlobalTemplateResponse,
    ReorderRequest,
    TemplateWithColumnsResponse,
)

router = APIRouter()


# ── Templates ──


@router.get("/export-templates", response_model=list[GlobalTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    return GlobalExportService(db).list_templates()


@router.get("/export-templates/{template_id}", response_model=TemplateWithColumnsResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    try:
        return GlobalExportService(db).get_template_with_columns(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Columns CRUD (admin/analytics only) ──


@router.post(
    "/export-templates/{template_id}/columns",
    response_model=GlobalColumnResponse,
    status_code=201,
)
def create_column(
    template_id: int,
    body: GlobalColumnCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "analytics")),
):
    dao = GlobalExportDAO(db)
    t = dao.get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    pos = dao.next_position(template_id)
    return dao.create_column(template_id, pos, **body.model_dump())


@router.patch("/global-export-columns/{column_id}", response_model=GlobalColumnResponse)
def update_column(
    column_id: int,
    body: GlobalColumnUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "analytics")),
):
    dao = GlobalExportDAO(db)
    col = dao.get_column(column_id)
    if col is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    return dao.update_column(col, **body.model_dump(exclude_unset=True))


@router.delete("/global-export-columns/{column_id}", status_code=204)
def delete_column(
    column_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "analytics")),
) -> None:
    dao = GlobalExportDAO(db)
    col = dao.get_column(column_id)
    if col is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    dao.delete_column(col)


@router.post(
    "/export-templates/{template_id}/columns/reorder",
    response_model=list[GlobalColumnResponse],
)
def reorder_columns(
    template_id: int,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "analytics")),
):
    return GlobalExportDAO(db).reorder_columns(template_id, body.ordered_column_ids)


# ── Deal export config (row-level) ──


@router.get(
    "/deals/{deal_id}/export-config/{template_id}",
    response_model=DealExportConfigResponse,
)
def get_deal_config(
    deal_id: int,
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return GlobalExportService(db).get_deal_config(deal_id, template_id)


@router.put(
    "/deals/{deal_id}/export-config/{template_id}",
    response_model=DealExportConfigResponse,
)
def save_deal_config(
    deal_id: int,
    template_id: int,
    body: DealExportConfigSave,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    rows_data = [
        {
            "node_id": r.node_id,
            "row_order": r.row_order,
            "identifier_group": r.identifier_group,
            "cells": [
                {
                    "column_id": c.column_id,
                    "value_source": c.value_source,
                    "source_ref": c.source_ref,
                }
                for c in r.cells
            ],
        }
        for r in body.rows
    ]
    return GlobalExportService(db).save_deal_config(deal_id, template_id, rows_data)


# ── Preview ──


@router.get("/deals/{deal_id}/export-preview/{template_id}")
def preview_export_json(
    deal_id: int,
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Structured preview for the inline grid."""
    return GlobalExportService(db).preview_structured(deal_id, template_id)


@router.get("/deals/{deal_id}/export-preview/{template_id}/xlsx")
def preview_export_xlsx(
    deal_id: int,
    template_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Downloadable .xlsx preview with placeholder values."""
    data = GlobalExportService(db).preview_xlsx(deal_id, template_id)
    filename = f"preview_deal_{deal_id}_template_{template_id}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
