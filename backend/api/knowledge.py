from fastapi import APIRouter, HTTPException, Query
from services.knowledge_layer import (
    get_canonical_facts,
    get_canonical_fact,
    get_knowledge_stats,
    build_canonical_facts_for_document,
)
from database.db import get_db
from utils.logger import get_logger

log = get_logger("knowledge_api")
router = APIRouter()


@router.get("/knowledge/stats")
def knowledge_stats():
    """Dashboard stats for the canonical knowledge layer."""
    return get_knowledge_stats()


@router.get("/knowledge/facts")
def list_canonical_facts(
    entity: str | None = Query(None),
    attribute: str | None = Query(None),
    period: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """List canonical facts — the primary user-facing knowledge objects."""
    return get_canonical_facts(entity=entity, attribute=attribute, period=period,
                               limit=limit, offset=offset)


@router.get("/knowledge/facts/{cf_id}")
def get_canonical_fact_detail(cf_id: str):
    """Get a canonical fact with all raw facts, evidence, and relationships."""
    cf = get_canonical_fact(cf_id)
    if not cf:
        raise HTTPException(status_code=404, detail="Canonical fact not found")
    return cf


@router.post("/knowledge/rebuild")
def rebuild_knowledge_layer():
    """Rebuild the entire canonical facts layer from all completed documents."""
    with get_db() as conn:
        docs = conn.execute(
            "SELECT id FROM documents WHERE status='completed'"
        ).fetchall()

    total = 0
    for doc in docs:
        total += build_canonical_facts_for_document(doc["id"])

    log.info("Knowledge layer rebuilt | canonical_facts=%d", total)
    return {"rebuilt": total}


@router.get("/knowledge/entities")
def list_entities():
    """List all unique canonical entities with fact counts."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT canonical_entity as entity,
                      COUNT(*) as fact_count,
                      AVG(confidence) as avg_confidence,
                      COUNT(DISTINCT period) as period_count
               FROM canonical_facts
               GROUP BY canonical_entity
               ORDER BY fact_count DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/knowledge/entities/{entity}/facts")
def get_entity_facts(entity: str):
    """Get all canonical facts for a specific entity."""
    facts = get_canonical_facts(entity=entity, limit=500)
    if not facts:
        raise HTTPException(status_code=404, detail="No facts found for this entity")
    return facts
