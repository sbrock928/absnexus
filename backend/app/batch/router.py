"""Batch — HTTP routing layer."""

import hashlib
import os
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.batch.service import BatchService, DealTapeInput
from app.core.database import get_db
from app.dependencies import get_current_user
from app.services.deal_service import DealService
from app.models.batch import BatchRun
from app.models.user import User
from app.schemas.batch import BatchCreateRequest, BatchResponse
from app.utils.file_manager import FileManager

router = APIRouter()


@router.post("/batches/upload-tape/{deal_id}")
def upload_tape_for_batch(
    deal_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Upload a tape file for a deal (standalone, not attached to a run yet)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    fm = FileManager()
    stored = fm.store_upload(deal_id, file.filename or "tape.xlsx", tmp_path)
    os.unlink(tmp_path)

    file_hash = hashlib.sha256(content).hexdigest()
    return {
        "filename": file.filename or "tape.xlsx",
        "file_path": stored,
        "file_hash": file_hash,
    }


@router.get("/batches", response_model=list[BatchResponse])
def list_batches(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchRun]:
    return BatchService(db).list_recent(limit)


@router.get("/batches/{batch_id}", response_model=BatchResponse)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchRun:
    batch = BatchService(db).get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch


@router.get("/batches/{batch_id}/summary")
def get_batch_summary(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return BatchService(db).get_batch_summary(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/batches", response_model=BatchResponse, status_code=201)
def create_batch(
    payload: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchRun:
    """Create a batch and its child runs. Does NOT execute yet."""
    if not payload.deal_inputs:
        raise HTTPException(
            status_code=400,
            detail="Must include at least one deal.",
        )
    inputs = [
        DealTapeInput(
            deal_id=di.deal_id,
            source_filename=di.source_filename,
            source_file_path=di.source_file_path,
            source_file_hash=di.source_file_hash,
        )
        for di in payload.deal_inputs
    ]
    return BatchService(db).create_batch(
        period=payload.report_period,
        username=current_user.username,
        deal_inputs=inputs,
    )


@router.post("/batches/{batch_id}/execute", response_model=BatchResponse)
def execute_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchRun:
    """Execute all runs in the batch sequentially."""
    batch = BatchService(db).get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    try:
        return BatchService(db).execute_batch(batch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/batches/{batch_id}/zip")
def download_batch_zip(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download all exports in the batch as a single zip file."""
    batch = BatchService(db).get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")

    buffer = BatchService(db).generate_batch_zip(batch_id)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{batch.batch_code}.zip"',
        },
    )
