"""Mapping endpoints — nested under /api/deals/{deal_id}/mappings."""

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role, require_editable_deal, get_current_user
from app.models.deal import Deal
from app.models.user import User
from app.models.processing import ProcessingRun
from app.schemas.mapping import MappingCreate, MappingUpdate, MappingResponse
from app.mappings.dao import MappingDAO
from app.mappings.service import MappingService
from app.services.deal_service import DealService
from app.utils.excel_reader import ExcelReader
from app.utils.file_manager import FileManager

router = APIRouter()


@router.get("/{deal_id}/mappings", response_model=list[MappingResponse])
def list_mappings(deal_id: int, db: Session = Depends(get_db)):
    return MappingDAO(db).list_for_deal(deal_id)


@router.post("/{deal_id}/mappings", response_model=MappingResponse, status_code=201)
def create_mapping(
    deal_id: int,
    body: MappingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    return MappingDAO(db).create(deal_id=deal_id, **body.model_dump())


@router.patch("/{deal_id}/mappings/{mapping_id}", response_model=MappingResponse)
def update_mapping(
    deal_id: int,
    mapping_id: int,
    body: MappingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    dao = MappingDAO(db)
    m = dao.get(mapping_id)
    if not m or m.deal_id != deal_id:
        raise HTTPException(404, "Mapping not found")
    return dao.update(m, **body.model_dump(exclude_unset=True))


@router.delete("/{deal_id}/mappings/{mapping_id}", status_code=204)
def delete_mapping(
    deal_id: int,
    mapping_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    dao = MappingDAO(db)
    m = dao.get(mapping_id)
    if not m or m.deal_id != deal_id:
        raise HTTPException(404, "Mapping not found")
    dao.delete(m)


@router.get("/{deal_id}/tape-grid")
def get_tape_grid(
    deal_id: int,
    sheet: str | None = Query(None),
    run_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the deal's tape as a navigable grid for the cell mapper.

    Looks up the tape from the most recent processing run (or a specific
    run_id if provided).
    """
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found.")

    # Find tape path from runs
    if run_id:
        run = (
            db.query(ProcessingRun)
            .filter(
                ProcessingRun.id == run_id,
                ProcessingRun.deal_id == deal_id,
            )
            .first()
        )
        if not run or not run.tape_file_path:
            raise HTTPException(404, "Run or tape not found.")
        tape_path = run.tape_file_path
    else:
        run = (
            db.query(ProcessingRun)
            .filter(
                ProcessingRun.deal_id == deal_id,
                ProcessingRun.tape_file_path.isnot(None),
            )
            .order_by(ProcessingRun.created_at.desc())
            .first()
        )
        if not run or not run.tape_file_path:
            raise HTTPException(404, "No tape uploaded for this deal yet.")
        tape_path = run.tape_file_path

    if not Path(tape_path).exists():
        raise HTTPException(404, "Tape file no longer exists on disk.")

    with ExcelReader(tape_path) as reader:
        sheet_names = reader.get_sheet_names()

        if sheet:
            if sheet not in sheet_names:
                raise HTTPException(404, f"Sheet '{sheet}' not found.")
            grid = reader.read_sheet_grid(sheet)
            return {
                "filename": tape_path.split("/")[-1] if "/" in tape_path else tape_path,
                "sheet_names": sheet_names,
                "sheet": grid,
            }

        return {
            "filename": tape_path.split("/")[-1] if "/" in tape_path else tape_path,
            "sheet_names": sheet_names,
            "sheets": [reader.read_sheet_grid(s) for s in sheet_names],
        }


@router.post("/{deal_id}/tape/upload")
def upload_tape(
    deal_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _deal: Deal = Depends(require_editable_deal),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        fm = FileManager()
        stored_path = fm.store_upload(deal_id, file.filename or "tape.xlsx", tmp_path)
        reader = ExcelReader(stored_path)
        sheets = {}
        for sn in reader.get_sheet_names():
            sheets[sn] = reader.get_sheet_grid(sn, max_rows=50)
        reader.close()
        return {"file_path": stored_path, "sheets": sheets}
    finally:
        os.unlink(tmp_path)


@router.post("/{deal_id}/mappings/test-extract")
def test_extract(
    deal_id: int,
    file_path: str,
    sheet_name: str,
    column_letter: str,
    row_number: int,
    db: Session = Depends(get_db),
):
    svc = MappingService(db)
    value = svc.test_extract(file_path, sheet_name, column_letter, row_number)
    return {"value": value, "type": type(value).__name__}
