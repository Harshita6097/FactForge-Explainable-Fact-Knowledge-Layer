from fastapi import APIRouter, Query, Depends
from services.timeline_service import build_timeline
from utils.auth import get_current_user
from utils.logger import get_logger

log = get_logger("timeline_api")
router = APIRouter()


@router.get("/timeline")
def get_timeline(
    entity: str | None = Query(None),
    attribute: str | None = Query(None),
    project_id: str | None = Query(None),
    document_id: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    # If no explicit scope, default to the user's own facts only
    from database.db import get_db
    resolved_project_id = project_id
    if not document_id and not project_id:
        # Scope to all projects owned by this user
        with get_db() as conn:
            user_project_ids = [
                r[0] for r in conn.execute(
                    "SELECT id FROM projects WHERE user_id=?", (user["id"],)
                ).fetchall()
            ]
        # Pass as a synthetic filter — handled below
        entries = _build_user_timeline(entity, attribute, user_project_ids)
        return {
            "total_periods": len(entries),
            "total_facts": sum(e["fact_count"] for e in entries),
            "entries": entries,
        }

    entries = build_timeline(
        entity=entity, attribute=attribute,
        project_id=resolved_project_id, document_id=document_id,
    )
    return {
        "total_periods": len(entries),
        "total_facts": sum(e["fact_count"] for e in entries),
        "entries": entries,
    }


def _build_user_timeline(entity, attribute, project_ids: list[str]) -> list[dict]:
    """Build timeline scoped to a list of project IDs (all user's projects)."""
    if not project_ids:
        return []
    from services.timeline_service import build_timeline as _bt
    all_entries: dict[str, dict] = {}
    for pid in project_ids:
        for entry in _bt(entity=entity, attribute=attribute, project_id=pid):
            period = entry["period"]
            if period not in all_entries:
                all_entries[period] = entry
            else:
                # Merge facts from same period across projects
                all_entries[period]["facts"].extend(entry["facts"])
                all_entries[period]["fact_count"] += entry["fact_count"]
                all_entries[period]["has_contradiction"] |= entry["has_contradiction"]
                all_entries[period]["has_corroboration"] |= entry["has_corroboration"]
                all_entries[period]["has_reconciled"] |= entry["has_reconciled"]
    result = sorted(all_entries.values(), key=lambda e: e["sort_key"])
    return result
