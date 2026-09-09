import uuid
from datetime import datetime, timezone
from typing import Optional

from database.db import get_db
from models.fact import RawExtractedFact
from services.rule_extractor import extract_facts_from_pages
from services.canonicalizer import canonicalize_fact, register_attribute
from services.incremental_indexer import (
    get_existing_fact_fingerprints,
    is_fact_duplicate,
    compute_optimal_batch_size,
)
from services.relationship_engine import log_extraction_failure
from services.document_processor import extract_primary_entity
from utils.logger import get_logger

log = get_logger("fact_miner")


def _deduplicate_batch(facts: list[RawExtractedFact]) -> list[RawExtractedFact]:
    """
    Within a single extraction batch, group facts that share the same
    (entity, canonical_attribute, canonical_period) and keep only the
    highest-confidence representative.

    Also drops facts whose canonical_value resolved to None (bibliographic
    artifacts rejected by the canonicalizer).
    """
    from services.canonicalizer import canonicalize_fact as _cf

    best: dict[tuple, RawExtractedFact] = {}
    for fact in facts:
        try:
            canon = _cf(fact.entity, fact.attribute, fact.raw_value, fact.unit, fact.period)
        except Exception:
            continue

        # Drop facts where the value couldn't be resolved
        if canon["canonical_value"] is None:
            log.debug("Post-process drop (no canonical value): %s.%s = %s",
                      fact.entity, fact.attribute, fact.raw_value)
            # Log as extraction failure so it appears in the Failures tab
            try:
                from services.relationship_engine import log_extraction_failure as _lef
                # document_id not available here — logged at mine_facts_for_document level
            except Exception:
                pass
            continue

        key = (
            fact.entity.strip().lower(),
            canon["canonical_attribute"].lower(),
            (canon["canonical_period"] or "").lower(),
        )
        existing = best.get(key)
        if existing is None or fact.confidence > existing.confidence:
            best[key] = fact

    deduped = list(best.values())
    log.debug("Batch dedup: %d → %d facts", len(facts), len(deduped))
    return deduped

def _parse_facts(raw: list, default_page: Optional[int] = None) -> list[RawExtractedFact]:
    facts = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            if "page_number" not in item or item["page_number"] is None:
                item["page_number"] = default_page
            facts.append(RawExtractedFact(**item))
        except Exception as e:
            log.warning("Skipping malformed fact item: %s | error: %s", item, e)
    return facts


def _store_fact_with_evidence(
    fact: RawExtractedFact,
    document_id: str,
    page_number: int,
) -> str:
    canon = canonicalize_fact(
        entity=fact.entity,
        attribute=fact.attribute,
        raw_value=fact.raw_value,
        unit=fact.unit,
        period=fact.period,
    )

    # Register attribute for dynamic schema discovery
    register_attribute(fact.attribute)

    fact_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO facts
               (id, document_id, entity, attribute, canonical_value, raw_value, unit, period, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact_id,
                document_id,
                fact.entity.strip(),
                canon["canonical_attribute"],
                canon["canonical_value"],
                fact.raw_value.strip(),
                canon["canonical_unit"],
                canon["canonical_period"],
                round(fact.confidence, 3),
                now,
            ),
        )
        conn.execute(
            """INSERT INTO evidence (id, fact_id, document_id, page_number, snippet)
               VALUES (?, ?, ?, ?, ?)""",
            (evidence_id, fact_id, document_id, page_number, fact.snippet.strip()),
        )

    log.debug(
        "Stored fact | entity=%s | attr=%s | value=%s | page=%d",
        fact.entity, canon["canonical_attribute"], canon["canonical_value"], page_number,
    )
    return fact_id


def mine_facts_for_document(document_id: str, filename: str) -> int:
    """
    Extract facts from all unprocessed pages of a document.
    - Uses dynamic batch sizing based on page density.
    - Skips duplicate facts within the same document.
    - Only processes pages not yet marked processed=1 (incremental).
    Returns total facts stored.
    """
    with get_db() as conn:
        pages = conn.execute(
            """SELECT page_number, text, char_count FROM document_pages
               WHERE document_id=? AND processed=0
               ORDER BY page_number""",
            (document_id,),
        ).fetchall()

    if not pages:
        log.info("No unprocessed pages for document %s", document_id)
        return 0

    pages = [dict(p) for p in pages]
    total_pages = len(pages)
    total_facts = 0

    # Extract primary entity hint from the uploaded PDF file
    from utils.config import get_settings
    from pathlib import Path
    settings = get_settings()
    with get_db() as conn:
        doc_row = conn.execute(
            "SELECT filename FROM documents WHERE id=?", (document_id,)
        ).fetchone()
    file_path = str(Path(settings.upload_dir) / doc_row["filename"]) if doc_row else None
    doc_entity_hint = extract_primary_entity(file_path) if file_path else None
    if doc_entity_hint:
        log.info("Entity hint for doc %s: '%s'", document_id[:8], doc_entity_hint)

    # Dynamic batch size based on page density
    batch_size = compute_optimal_batch_size(pages)
    total_batches = (total_pages + batch_size - 1) // batch_size

    log.info(
        "Starting fact mining | doc=%s | pages=%d | batch_size=%d | batches=%d",
        filename, total_pages, batch_size, total_batches,
    )

    # Load existing fingerprints for deduplication
    existing_fingerprints = get_existing_fact_fingerprints(document_id)

    for i in range(0, total_pages, batch_size):
        batch = pages[i: i + batch_size]
        page_range = f"{batch[0]['page_number']}-{batch[-1]['page_number']}"
        log.info("Processing batch pages %s of %s", page_range, filename)

        first_page = batch[0]["page_number"]
        try:
            raw_list = extract_facts_from_pages(batch, doc_entity_hint)
        except Exception as e:
            log.error("Rule extraction failed for pages %s: %s", page_range, e)
            raw_list = []

        facts = _parse_facts(raw_list, default_page=first_page)
        facts = _deduplicate_batch(facts)
        log.info("Extracted %d facts from pages %s (after dedup)", len(facts), page_range)

        for fact in facts:
            page_num = fact.page_number or first_page
            try:
                canon = canonicalize_fact(fact.entity, fact.attribute, fact.raw_value, fact.unit, fact.period)

                # Skip facts with no resolvable value (already filtered by dedup, belt-and-suspenders)
                if canon["canonical_value"] is None:
                    log_extraction_failure(
                        document_id=document_id,
                        page_number=page_num,
                        raw_text=fact.raw_value,
                        failure_reason="canonical_value_none",
                        chain_of_thought=(
                            f"Entity='{fact.entity}' Attribute='{fact.attribute}' "
                            f"RawValue='{fact.raw_value}' Unit='{fact.unit}' — "
                            f"normalize_value returned None (bibliographic artifact or unparseable number)."
                        ),
                        confidence=fact.confidence,
                    )
                    continue

                # Log low-confidence facts before storing
                if fact.confidence < 0.72:
                    log_extraction_failure(
                        document_id=document_id,
                        page_number=page_num,
                        raw_text=fact.snippet,
                        failure_reason="low_confidence",
                        chain_of_thought=(
                            f"Entity='{fact.entity}' Attribute='{fact.attribute}' "
                            f"Value='{fact.raw_value}' Confidence={fact.confidence:.2f} — "
                            f"below threshold 0.72; fact stored but flagged for review."
                        ),
                        confidence=fact.confidence,
                    )
                if is_fact_duplicate(
                    fact.entity, canon["canonical_attribute"],
                    canon["canonical_value"], canon["canonical_period"],
                    existing_fingerprints,
                ):
                    log.debug("Skipping duplicate fact: %s.%s", fact.entity, fact.attribute)
                    continue

                _store_fact_with_evidence(fact, document_id, page_num)
                # Add to fingerprints so subsequent batches don't re-add
                fp = f"{fact.entity}|{canon['canonical_attribute']}|{canon['canonical_value']}|{canon['canonical_period']}"
                existing_fingerprints.add(fp)
                total_facts += 1
            except Exception as e:
                log.error("Failed to store fact '%s.%s': %s", fact.entity, fact.attribute, e)

        page_numbers = [p["page_number"] for p in batch]
        with get_db() as conn:
            conn.execute(
                f"""UPDATE document_pages SET processed=1
                    WHERE document_id=? AND page_number IN ({','.join('?' * len(page_numbers))})""",
                [document_id] + page_numbers,
            )

    log.info("Fact mining complete | doc=%s | total_facts=%d", filename, total_facts)
    return total_facts


def get_facts_for_document(document_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE document_id=? ORDER BY entity, attribute",
            (document_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_fact_with_evidence(fact_id: str) -> Optional[dict]:
    with get_db() as conn:
        fact = conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        if not fact:
            return None
        evidence = conn.execute(
            """SELECT e.*, d.original_filename as document_name
               FROM evidence e
               JOIN documents d ON e.document_id = d.id
               WHERE e.fact_id=?""",
            (fact_id,),
        ).fetchall()
    return {**dict(fact), "evidence": [dict(e) for e in evidence]}
