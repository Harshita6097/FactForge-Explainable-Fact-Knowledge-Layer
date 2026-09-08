"""
Knowledge Layer Manager
-----------------------
Merges raw extracted facts into canonical facts — first-class objects
with aggregated evidence, confidence, and cross-document support counts.

Raw facts are never modified. Canonical facts are derived views that
become the primary user-facing objects.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from database.db import get_db
from services.canonicalizer import canonicalize_attribute
from utils.logger import get_logger

log = get_logger("knowledge_layer")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(canonical_entity: str, canonical_attribute: str, period: Optional[str]) -> str:
    """Canonical fact identity key — entity + attribute + period."""
    return f"{canonical_entity.lower().strip()}|{canonical_attribute.lower().strip()}|{(period or '').lower().strip()}"


def resolve_entity(raw_entity: str) -> str:
    """
    Look up canonical entity name from alias table.
    Falls back to title-cased raw name if no alias found.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT canonical_name FROM entity_aliases WHERE LOWER(raw_name)=LOWER(?)",
            (raw_entity.strip(),),
        ).fetchone()
    if row:
        return row["canonical_name"]
    return raw_entity.strip()


def register_entity_alias(raw_name: str, canonical_name: str, confidence: float = 1.0):
    """Store an entity alias mapping."""
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO entity_aliases (raw_name, canonical_name, confidence, created_at)
               VALUES (?, ?, ?, ?)""",
            (raw_name.strip(), canonical_name.strip(), confidence, _now()),
        )


def upsert_canonical_fact(
    raw_fact_id: str,
    entity: str,
    canonical_attribute: str,
    canonical_value: Optional[str],
    canonical_unit: Optional[str],
    period: Optional[str],
    confidence: float,
    is_conflicting: bool = False,
) -> str:
    """
    Insert or update a canonical fact.
    - If a canonical fact with same entity+attribute+period exists: merge it.
    - Merging: add source_fact_id, update confidence (max), increment support/conflict count.
    - Returns canonical_fact_id.
    """
    canonical_entity = resolve_entity(entity)
    fp = _fingerprint(canonical_entity, canonical_attribute, period)

    with get_db() as conn:
        # Find existing canonical fact by fingerprint
        existing = conn.execute(
            """SELECT id, source_fact_ids, confidence, supporting_count, conflicting_count
               FROM canonical_facts
               WHERE LOWER(canonical_entity)=LOWER(?) AND LOWER(canonical_attribute)=LOWER(?)
               AND (period=? OR (period IS NULL AND ? IS NULL))""",
            (canonical_entity, canonical_attribute, period, period),
        ).fetchone()

        if existing:
            cf_id = existing["id"]
            source_ids = json.loads(existing["source_fact_ids"])
            if raw_fact_id not in source_ids:
                source_ids.append(raw_fact_id)
            new_confidence = max(existing["confidence"], confidence)
            new_support = existing["supporting_count"] + (0 if is_conflicting else 1)
            new_conflict = existing["conflicting_count"] + (1 if is_conflicting else 0)

            conn.execute(
                """UPDATE canonical_facts
                   SET source_fact_ids=?, confidence=?, supporting_count=?,
                       conflicting_count=?, updated_at=?
                   WHERE id=?""",
                (json.dumps(source_ids), new_confidence, new_support,
                 new_conflict, _now(), cf_id),
            )
            log.debug("Merged into canonical fact %s | entity=%s | attr=%s", cf_id[:8], canonical_entity, canonical_attribute)
            return cf_id
        else:
            cf_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO canonical_facts
                   (id, entity, canonical_entity, attribute, canonical_attribute,
                    canonical_value, canonical_unit, period, confidence,
                    supporting_count, conflicting_count, source_fact_ids, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cf_id, entity, canonical_entity,
                    canonical_attribute, canonical_attribute,
                    canonical_value, canonical_unit, period,
                    confidence, 1, 0,
                    json.dumps([raw_fact_id]),
                    _now(), _now(),
                ),
            )
            log.debug("Created canonical fact %s | entity=%s | attr=%s", cf_id[:8], canonical_entity, canonical_attribute)
            return cf_id


def build_canonical_facts_for_document(document_id: str) -> int:
    """
    Process all facts from a document into the canonical facts layer.
    Called after fact mining completes.
    Returns count of canonical facts created or updated.
    """
    with get_db() as conn:
        facts = conn.execute(
            """SELECT id, entity, attribute, canonical_value, canonical_unit,
                      period, confidence
               FROM facts WHERE document_id=?""",
            (document_id,),
        ).fetchall()

    count = 0
    for f in facts:
        try:
            upsert_canonical_fact(
                raw_fact_id=f["id"],
                entity=f["entity"],
                canonical_attribute=f["attribute"],
                canonical_value=f["canonical_value"],
                canonical_unit=f["canonical_unit"],
                period=f["period"],
                confidence=f["confidence"],
            )
            count += 1
        except Exception as e:
            log.warning("Failed to upsert canonical fact for raw %s: %s", f["id"], e)

    # After merging, update conflicting_count based on relationships
    _refresh_conflict_counts()

    log.info("Canonical facts built | doc=%s | processed=%d", document_id, count)
    return count


def _refresh_conflict_counts():
    """Update conflicting_count on canonical facts based on contradiction relationships."""
    with get_db() as conn:
        contradictions = conn.execute(
            """SELECT r.source_fact_id, r.target_fact_id
               FROM relationships r
               WHERE r.relationship_type='contradiction'"""
        ).fetchall()

        for rel in contradictions:
            for fact_id in [rel["source_fact_id"], rel["target_fact_id"]]:
                # Find which canonical fact this raw fact belongs to
                cf = conn.execute(
                    """SELECT id, conflicting_count FROM canonical_facts
                       WHERE source_fact_ids LIKE ?""",
                    (f'%"{fact_id}"%',),
                ).fetchone()
                if cf:
                    conn.execute(
                        "UPDATE canonical_facts SET conflicting_count=conflicting_count+1 WHERE id=? AND conflicting_count=0",
                        (cf["id"],),
                    )


def get_canonical_facts(
    entity: Optional[str] = None,
    attribute: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    conditions = []
    params: list = []

    if entity:
        conditions.append("LOWER(cf.canonical_entity) LIKE ?")
        params.append(f"%{entity.lower()}%")
    if attribute:
        conditions.append("LOWER(cf.canonical_attribute) LIKE ?")
        params.append(f"%{attribute.lower()}%")
    if period:
        conditions.append("cf.period=?")
        params.append(period)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT cf.*,
                       (SELECT COUNT(*) FROM relationships r
                        JOIN facts f ON r.source_fact_id=f.id OR r.target_fact_id=f.id
                        WHERE f.id IN (SELECT value FROM json_each(cf.source_fact_ids))
                        AND r.relationship_type='corroborated') as corroboration_count
                FROM canonical_facts cf
                {where}
                ORDER BY cf.confidence DESC, cf.supporting_count DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["source_fact_ids"] = json.loads(d["source_fact_ids"] or "[]")
        result.append(d)
    return result


def get_canonical_fact(cf_id: str) -> Optional[dict]:
    """Get a single canonical fact with all its raw facts and evidence."""
    with get_db() as conn:
        cf = conn.execute(
            "SELECT * FROM canonical_facts WHERE id=?", (cf_id,)
        ).fetchone()
        if not cf:
            return None

        cf_dict = dict(cf)
        source_ids = json.loads(cf_dict["source_fact_ids"] or "[]")

        # Fetch all raw facts with evidence
        raw_facts = []
        for fid in source_ids:
            fact = conn.execute("SELECT * FROM facts WHERE id=?", (fid,)).fetchone()
            if not fact:
                continue
            evidence = conn.execute(
                """SELECT e.*, d.original_filename as document_name
                   FROM evidence e JOIN documents d ON e.document_id=d.id
                   WHERE e.fact_id=?""",
                (fid,),
            ).fetchall()
            raw_facts.append({
                **dict(fact),
                "evidence": [dict(e) for e in evidence],
            })

        # Fetch relationships involving any of these raw facts
        relationships = []
        if source_ids:
            placeholders = ",".join("?" * len(source_ids))
            rels = conn.execute(
                f"""SELECT r.*, fa.entity as src_entity, fa.attribute as src_attr,
                           fa.canonical_value as src_value, fa.period as src_period,
                           fb.entity as tgt_entity, fb.attribute as tgt_attr,
                           fb.canonical_value as tgt_value, fb.period as tgt_period,
                           da.original_filename as src_doc, db.original_filename as tgt_doc
                    FROM relationships r
                    JOIN facts fa ON r.source_fact_id=fa.id
                    JOIN facts fb ON r.target_fact_id=fb.id
                    JOIN documents da ON fa.document_id=da.id
                    JOIN documents db ON fb.document_id=db.id
                    WHERE r.source_fact_id IN ({placeholders})
                       OR r.target_fact_id IN ({placeholders})""",
                source_ids + source_ids,
            ).fetchall()
            relationships = [dict(r) for r in rels]

    cf_dict["source_fact_ids"] = source_ids
    cf_dict["raw_facts"] = raw_facts
    cf_dict["relationships"] = relationships
    return cf_dict


def get_knowledge_stats() -> dict:
    with get_db() as conn:
        total_canonical = conn.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
        multi_doc = conn.execute(
            "SELECT COUNT(*) FROM canonical_facts WHERE supporting_count > 1"
        ).fetchone()[0]
        conflicted = conn.execute(
            "SELECT COUNT(*) FROM canonical_facts WHERE conflicting_count > 0"
        ).fetchone()[0]
        entities = conn.execute(
            "SELECT COUNT(DISTINCT canonical_entity) FROM canonical_facts"
        ).fetchone()[0]
        attributes = conn.execute(
            "SELECT COUNT(DISTINCT canonical_attribute) FROM canonical_facts"
        ).fetchone()[0]

    return {
        "canonical_facts": total_canonical,
        "multi_document_facts": multi_doc,
        "conflicted_facts": conflicted,
        "unique_entities": entities,
        "unique_attributes": attributes,
    }
