import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database.db import get_db
from utils.logger import get_logger

log = get_logger("progress_api")
router = APIRouter()

# In-memory progress store keyed by document_id
# {doc_id: {"stage": str, "current": int, "total": int, "facts": int, "relationships": int}}
_progress: dict[str, dict] = {}


def update_progress(
    doc_id: str,
    stage: str,
    current: int = 0,
    total: int = 0,
    facts: int = 0,
    relationships: int = 0,
):
    """Called by background tasks to push progress updates."""
    _progress[doc_id] = {
        "stage": stage,
        "current": current,
        "total": total,
        "facts": facts,
        "relationships": relationships,
    }


def get_progress(doc_id: str) -> dict:
    return _progress.get(doc_id, {})


def clear_progress(doc_id: str):
    _progress.pop(doc_id, None)


async def _event_generator(doc_id: str):
    """
    Async generator that yields SSE events for a document's processing progress.
    Polls DB status + in-memory progress every second.
    Stops when status is completed or failed.
    """
    terminal_states = {"completed", "failed"}
    last_sent = None
    idle_ticks = 0

    while True:
        with get_db() as conn:
            doc = conn.execute(
                "SELECT status, page_count FROM documents WHERE id=?", (doc_id,)
            ).fetchone()
            if not doc:
                yield f"data: {json.dumps({'error': 'Document not found'})}\n\n"
                return

            facts_count = conn.execute(
                "SELECT COUNT(*) FROM facts WHERE document_id=?", (doc_id,)
            ).fetchone()[0]

            rels_count = conn.execute(
                """SELECT COUNT(*) FROM relationships r
                   JOIN facts f ON r.source_fact_id = f.id
                   WHERE f.document_id=?""",
                (doc_id,),
            ).fetchone()[0]

            processed_pages = conn.execute(
                "SELECT COUNT(*) FROM document_pages WHERE document_id=? AND processed=1",
                (doc_id,),
            ).fetchone()[0]

        mem_progress = get_progress(doc_id)

        payload = {
            "status": doc["status"],
            "page_count": doc["page_count"],
            "processed_pages": processed_pages,
            "facts_found": facts_count,
            "relationships_found": rels_count,
            "stage": mem_progress.get("stage", doc["status"]),
            "pct": round((processed_pages / max(doc["page_count"], 1)) * 100),
        }

        # Only send if something changed
        if payload != last_sent:
            yield f"data: {json.dumps(payload)}\n\n"
            last_sent = payload
            idle_ticks = 0
        else:
            idle_ticks += 1

        if doc["status"] in terminal_states:
            # Send final event then close
            yield f"data: {json.dumps({**payload, 'done': True})}\n\n"
            clear_progress(doc_id)
            return

        # Stop streaming after 5 minutes of no activity
        if idle_ticks > 300:
            yield f"data: {json.dumps({'timeout': True})}\n\n"
            return

        await asyncio.sleep(1)


@router.get("/documents/{doc_id}/progress")
async def stream_progress(doc_id: str):
    """SSE endpoint — stream live processing progress for a document."""
    with get_db() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    log.info("SSE stream opened for document %s", doc_id)

    return StreamingResponse(
        _event_generator(doc_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
