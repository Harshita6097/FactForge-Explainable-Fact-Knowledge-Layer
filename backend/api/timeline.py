from fastapi import APIRouter, Query
from services.timeline_service import build_timeline
from utils.logger import get_logger

log = get_logger("timeline_api")
router = APIRouter()


@router.get("/timeline")
def get_timeline(
    entity: str | None = Query(None, description="Filter by entity name"),
    attribute: str | None = Query(None, description="Filter by attribute name"),
):
    """
    Returns all facts grouped by period and sorted chronologically.
    Includes relationship markers (contradiction, corroboration, reconciled) per period.
    """
    entries = build_timeline(entity=entity, attribute=attribute)
    return {
        "total_periods": len(entries),
        "total_facts": sum(e["fact_count"] for e in entries),
        "entries": entries,
    }
