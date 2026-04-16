"""Mapping endpoints — nested under /api/deals/{deal_id}/mappings."""
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.mapping import MappingCreate, MappingUpdate, MappingResponse
from app.mappings.dao import MappingDAO
from app.mappings.service import MappingService
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
):
    return MappingDAO(db).create(deal_id=deal_id, **body.model_dump())


@router.patch("/{deal_id}/mappings/{mapping_id}", response_model=MappingResponse)
def update_mapping(
    deal_id: int,
    mapping_id: int,
    body: MappingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
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
):
    dao = MappingDAO(db)
    m = dao.get(mapping_id)
    if not m or m.deal_id != deal_id:
        raise HTTPException(404, "Mapping not found")
    dao.delete(m)


@router.post("/{deal_id}/tape/upload")
def upload_tape(
    deal_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
