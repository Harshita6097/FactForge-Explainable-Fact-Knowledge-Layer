import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from database.db import get_db
from models.document import DocumentResponse, ProcessingStatus
from services.document_processor import extract_pages, get_page_count, is_valid_pdf
from services.fact_miner import mine_facts_for_document
from utils.config import get_settings

settings = get_settings()
router = APIRouter()


def _save_document_record(doc_id: str, filename: str, original_filename: str, page_count: int):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO documents (id, filename, original_filename, page_count, status, uploaded_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (doc_id, filename, original_filename, page_count,
             datetime.now(timezone.utc).isoformat()),
        )


def _update_status(doc_id: str, status: str, page_count: Optional[int] = None):
    with get_db() as conn:
        if page_count is not None:
            conn.execute(
                "UPDATE documents SET status=?, page_count=? WHERE id=?",
                (status, page_count, doc_id),
            )
        else:
            processed_at = datetime.now(timezone.utc).isoformat() if status == "completed" else None
            conn.execute(
                "UPDATE documents SET status=?, processed_at=? WHERE id=?",
                (status, processed_at, doc_id),
            )


def _process_document_background(doc_id: str, file_path: str):
    """Background task: extract pages and store them, then mark ready for fact mining."""
    try:
        _update_status(doc_id, "processing")
        pages = extract_pages(file_path)
        _update_status(doc_id, "extracted", len(pages))

        # Store raw pages in a lightweight pages table for incremental processing
        with get_db() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO document_pages (id, document_id, page_number, text, char_count)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (str(uuid.uuid4()), doc_id, p.page_number, p.text, p.char_count)
                    for p in pages
                ],
            )
        # Mine facts from extracted pages via Gemini
        _update_status(doc_id, "mining")
        with get_db() as conn:
            doc = conn.execute(
                "SELECT original_filename FROM documents WHERE id=?", (doc_id,)
            ).fetchone()
        filename = doc["original_filename"] if doc else "unknown"
        mine_facts_for_document(doc_id, filename)
        _update_status(doc_id, "completed")
    except Exception as e:
        with get_db() as conn:
            conn.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))
        raise e


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}.pdf"
    upload_path = Path(settings.upload_dir) / safe_name

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if not is_valid_pdf(str(upload_path)):
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF")

    page_count = get_page_count(str(upload_path))
    _save_document_record(doc_id, safe_name, file.filename, page_count)
    background_tasks.add_task(_process_document_background, doc_id, str(upload_path))

    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()

    return DocumentResponse(**dict(row))


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
    return [DocumentResponse(**dict(r)) for r in rows]


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**dict(row))


@router.get("/documents/{doc_id}/status", response_model=ProcessingStatus)
def get_document_status(doc_id: str):
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        facts_count = conn.execute(
            "SELECT COUNT(*) FROM facts WHERE document_id=?", (doc_id,)
        ).fetchone()[0]
        relationships_count = conn.execute(
            """SELECT COUNT(*) FROM relationships r
               JOIN facts f ON r.source_fact_id = f.id
               WHERE f.document_id=?""",
            (doc_id,),
        ).fetchone()[0]

    return ProcessingStatus(
        document_id=doc_id,
        status=doc["status"],
        page_count=doc["page_count"],
        facts_found=facts_count,
        relationships_found=relationships_count,
    )


@router.get("/documents/{doc_id}/pages")
def get_document_pages(doc_id: str):
    with get_db() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        pages = conn.execute(
            "SELECT page_number, char_count FROM document_pages WHERE document_id=? ORDER BY page_number",
            (doc_id,),
        ).fetchall()
    return [dict(p) for p in pages]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    with get_db() as conn:
        doc = conn.execute("SELECT filename FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        conn.execute("DELETE FROM evidence WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM document_pages WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM facts WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))

    file_path = Path(settings.upload_dir) / doc["filename"]
    file_path.unlink(missing_ok=True)
    return {"message": "Document deleted"}
