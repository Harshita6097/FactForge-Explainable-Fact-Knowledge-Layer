import uuid
import re
import json
from datetime import datetime, timezone
from typing import Optional

from database.db import get_db
from prompts.relationship_prompts import RELATIONSHIP_EXPLANATION_PROMPT
from services.gemini_client import generate_text, get_embedding
from services.vector_store import add_fact_embedding, search_similar
from services.incremental_indexer import get_new_facts_since_last_analysis
from utils.logger import get_logger

log = get_logger("relationship_engine")

# Tolerance for numeric comparison — metric-aware, configurable per attribute
_DEFAULT_TOLERANCE = 0.05

# Per-attribute tolerance rules (canonical attribute name → tolerance fraction)
_ATTRIBUTE_TOLERANCES: dict[str, float] = {
    "revenue": 0.05,
    "net income": 0.05,
    "ebitda": 0.05,
    "pbt": 0.05,
    "market cap": 0.05,
    "gdp growth rate": 0.002,   # 0.2% — macroeconomic figures are precise
    "inflation": 0.001,          # 0.1%
    "repo rate": 0.001,
    "employees": 0.0,            # exact match for headcount
    "page count": 0.0,
    "warehouses": 0.0,
    "fulfillment centers": 0.0,
}


def _get_tolerance(attribute: str) -> float:
    """Return the appropriate numeric tolerance for a given attribute."""
    key = attribute.lower().strip()
    for attr_key, tol in _ATTRIBUTE_TOLERANCES.items():
        if attr_key in key or key in attr_key:
            return tol
    return _DEFAULT_TOLERANCE

# Minimum FAISS similarity to consider facts related
_SIMILARITY_THRESHOLD = 0.82


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    clean = re.sub(r"[,\s]", "", value)
    m = re.search(r"-?\d+\.?\d*", clean)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def _periods_differ(p1: Optional[str], p2: Optional[str]) -> bool:
    if not p1 or not p2:
        return False
    return p1.strip().upper() != p2.strip().upper()


def _entities_match(e1: str, e2: str) -> bool:
    return e1.strip().lower() == e2.strip().lower()


def _attributes_match(a1: str, a2: str) -> bool:
    return a1.strip().lower() == a2.strip().lower()


def _numeric_conflict(v1: Optional[str], v2: Optional[str], attribute: str = "") -> bool:
    """True if both are numbers and they differ beyond attribute-specific tolerance."""
    n1, n2 = _extract_number(v1), _extract_number(v2)
    if n1 is None or n2 is None:
        return False
    if n1 == 0 and n2 == 0:
        return False
    tol = _get_tolerance(attribute)
    denom = max(abs(n1), abs(n2))
    return abs(n1 - n2) / denom > tol


def _numeric_match(v1: Optional[str], v2: Optional[str], attribute: str = "") -> bool:
    """True if both are numbers and they are within attribute-specific tolerance."""
    n1, n2 = _extract_number(v1), _extract_number(v2)
    if n1 is None or n2 is None:
        return v1 and v2 and v1.strip().lower() == v2.strip().lower()
    if n1 == 0 and n2 == 0:
        return True
    tol = _get_tolerance(attribute)
    denom = max(abs(n1), abs(n2))
    return abs(n1 - n2) / denom <= tol


# ---------------------------------------------------------------------------
# Relationship detection — fully deterministic, no LLM
# ---------------------------------------------------------------------------

def _detect_relationship(fact_a: dict, fact_b: dict) -> Optional[tuple[str, float, list]]:
    """
    Returns (relationship_type, confidence, reasoning_steps) or None if unrelated.
    """
    same_entity = _entities_match(fact_a["entity"], fact_b["entity"])
    same_attr = _attributes_match(fact_a["attribute"], fact_b["attribute"])
    periods_differ = _periods_differ(fact_a["period"], fact_b["period"])

    val_a = fact_a.get("canonical_value") or fact_a.get("raw_value")
    val_b = fact_b.get("canonical_value") or fact_b.get("raw_value")

    rel_type = None
    confidence = 0.0

    if same_entity and same_attr:
        if _numeric_match(val_a, val_b, fact_a.get("attribute", "")):
            rel_type, confidence = "corroborated", 0.95
        elif _numeric_conflict(val_a, val_b, fact_a.get("attribute", "")):
            if periods_differ:
                rel_type, confidence = "reconciled", 0.88
            else:
                rel_type, confidence = "contradiction", 0.90
        else:
            if periods_differ:
                rel_type, confidence = "reconciled", 0.80
            else:
                rel_type, confidence = "contradiction", 0.75
    elif same_attr and not same_entity:
        rel_type, confidence = "related", 0.60

    if rel_type is None:
        return None

    steps = _build_reasoning_steps(
        fact_a, fact_b, rel_type, same_entity, same_attr,
        periods_differ, val_a, val_b,
    )
    return (rel_type, confidence, steps)


# ---------------------------------------------------------------------------
# Evidence fetcher
# ---------------------------------------------------------------------------

def _get_fact_with_evidence(fact_id: str, conn) -> Optional[dict]:
    fact = conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
    if not fact:
        return None
    ev = conn.execute(
        """SELECT e.page_number, e.snippet, d.original_filename
           FROM evidence e JOIN documents d ON e.document_id=d.id
           WHERE e.fact_id=? LIMIT 1""",
        (fact_id,),
    ).fetchone()
    return {**dict(fact), "evidence": dict(ev) if ev else {}}


# ---------------------------------------------------------------------------
# Explanation via Gemini — only called after relationship is detected
# ---------------------------------------------------------------------------

def _build_reasoning_steps(
    fact_a: dict, fact_b: dict, rel_type: str,
    same_entity: bool, same_attr: bool, periods_differ: bool,
    val_a: Optional[str], val_b: Optional[str],
) -> list[dict]:
    """Build a deterministic step-by-step reasoning chain for a relationship."""
    steps = []
    step = 1

    # Entity check
    if same_entity:
        steps.append({"step": step, "check": "Entity Match",
                      "result": "match",
                      "detail": f"Both facts refer to '{fact_a['entity']}'."})
    else:
        steps.append({"step": step, "check": "Entity Match",
                      "result": "different",
                      "detail": f"'{fact_a['entity']}' vs '{fact_b['entity']}' — different entities."})
    step += 1

    # Attribute check
    if same_attr:
        steps.append({"step": step, "check": "Attribute Match",
                      "result": "match",
                      "detail": f"Both measure '{fact_a['attribute']}'."})
    else:
        steps.append({"step": step, "check": "Attribute Match",
                      "result": "different",
                      "detail": f"'{fact_a['attribute']}' vs '{fact_b['attribute']}' — semantically related attributes."})
    step += 1

    # Period check
    p_a = fact_a.get("period") or "N/A"
    p_b = fact_b.get("period") or "N/A"
    if periods_differ:
        steps.append({"step": step, "check": "Period Comparison",
                      "result": "different",
                      "detail": f"Reporting periods differ: {p_a} vs {p_b}."})
    else:
        steps.append({"step": step, "check": "Period Comparison",
                      "result": "match",
                      "detail": f"Same reporting period: {p_a}."})
    step += 1

    # Value check
    n_a, n_b = _extract_number(val_a), _extract_number(val_b)
    if n_a is not None and n_b is not None:
        denom = max(abs(n_a), abs(n_b))
        diff_pct = abs(n_a - n_b) / denom * 100 if denom else 0
        if diff_pct <= 5:
            steps.append({"step": step, "check": "Value Comparison",
                          "result": "match",
                          "detail": f"{val_a} vs {val_b} — within 5% tolerance ({diff_pct:.1f}% difference)."})
        else:
            steps.append({"step": step, "check": "Value Comparison",
                          "result": "conflict",
                          "detail": f"{val_a} vs {val_b} — {diff_pct:.1f}% difference exceeds tolerance."})
    else:
        match = (val_a or "").strip().lower() == (val_b or "").strip().lower()
        steps.append({"step": step, "check": "Value Comparison",
                      "result": "match" if match else "conflict",
                      "detail": f"'{val_a}' vs '{val_b}'."})
    step += 1

    # Source check
    src_a = fact_a.get("evidence", {}).get("original_filename", "Unknown")
    src_b = fact_b.get("evidence", {}).get("original_filename", "Unknown")
    steps.append({"step": step, "check": "Source Documents",
                  "result": "info",
                  "detail": f"Document A: {src_a} · Document B: {src_b}."})
    step += 1

    # Classification
    classification_detail = {
        "corroborated": "Same entity, same attribute, same period, values agree → Corroborated.",
        "contradiction": "Same entity, same attribute, same period, values conflict → Contradiction.",
        "reconciled": "Same entity, same attribute, different periods → Reconciled (temporal change).",
        "related": "Different entities share the same attribute → Related.",
    }.get(rel_type, f"Classified as {rel_type}.")
    steps.append({"step": step, "check": "Classification",
                  "result": rel_type,
                  "detail": classification_detail})

    return steps


def _store_reasoning(relationship_id: str, steps: list[dict]):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO relationship_reasoning (relationship_id, steps, created_at)
               VALUES (?, ?, ?)""",
            (relationship_id, json.dumps(steps), datetime.now(timezone.utc).isoformat()),
        )


    ev_a = fact_a.get("evidence", {})
    ev_b = fact_b.get("evidence", {})

    prompt = RELATIONSHIP_EXPLANATION_PROMPT.format(
        entity_a=fact_a["entity"], attribute_a=fact_a["attribute"],
        value_a=fact_a.get("canonical_value") or fact_a["raw_value"],
        period_a=fact_a.get("period") or "N/A",
        source_a=ev_a.get("original_filename", "Unknown"),
        page_a=ev_a.get("page_number", "?"),
        snippet_a=ev_a.get("snippet", "")[:200],
        entity_b=fact_b["entity"], attribute_b=fact_b["attribute"],
        value_b=fact_b.get("canonical_value") or fact_b["raw_value"],
        period_b=fact_b.get("period") or "N/A",
        source_b=ev_b.get("original_filename", "Unknown"),
        page_b=ev_b.get("page_number", "?"),
        snippet_b=ev_b.get("snippet", "")[:200],
        relationship_type=rel_type,
    )
    try:
        return generate_text(prompt, temperature=0.2)
    except Exception as e:
        log.warning("Explanation generation failed: %s", e)
        return f"{rel_type.capitalize()} relationship detected between {fact_a['entity']} and {fact_b['entity']}."


# ---------------------------------------------------------------------------
# Store relationship
# ---------------------------------------------------------------------------

def _store_relationship(source_id: str, target_id: str, rel_type: str, explanation: str, confidence: float):
    # Avoid duplicates
    with get_db() as conn:
        existing = conn.execute(
            """SELECT id FROM relationships
               WHERE (source_fact_id=? AND target_fact_id=?)
                  OR (source_fact_id=? AND target_fact_id=?)""",
            (source_id, target_id, target_id, source_id),
        ).fetchone()
        if existing:
            return None

        rel_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO relationships
               (id, source_fact_id, target_fact_id, relationship_type, explanation, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rel_id, source_id, target_id, rel_type, explanation,
             round(confidence, 3), datetime.now(timezone.utc).isoformat()),
        )
    log.info("Relationship stored | type=%s | src=%s | tgt=%s", rel_type, source_id[:8], target_id[:8])
    return rel_id


# ---------------------------------------------------------------------------
# Main: analyze a new document's facts against all existing facts
# ---------------------------------------------------------------------------

def analyze_document_relationships(document_id: str) -> int:
    """
    Compare only NEW facts (not yet analyzed) from document_id against all
    existing facts from other documents. Fully incremental — never re-analyzes
    already-compared pairs.
    Returns count of relationships created.
    """
    # Only get facts not yet in the relationships table as source
    new_fact_ids = get_new_facts_since_last_analysis(document_id)

    if not new_fact_ids:
        log.info("No new facts to analyze for document %s", document_id)
        return 0

    with get_db() as conn:
        placeholders = ",".join("?" * len(new_fact_ids))
        new_facts = conn.execute(
            f"SELECT * FROM facts WHERE id IN ({placeholders})",
            new_fact_ids,
        ).fetchall()

    new_facts = [dict(f) for f in new_facts]
    total_relationships = 0

    log.info("Analyzing relationships for %d new facts in document %s", len(new_facts), document_id)

    for fact in new_facts:
        embed_text = f"{fact['entity']} {fact['attribute']} {fact.get('canonical_value') or fact['raw_value']} {fact.get('period') or ''}"

        try:
            embedding = get_embedding(embed_text)
        except Exception as e:
            log.warning("Embedding failed for fact %s: %s", fact["id"], e)
            embedding = None

        if embedding:
            candidates_meta = search_similar(embedding, top_k=20, threshold=_SIMILARITY_THRESHOLD)
            candidate_ids = [
                c["fact_id"] for c in candidates_meta
                if c["fact_id"] != fact["id"]
            ]
            add_fact_embedding(fact["id"], fact["entity"], fact["attribute"], fact.get("period"), embedding)
        else:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT id FROM facts
                       WHERE attribute=? AND document_id!=? AND id!=?
                       LIMIT 50""",
                    (fact["attribute"], document_id, fact["id"]),
                ).fetchall()
            candidate_ids = [r["id"] for r in rows]

        if not candidate_ids:
            continue

        with get_db() as conn:
            for cand_id in candidate_ids:
                fact_a = _get_fact_with_evidence(fact["id"], conn)
                fact_b = _get_fact_with_evidence(cand_id, conn)
                if not fact_a or not fact_b:
                    continue

                result = _detect_relationship(fact_a, fact_b)
                if not result:
                    continue

                rel_type, confidence, reasoning_steps = result
                explanation = _generate_explanation(fact_a, fact_b, rel_type)
                rel_id = _store_relationship(fact["id"], cand_id, rel_type, explanation, confidence)
                if rel_id:
                    _store_reasoning(rel_id, reasoning_steps)
                    total_relationships += 1

    log.info("Relationship analysis complete | doc=%s | relationships=%d", document_id, total_relationships)
    return total_relationships


def get_relationships_for_fact(fact_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT r.*, 
                fa.entity as src_entity, fa.attribute as src_attr,
                fa.canonical_value as src_value, fa.period as src_period,
                fb.entity as tgt_entity, fb.attribute as tgt_attr,
                fb.canonical_value as tgt_value, fb.period as tgt_period
               FROM relationships r
               JOIN facts fa ON r.source_fact_id = fa.id
               JOIN facts fb ON r.target_fact_id = fb.id
               WHERE r.source_fact_id=? OR r.target_fact_id=?""",
            (fact_id, fact_id),
        ).fetchall()
    return [dict(r) for r in rows]
