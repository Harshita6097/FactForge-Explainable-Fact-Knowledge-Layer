from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from database.db import get_db
from services.relationship_engine import analyze_document_relationships, get_extraction_failures
from utils.logger import get_logger
from utils.auth import get_current_user
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


@router.get("/extraction-failures")
def list_extraction_failures(
    project_id: str | None = Query(None),
    document_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    user: dict = Depends(get_current_user),
):
    """Return logged extraction failures scoped to the user's projects."""
    with get_db() as conn:
        if document_id:
            # Verify ownership
            doc = conn.execute(
                "SELECT id FROM documents WHERE id=? AND project_id IN (SELECT id FROM projects WHERE user_id=?)",
                (document_id, user["id"]),
            ).fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            rows = conn.execute(
                """SELECT ef.*, d.original_filename FROM extraction_failures ef
                   JOIN documents d ON ef.document_id=d.id
                   WHERE ef.document_id=? ORDER BY ef.created_at DESC LIMIT ?""",
                (document_id, limit),
            ).fetchall()
        elif project_id:
            rows = conn.execute(
                """SELECT ef.*, d.original_filename FROM extraction_failures ef
                   JOIN documents d ON ef.document_id=d.id
                   WHERE d.project_id=? AND d.project_id IN (SELECT id FROM projects WHERE user_id=?)
                   ORDER BY ef.created_at DESC LIMIT ?""",
                (project_id, user["id"], limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ef.*, d.original_filename FROM extraction_failures ef
                   JOIN documents d ON ef.document_id=d.id
                   WHERE d.project_id IN (SELECT id FROM projects WHERE user_id=?)
                   ORDER BY ef.created_at DESC LIMIT ?""",
                (user["id"], limit),
            ).fetchall()
    return [dict(r) for r in rows]



@router.get("/relationships")
def list_relationships(
    relationship_type: str | None = Query(None),
    project_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    include_noise: bool = Query(False),
    user: dict = Depends(get_current_user),
):
    conditions = [
        "r.source_fact_id IN (SELECT f.id FROM facts f JOIN documents d ON f.document_id=d.id WHERE d.project_id IN (SELECT id FROM projects WHERE user_id=?))"
    ]
    params: list = [user["id"]]

    if project_id:
        conditions.append("r.source_fact_id IN (SELECT f.id FROM facts f JOIN documents d ON f.document_id=d.id WHERE d.project_id=?)")
        params.append(project_id)
    if relationship_type:
        conditions.append("r.relationship_type = ?")
        params.append(relationship_type)
    if not include_noise:
        # Exclude relationships where either fact has a noise attribute or null canonical value
        conditions.append(
            "r.source_fact_id IN (SELECT id FROM facts WHERE attribute NOT IN ('Metric','Description') AND canonical_value IS NOT NULL)"
        )
        conditions.append(
            "r.target_fact_id IN (SELECT id FROM facts WHERE attribute NOT IN ('Metric','Description') AND canonical_value IS NOT NULL)"
        )

    params += [limit, offset]
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT r.* FROM relationships r WHERE {' AND '.join(conditions)}
                ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
    return [_enrich_relationship(dict(r)) for r in rows]


@router.get("/relationships/summary")
def relationships_summary(project_id: str | None = Query(None), user: dict = Depends(get_current_user)):
    user_filter = "r.source_fact_id IN (SELECT f.id FROM facts f JOIN documents d ON f.document_id=d.id WHERE d.project_id IN (SELECT id FROM projects WHERE user_id=?))"
    noise_filter = "r.source_fact_id IN (SELECT id FROM facts WHERE attribute NOT IN ('Metric','Description') AND canonical_value IS NOT NULL) AND r.target_fact_id IN (SELECT id FROM facts WHERE attribute NOT IN ('Metric','Description') AND canonical_value IS NOT NULL)"
    with get_db() as conn:
        if project_id:
            rows = conn.execute(
                f"""SELECT r.relationship_type, COUNT(*) as count FROM relationships r
                   JOIN facts f ON r.source_fact_id=f.id JOIN documents d ON f.document_id=d.id
                   WHERE d.project_id=? AND {user_filter} AND {noise_filter}
                   GROUP BY r.relationship_type""",
                (project_id, user["id"]),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT r.relationship_type, COUNT(*) as count FROM relationships r
                   WHERE {user_filter} AND {noise_filter} GROUP BY r.relationship_type""",
                (user["id"],),
            ).fetchall()
    return {r["relationship_type"]: r["count"] for r in rows}


@router.get("/relationships/{rel_id}")
def get_relationship(rel_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM relationships WHERE id=?", (rel_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return _enrich_relationship(dict(row))


@router.post("/documents/{doc_id}/analyze")
def trigger_analysis(doc_id: str, background_tasks: BackgroundTasks, reset: bool = False):
    """Manually trigger relationship analysis. Pass ?reset=true to re-run from scratch."""
    with get_db() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if reset:
        from services.incremental_indexer import reset_analysis_for_document
        deleted = reset_analysis_for_document(doc_id)
        log.info("Reset %d relationships for document %s before re-analysis", deleted, doc_id)

    background_tasks.add_task(analyze_document_relationships, doc_id)
    log.info("Relationship analysis triggered for document %s (reset=%s)", doc_id, reset)
    return {"message": "Relationship analysis started", "document_id": doc_id}


@router.get("/facts/{fact_id}/relationships")
def get_fact_relationships(fact_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        # Verify fact belongs to user
        fact = conn.execute(
            "SELECT f.id FROM facts f JOIN documents d ON f.document_id=d.id WHERE f.id=? AND d.project_id IN (SELECT id FROM projects WHERE user_id=?)",
            (fact_id, user["id"]),
        ).fetchone()
        if not fact:
            raise HTTPException(status_code=404, detail="Fact not found")
        rows = conn.execute(
            """SELECT * FROM relationships
               WHERE source_fact_id=? OR target_fact_id=?
               ORDER BY confidence DESC""",
            (fact_id, fact_id),
        ).fetchall()
    return [_enrich_relationship(dict(r)) for r in rows]
