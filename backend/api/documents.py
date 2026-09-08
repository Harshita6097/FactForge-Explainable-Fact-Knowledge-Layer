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
from services.relationship_engine import analyze_document_relationships
from services.incremental_indexer import is_duplicate_document
from services.knowledge_layer import build_canonical_facts_for_document
from api.progress import update_progress, clear_progress
from utils.config import get_settings
from utils.logger import get_logger

settings = get_settings()
log = get_logger("documents_api")
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
    """Background task: extract pages, mine facts, analyze relationships."""
    try:
        log.info("Starting processing for document %s", doc_id)
        update_progress(doc_id, "processing")
        _update_status(doc_id, "processing")

        pages = extract_pages(file_path)
        _update_status(doc_id, "extracted", len(pages))
        update_progress(doc_id, "extracted", total=len(pages))
        log.info("Extracted %d pages for document %s", len(pages), doc_id)

        with get_db() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO document_pages (id, document_id, page_number, text, char_count)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (str(uuid.uuid4()), doc_id, p.page_number, p.text, p.char_count)
                    for p in pages
                ],
            )

        _update_status(doc_id, "mining")
        update_progress(doc_id, "mining", total=len(pages))

        with get_db() as conn:
            doc = conn.execute(
                "SELECT original_filename FROM documents WHERE id=?", (doc_id,)
            ).fetchone()
        filename = doc["original_filename"] if doc else "unknown"
        total_facts = mine_facts_for_document(doc_id, filename)
        log.info("Mining complete for %s — %d facts stored", filename, total_facts)

        _update_status(doc_id, "analyzing")
        update_progress(doc_id, "analyzing", total=len(pages), facts=total_facts)
        total_rels = analyze_document_relationships(doc_id)
        log.info("Relationship analysis complete for %s — %d relationships", filename, total_rels)

        # Build canonical knowledge layer
        build_canonical_facts_for_document(doc_id)

        _update_status(doc_id, "completed")
        update_progress(doc_id, "completed", total=len(pages), facts=total_facts, relationships=total_rels)
    except Exception as e:
        log.error("Processing failed for document %s: %s", doc_id, e, exc_info=True)
        with get_db() as conn:
            conn.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))
        update_progress(doc_id, "failed")
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

    # Check for duplicate document before processing
    existing_id = is_duplicate_document(file.filename, page_count)
    if existing_id:
        upload_path.unlink(missing_ok=True)
        log.info("Duplicate upload rejected: %s already exists as %s", file.filename, existing_id)
        with get_db() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (existing_id,)).fetchone()
        return DocumentResponse(**dict(row))

    log.info("Upload received: %s (%d pages)", file.filename, page_count)
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
        # Delete in dependency order
        fact_ids = [r[0] for r in conn.execute(
            "SELECT id FROM facts WHERE document_id=?", (doc_id,)
        ).fetchall()]
        if fact_ids:
            ph = ",".join("?" * len(fact_ids))
            # Delete reasoning BEFORE relationships (FK constraint)
            rel_ids = [r[0] for r in conn.execute(
                f"SELECT id FROM relationships WHERE source_fact_id IN ({ph}) OR target_fact_id IN ({ph})",
                fact_ids + fact_ids,
            ).fetchall()]
            if rel_ids:
                rph = ",".join("?" * len(rel_ids))
                conn.execute(f"DELETE FROM relationship_reasoning WHERE relationship_id IN ({rph})", rel_ids)
                conn.execute(f"DELETE FROM relationships WHERE id IN ({rph})", rel_ids)
        if fact_ids:
            for fid in fact_ids:
                conn.execute(
                    "DELETE FROM canonical_facts WHERE source_fact_ids LIKE ?",
                    (f'%"{fid}"%',),
                )
        conn.execute("DELETE FROM evidence WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM document_pages WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM facts WHERE document_id=?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))

    file_path = Path(settings.upload_dir) / doc["filename"]
    file_path.unlink(missing_ok=True)
    return {"message": "Document deleted"}
