from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from database.db import get_db
from services.relationship_engine import analyze_document_relationships
from utils.logger import get_logger
import json

log = get_logger("relationships_api")
router = APIRouter()


def _enrich_relationship(row: dict) -> dict:
    """Attach source and target fact details including evidence and reasoning."""
    with get_db() as conn:
        src = conn.execute(
            """SELECT f.*, e.page_number, e.snippet, d.original_filename
               FROM facts f
               LEFT JOIN evidence e ON e.fact_id = f.id
               LEFT JOIN documents d ON d.id = f.document_id
               WHERE f.id=? LIMIT 1""",
            (row["source_fact_id"],),
        ).fetchone()
        tgt = conn.execute(
            """SELECT f.*, e.page_number, e.snippet, d.original_filename
               FROM facts f
               LEFT JOIN evidence e ON e.fact_id = f.id
               LEFT JOIN documents d ON d.id = f.document_id
               WHERE f.id=? LIMIT 1""",
            (row["target_fact_id"],),
        ).fetchone()
        reasoning = conn.execute(
            "SELECT steps FROM relationship_reasoning WHERE relationship_id=?",
            (row["id"],),
        ).fetchone()

    return {
        **row,
        "source_fact": dict(src) if src else None,
        "target_fact": dict(tgt) if tgt else None,
        "reasoning_steps": json.loads(reasoning["steps"]) if reasoning else [],
    }


@router.get("/relationships")
def list_relationships(
    relationship_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    conditions = []
    params: list = []

    if relationship_type:
        conditions.append("relationship_type = ?")
        params.append(relationship_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT * FROM relationships {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params,
        ).fetchall()

    return [_enrich_relationship(dict(r)) for r in rows]


@router.get("/relationships/summary")
def relationships_summary():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT relationship_type, COUNT(*) as count
               FROM relationships GROUP BY relationship_type"""
        ).fetchall()
    return {r["relationship_type"]: r["count"] for r in rows}


@router.get("/relationships/{rel_id}")
def get_relationship(rel_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM relationships WHERE id=?", (rel_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return _enrich_relationship(dict(row))


@router.post("/documents/{doc_id}/analyze")
def trigger_analysis(doc_id: str, background_tasks: BackgroundTasks):
    """Manually trigger relationship analysis for a document."""
    with get_db() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    background_tasks.add_task(analyze_document_relationships, doc_id)
    log.info("Manual relationship analysis triggered for document %s", doc_id)
    return {"message": "Relationship analysis started", "document_id": doc_id}


@router.get("/facts/{fact_id}/relationships")
def get_fact_relationships(fact_id: str):
    with get_db() as conn:
        fact = conn.execute("SELECT id FROM facts WHERE id=?", (fact_id,)).fetchone()
        if not fact:
            raise HTTPException(status_code=404, detail="Fact not found")
        rows = conn.execute(
            """SELECT * FROM relationships
               WHERE source_fact_id=? OR target_fact_id=?
               ORDER BY confidence DESC""",
            (fact_id, fact_id),
        ).fetchall()
    return [_enrich_relationship(dict(r)) for r in rows]
