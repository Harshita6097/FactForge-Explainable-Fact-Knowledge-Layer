import re
from typing import Optional
from database.db import get_db
from utils.logger import get_logger

log = get_logger("timeline_service")

# ---------------------------------------------------------------------------
# Period → sortable integer key
# ---------------------------------------------------------------------------

_FY_RE = re.compile(r"FY(\d{4})", re.IGNORECASE)
_Q_RE = re.compile(r"Q([1-4])\s*FY(\d{4})", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(19|20)(\d{2})$")


def _period_sort_key(period: Optional[str]) -> int:
    """
    Convert a canonical period string to a sortable integer.
    FY2024       → 20240000
    Q3 FY2024    → 20240300
    2024         → 20240000
    None / other → 99999999  (pushed to end)
    """
    if not period:
        return 99_999_999

    m = _Q_RE.search(period)
    if m:
        return int(m.group(2)) * 10_000 + int(m.group(1)) * 100

    m = _FY_RE.search(period)
    if m:
        return int(m.group(1)) * 10_000

    m = _YEAR_RE.match(period.strip())
    if m:
        return int(period.strip()) * 10_000

    return 99_999_999


def _period_label(period: Optional[str]) -> str:
    if not period:
        return "Undated"
    return period


def _period_type(period: Optional[str]) -> str:
    if not period:
        return "unknown"
    if _Q_RE.search(period):
        return "quarter"
    if _FY_RE.search(period):
        return "fiscal_year"
    if _YEAR_RE.match(period.strip() if period else ""):
        return "calendar_year"
    return "other"


# ---------------------------------------------------------------------------
# Build timeline
# ---------------------------------------------------------------------------

def build_timeline(
    entity: Optional[str] = None,
    attribute: Optional[str] = None,
) -> list[dict]:
    """
    Returns a list of timeline entries sorted chronologically.
    Each entry groups all facts for a given period.
    """
    conditions = ["f.period IS NOT NULL"]
    params: list = []

    if entity:
        conditions.append("LOWER(f.entity) LIKE ?")
        params.append(f"%{entity.lower()}%")
    if attribute:
        conditions.append("LOWER(f.attribute) LIKE ?")
        params.append(f"%{attribute.lower()}%")

    where = "WHERE " + " AND ".join(conditions)

    with get_db() as conn:
        facts = conn.execute(
            f"""SELECT f.id, f.entity, f.attribute, f.canonical_value, f.raw_value,
                       f.unit, f.period, f.confidence, f.document_id,
                       d.original_filename,
                       e.page_number, e.snippet
                FROM facts f
                JOIN documents d ON f.document_id = d.id
                LEFT JOIN evidence e ON e.fact_id = f.id
                {where}
                ORDER BY f.period, f.entity, f.attribute""",
            params,
        ).fetchall()

        # Fetch relationship markers for these facts
        rel_map: dict[str, list[str]] = {}
        all_fact_ids = [f["id"] for f in facts]
        if all_fact_ids:
            placeholders = ",".join("?" * len(all_fact_ids))
            rels = conn.execute(
                f"""SELECT source_fact_id, target_fact_id, relationship_type
                    FROM relationships
                    WHERE source_fact_id IN ({placeholders})
                       OR target_fact_id IN ({placeholders})""",
                all_fact_ids + all_fact_ids,
            ).fetchall()
            for r in rels:
                for fid in [r["source_fact_id"], r["target_fact_id"]]:
                    rel_map.setdefault(fid, [])
                    if r["relationship_type"] not in rel_map[fid]:
                        rel_map[fid].append(r["relationship_type"])

    # Group by period
    period_groups: dict[str, list[dict]] = {}
    for f in facts:
        period = f["period"] or "Undated"
        period_groups.setdefault(period, [])
        period_groups[period].append({
            "id": f["id"],
            "entity": f["entity"],
            "attribute": f["attribute"],
            "canonical_value": f["canonical_value"],
            "raw_value": f["raw_value"],
            "unit": f["unit"],
            "confidence": f["confidence"],
            "document": f["original_filename"],
            "page_number": f["page_number"],
            "snippet": f["snippet"],
            "relationships": rel_map.get(f["id"], []),
        })

    # Build sorted timeline entries
    entries = []
    for period, period_facts in period_groups.items():
        # Collect relationship types present in this period
        all_rel_types = set()
        for pf in period_facts:
            all_rel_types.update(pf["relationships"])

        entries.append({
            "period": _period_label(period),
            "period_type": _period_type(period),
            "sort_key": _period_sort_key(period),
            "fact_count": len(period_facts),
            "has_contradiction": "contradiction" in all_rel_types,
            "has_corroboration": "corroborated" in all_rel_types,
            "has_reconciled": "reconciled" in all_rel_types,
            "facts": period_facts,
        })

    entries.sort(key=lambda e: e["sort_key"])

    log.info(
        "Timeline built | periods=%d | total_facts=%d | entity=%s | attribute=%s",
        len(entries), len(facts), entity or "*", attribute or "*",
    )
    return entries
