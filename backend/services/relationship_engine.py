import uuid
import re
import json
from datetime import datetime, timezone
from typing import Optional

from database.db import get_db
from services.local_embedder import get_embedding
from services.vector_store import add_fact_embedding, search_similar
from services.incremental_indexer import get_new_facts_since_last_analysis
from utils.logger import get_logger

log = get_logger("relationship_engine")

_DEFAULT_TOLERANCE = 0.05

_ATTRIBUTE_TOLERANCES: dict[str, float] = {
    "revenue": 0.05,
    "net income": 0.05,
    "ebitda": 0.05,
    "pbt": 0.05,
    "market cap": 0.05,
    "gdp growth rate": 0.002,
    "inflation": 0.001,
    "repo rate": 0.001,
    "employees": 0.0,
    "page count": 0.0,
    "warehouses": 0.0,
    "fulfillment centers": 0.0,
}

# Minimum FAISS similarity to consider facts related
_SIMILARITY_THRESHOLD = 0.82

# Confidence threshold below which a fact is flagged as extraction_failure
_LOW_CONFIDENCE_THRESHOLD = 0.55


def _get_tolerance(attribute: str) -> float:
    key = attribute.lower().strip()
    for attr_key, tol in _ATTRIBUTE_TOLERANCES.items():
        if attr_key in key or key in attr_key:
            return tol
    return _DEFAULT_TOLERANCE


# ---------------------------------------------------------------------------
# Numeric helpers
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


def _unit_type(unit: Optional[str]) -> str:
    """
    Classify a canonical unit into a broad type bucket.
    Returns 'monetary' | 'percentage' | 'count' | 'other'.
    Prevents cross-type comparisons (e.g. % vs INR).
    """
    if not unit:
        return "other"
    u = unit.lower()
    if any(k in u for k in ("inr", "usd", "eur", "gbp", "crore", "lakh", "million", "billion", "thousand")):
        return "monetary"
    if "%" in u or "percent" in u or "bps" in u or "basis" in u:
        return "percentage"
    if any(k in u for k in ("employee", "headcount", "warehouse", "shipment", "order",
                             "customer", "store", "city", "pin", "unit", "count")):
        return "count"
    return "other"


def _units_compatible(unit_a: Optional[str], unit_b: Optional[str]) -> bool:
    """Return False if the two units belong to incompatible type buckets."""
    t_a, t_b = _unit_type(unit_a), _unit_type(unit_b)
    # 'other' is compatible with anything (unknown units — don't block)
    if t_a == "other" or t_b == "other":
        return True
    return t_a == t_b


def _numeric_conflict(v1: Optional[str], v2: Optional[str], attribute: str = "") -> bool:
    n1, n2 = _extract_number(v1), _extract_number(v2)
    if n1 is None or n2 is None:
        return False
    if n1 == 0 and n2 == 0:
        return False
    tol = _get_tolerance(attribute)
    denom = max(abs(n1), abs(n2))
    return abs(n1 - n2) / denom > tol


def _numeric_match(v1: Optional[str], v2: Optional[str], attribute: str = "") -> bool:
    n1, n2 = _extract_number(v1), _extract_number(v2)
    if n1 is None or n2 is None:
        return bool(v1 and v2 and v1.strip().lower() == v2.strip().lower())
    if n1 == 0 and n2 == 0:
        return True
    tol = _get_tolerance(attribute)
    denom = max(abs(n1), abs(n2))
    return abs(n1 - n2) / denom <= tol


def _diff_pct(v1: Optional[str], v2: Optional[str]) -> Optional[float]:
    n1, n2 = _extract_number(v1), _extract_number(v2)
    if n1 is None or n2 is None:
        return None
    denom = max(abs(n1), abs(n2))
    if denom == 0:
        return 0.0
    return abs(n1 - n2) / denom * 100


# ---------------------------------------------------------------------------
# Reconciliation context detector
# Determines *why* two facts with the same entity+attribute differ.
# Returns a human-readable context string used in the reasoning chain.
# ---------------------------------------------------------------------------

def _reconciliation_context(fact_a: dict, fact_b: dict) -> str:
    """
    Classify the reason two facts for the same entity+attribute differ.
    Returns one of: 'different_periods' | 'different_scope' |
                    'different_accounting_standard' | 'rounding_difference'
    """
    p_a = (fact_a.get("period") or "").upper()
    p_b = (fact_b.get("period") or "").upper()

    # Different fiscal periods — most common reconciliation
    if p_a and p_b and p_a != p_b:
        return "different_periods"

    # Scope difference — one value is significantly larger (consolidated vs standalone)
    n_a = _extract_number(fact_a.get("canonical_value"))
    n_b = _extract_number(fact_b.get("canonical_value"))
    if n_a and n_b:
        ratio = max(n_a, n_b) / min(n_a, n_b) if min(n_a, n_b) != 0 else 0
        if ratio > 1.5:
            return "different_scope"

    # Attribute name hints at accounting standard difference
    attr = fact_a.get("attribute", "").lower()
    if any(kw in attr for kw in ["adjusted", "reported", "restated", "pro forma", "ifrs", "gaap", "ind as"]):
        return "different_accounting_standard"

    # Small numeric difference — likely rounding
    pct = _diff_pct(fact_a.get("canonical_value"), fact_b.get("canonical_value"))
    if pct is not None and pct <= 2.0:
        return "rounding_difference"

    return "different_periods"


# ---------------------------------------------------------------------------
# Relationship detection — fully deterministic, four categories
# ---------------------------------------------------------------------------

def _detect_relationship(fact_a: dict, fact_b: dict) -> Optional[tuple[str, float, list, str]]:
    """
    Returns (relationship_type, confidence, reasoning_steps, reasoning_summary)
    or None if unrelated.

    Four categories:
      corroborated       — same entity, attribute, period, values agree
      contradiction      — same entity, attribute, period, values conflict
      reconciled         — same entity, attribute, different periods/scope/standard
      extraction_failure — one fact has low confidence or unmapped attribute
    """
    # --- Extraction failure check first ---
    conf_a = fact_a.get("confidence", 1.0)
    conf_b = fact_b.get("confidence", 1.0)
    attr_a = fact_a.get("attribute", "")
    attr_b = fact_b.get("attribute", "")

    if conf_a < _LOW_CONFIDENCE_THRESHOLD or conf_b < _LOW_CONFIDENCE_THRESHOLD:
        low_fact = fact_a if conf_a < conf_b else fact_b
        steps = _build_failure_steps(fact_a, fact_b, "low_confidence",
                                     f"Confidence {min(conf_a, conf_b):.2f} below threshold {_LOW_CONFIDENCE_THRESHOLD}")
        summary = (
            f"Extraction quality flag: '{low_fact['entity']} {low_fact['attribute']}' "
            f"has confidence {min(conf_a, conf_b):.2f} — result may be unreliable."
        )
        return ("extraction_failure", min(conf_a, conf_b), steps, summary)

    if attr_a.lower() in ("metric", "description") or attr_b.lower() in ("metric", "description"):
        steps = _build_failure_steps(fact_a, fact_b, "unmapped_attribute",
                                     "Attribute could not be mapped to a known financial/operational category")
        summary = (
            f"Extraction quality flag: attribute '{attr_a}' or '{attr_b}' "
            f"is unmapped — relationship classification skipped."
        )
        return ("extraction_failure", 0.40, steps, summary)

    # --- Standard relationship detection ---
    same_entity = _entities_match(fact_a["entity"], fact_b["entity"])
    same_attr = _attributes_match(attr_a, attr_b)
    periods_differ = _periods_differ(fact_a.get("period"), fact_b.get("period"))

    val_a = fact_a.get("canonical_value") or fact_a.get("raw_value")
    val_b = fact_b.get("canonical_value") or fact_b.get("raw_value")

    rel_type: Optional[str] = None
    confidence = 0.0
    context = ""

    unit_a = fact_a.get("unit") or fact_a.get("canonical_unit")
    unit_b = fact_b.get("unit") or fact_b.get("canonical_unit")
    units_ok = _units_compatible(unit_a, unit_b)

    if same_entity and same_attr:
        # Criterion 2: units must be the same type — no % vs INR comparisons
        if not units_ok:
            return None
        # Criterion 3: canonical units must also agree (prevents crore vs billion mismatch)
        if unit_a and unit_b and unit_a.lower() != unit_b.lower():
            # Different canonical units for same attribute — log as reconciled, not contradiction
            if _numeric_conflict(val_a, val_b, attr_a):
                rel_type, confidence = "reconciled", 0.72
                context = "different_scope"
            else:
                return None
        elif _numeric_match(val_a, val_b, attr_a):
            rel_type, confidence = "corroborated", 0.95
        elif _numeric_conflict(val_a, val_b, attr_a):
            if periods_differ:
                rel_type, confidence = "reconciled", 0.88
                context = _reconciliation_context(fact_a, fact_b)
            else:
                rel_type, confidence = "contradiction", 0.90
        else:
            if periods_differ:
                rel_type, confidence = "reconciled", 0.80
                context = _reconciliation_context(fact_a, fact_b)
            else:
                rel_type, confidence = "contradiction", 0.75
    elif same_attr and not same_entity:
        if not units_ok:
            return None
        rel_type, confidence = "related", 0.60

    if rel_type is None:
        return None

    steps = _build_reasoning_steps(
        fact_a, fact_b, rel_type, same_entity, same_attr,
        periods_differ, val_a, val_b, context,
    )
    summary = _build_summary(fact_a, fact_b, rel_type, val_a, val_b, context)
    return (rel_type, confidence, steps, summary)


# ---------------------------------------------------------------------------
# Evidence fetcher
# ---------------------------------------------------------------------------

def _get_fact_with_evidence(fact_id: str, conn) -> Optional[dict]:
    fact = conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
    if not fact:
        return None
    ev = conn.execute(
        """SELECT e.page_number, e.snippet, d.original_filename, d.id as document_id
           FROM evidence e JOIN documents d ON e.document_id=d.id
           WHERE e.fact_id=? LIMIT 1""",
        (fact_id,),
    ).fetchone()
    return {**dict(fact), "evidence": dict(ev) if ev else {}}


# ---------------------------------------------------------------------------
# Reasoning builders
# ---------------------------------------------------------------------------

_RECONCILIATION_LABELS = {
    "different_periods": "Values cover different fiscal periods — temporal change, not a conflict.",
    "different_scope":   "Values differ in scope (e.g. consolidated vs standalone reporting).",
    "different_accounting_standard": "Values use different accounting standards or adjustments.",
    "rounding_difference": "Difference is within rounding tolerance — effectively the same value.",
}


def _build_reasoning_steps(
    fact_a: dict, fact_b: dict, rel_type: str,
    same_entity: bool, same_attr: bool, periods_differ: bool,
    val_a: Optional[str], val_b: Optional[str],
    context: str = "",
) -> list[dict]:
    steps = []
    n = 1

    steps.append({
        "step": n, "check": "Entity Match",
        "result": "match" if same_entity else "different",
        "detail": (
            f"Both facts refer to '{fact_a['entity']}'."
            if same_entity else
            f"'{fact_a['entity']}' vs '{fact_b['entity']}' — different entities."
        ),
    })
    n += 1

    steps.append({
        "step": n, "check": "Attribute Match",
        "result": "match" if same_attr else "different",
        "detail": (
            f"Both measure '{fact_a['attribute']}'."
            if same_attr else
            f"'{fact_a['attribute']}' vs '{fact_b['attribute']}' — semantically related."
        ),
    })
    n += 1

    unit_a = fact_a.get("unit") or fact_a.get("canonical_unit")
    unit_b = fact_b.get("unit") or fact_b.get("canonical_unit")
    units_ok = _units_compatible(unit_a, unit_b)
    steps.append({
        "step": n, "check": "Unit Compatibility",
        "result": "match" if units_ok else "incompatible",
        "detail": (
            f"Units compatible: {unit_a or 'N/A'} vs {unit_b or 'N/A'}."
            if units_ok else
            f"Unit type mismatch: '{unit_a}' vs '{unit_b}' — comparison blocked."
        ),
    })
    n += 1

    p_a = fact_a.get("period") or "N/A"
    p_b = fact_b.get("period") or "N/A"
    steps.append({
        "step": n, "check": "Period Comparison",
        "result": "different" if periods_differ else "match",
        "detail": (
            f"Reporting periods differ: {p_a} vs {p_b}."
            if periods_differ else
            f"Same reporting period: {p_a}."
        ),
    })
    n += 1

    n_a, n_b = _extract_number(val_a), _extract_number(val_b)
    if n_a is not None and n_b is not None:
        denom = max(abs(n_a), abs(n_b))
        diff_pct = abs(n_a - n_b) / denom * 100 if denom else 0
        steps.append({
            "step": n, "check": "Value Comparison",
            "result": "match" if diff_pct <= _get_tolerance(fact_a.get("attribute", "")) * 100 else "conflict",
            "detail": f"{val_a} vs {val_b} — {diff_pct:.1f}% difference.",
        })
    else:
        match = (val_a or "").strip().lower() == (val_b or "").strip().lower()
        steps.append({
            "step": n, "check": "Value Comparison",
            "result": "match" if match else "conflict",
            "detail": f"'{val_a}' vs '{val_b}'.",
        })
    n += 1

    src_a = fact_a.get("evidence", {}).get("original_filename", "Unknown")
    src_b = fact_b.get("evidence", {}).get("original_filename", "Unknown")
    steps.append({
        "step": n, "check": "Source Documents",
        "result": "info",
        "detail": f"Document A: {src_a} · Document B: {src_b}.",
    })
    n += 1

    if rel_type == "reconciled" and context:
        steps.append({
            "step": n, "check": "Reconciliation Context",
            "result": "reconciled",
            "detail": _RECONCILIATION_LABELS.get(context, context),
        })
        n += 1

    classification_detail = {
        "corroborated":  "Same entity, attribute, period — values agree → Corroborated.",
        "contradiction": "Same entity, attribute, period — values conflict → Genuine Contradiction.",
        "reconciled":    "Same entity, attribute — apparent conflict explained by context → Reconciled.",
        "related":       "Different entities share the same attribute → Related.",
    }.get(rel_type, f"Classified as {rel_type}.")
    steps.append({"step": n, "check": "Classification", "result": rel_type, "detail": classification_detail})

    return steps


def _build_failure_steps(fact_a: dict, fact_b: dict, reason: str, detail: str) -> list[dict]:
    src_a = fact_a.get("evidence", {}).get("original_filename", "Unknown")
    src_b = fact_b.get("evidence", {}).get("original_filename", "Unknown")
    return [
        {"step": 1, "check": "Extraction Quality", "result": "flagged", "detail": detail},
        {"step": 2, "check": "Source Documents", "result": "info",
         "detail": f"Document A: {src_a} · Document B: {src_b}."},
        {"step": 3, "check": "Classification", "result": "extraction_failure",
         "detail": f"Flagged as extraction/reasoning failure — reason: {reason}."},
    ]


def _build_summary(
    fact_a: dict, fact_b: dict, rel_type: str,
    val_a: Optional[str], val_b: Optional[str],
    context: str = "",
) -> str:
    src_a = fact_a.get("evidence", {}).get("original_filename", "Doc A")
    src_b = fact_b.get("evidence", {}).get("original_filename", "Doc B")
    p_a = fact_a.get("period") or ""
    p_b = fact_b.get("period") or ""
    attr = fact_a.get("attribute", "")
    entity = fact_a.get("entity", "")
    pa_str = f" ({p_a})" if p_a else ""
    pb_str = f" ({p_b})" if p_b else ""

    if rel_type == "corroborated":
        return (
            f"{entity} {attr} of {val_a}{pa_str} is corroborated across "
            f"{src_a} and {src_b} — both sources agree."
        )
    if rel_type == "contradiction":
        return (
            f"Genuine contradiction: {entity} {attr} — {src_a} reports {val_a}{pa_str} "
            f"while {src_b} reports {val_b}{pb_str} for the same period."
        )
    if rel_type == "reconciled":
        label = _RECONCILIATION_LABELS.get(context, "context differs")
        return (
            f"Apparent contradiction reconciled: {entity} {attr} shows {val_a}{pa_str} vs "
            f"{val_b}{pb_str} — {label}"
        )
    if rel_type == "related":
        return (
            f"{fact_a['entity']} and {fact_b['entity']} both report {attr}: "
            f"{val_a} vs {val_b} ({src_a} vs {src_b})."
        )
    return f"{rel_type.capitalize()} relationship between {entity} and {fact_b['entity']}."


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _store_reasoning(relationship_id: str, steps: list[dict]):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO relationship_reasoning (relationship_id, steps, created_at)
               VALUES (?, ?, ?)""",
            (relationship_id, json.dumps(steps), datetime.now(timezone.utc).isoformat()),
        )


def _store_relationship(
    source_id: str, target_id: str, rel_type: str,
    summary: str, confidence: float,
) -> Optional[str]:
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
               (id, source_fact_id, target_fact_id, relationship_type,
                explanation, reasoning_summary, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rel_id, source_id, target_id, rel_type,
             summary, summary,
             round(confidence, 3), datetime.now(timezone.utc).isoformat()),
        )
    log.info("Relationship stored | type=%s | src=%s | tgt=%s", rel_type, source_id[:8], target_id[:8])
    return rel_id


def log_extraction_failure(
    document_id: str,
    page_number: Optional[int],
    raw_text: str,
    failure_reason: str,
    chain_of_thought: str,
    confidence: float = 0.0,
):
    """Record a fact that failed extraction quality checks into extraction_failures."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO extraction_failures
               (id, document_id, page_number, raw_text, failure_reason,
                chain_of_thought, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), document_id, page_number,
                raw_text[:500], failure_reason, chain_of_thought,
                round(confidence, 3), datetime.now(timezone.utc).isoformat(),
            ),
        )


# ---------------------------------------------------------------------------
# Main: analyze a new document's facts against facts from OTHER documents
# ---------------------------------------------------------------------------

def analyze_document_relationships(document_id: str) -> int:
    """
    Compare facts from document_id against:
      1. Facts from OTHER documents (cross-document)
      2. Facts within the SAME document (intra-document contradictions/corroborations)
    Fully incremental. Returns count of relationships created.
    """
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

    from services.vector_store import get_index_meta

    for fact in new_facts:
        embed_text = (
            f"{fact['entity']} {fact['attribute']} "
            f"{fact.get('canonical_value') or fact['raw_value']} "
            f"{fact.get('period') or ''}"
        )

        try:
            embedding = get_embedding(embed_text)
        except Exception as e:
            log.warning("Embedding failed for fact %s: %s", fact["id"], e)
            embedding = None

        if embedding:
            already_indexed = any(m["fact_id"] == fact["id"] for m in get_index_meta())
            if not already_indexed:
                add_fact_embedding(
                    fact["id"], fact["entity"],
                    fact["attribute"], fact.get("period"), embedding,
                )
            candidates_meta = search_similar(embedding, top_k=20, threshold=_SIMILARITY_THRESHOLD)
            candidate_ids = [
                c["fact_id"] for c in candidates_meta
                if c["fact_id"] != fact["id"]
            ]
        else:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT id FROM facts
                       WHERE attribute=? AND id!=?
                       LIMIT 50""",
                    (fact["attribute"], fact["id"]),
                ).fetchall()
            candidate_ids = [r["id"] for r in rows]

        if not candidate_ids:
            continue

        for cand_id in candidate_ids:
            with get_db() as conn:
                fact_a = _get_fact_with_evidence(fact["id"], conn)
                fact_b = _get_fact_with_evidence(cand_id, conn)

            if not fact_a or not fact_b:
                continue

            doc_a = fact_a.get("document_id") or fact_a.get("evidence", {}).get("document_id")
            doc_b = fact_b.get("document_id") or fact_b.get("evidence", {}).get("document_id")
            same_doc = doc_a and doc_b and doc_a == doc_b

            result = _detect_relationship(fact_a, fact_b)
            if not result:
                continue

            rel_type, confidence, reasoning_steps, summary = result

            # For intra-document pairs, only store meaningful relationship types
            # (skip "related" within same doc — different entities same attr is noise)
            if same_doc and rel_type == "related":
                continue

            rel_id = _store_relationship(fact["id"], cand_id, rel_type, summary, confidence)
            if rel_id:
                _store_reasoning(rel_id, reasoning_steps)
                total_relationships += 1

    log.info("Relationship analysis complete | doc=%s | relationships=%d", document_id, total_relationships)
    return total_relationships


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_relationships_for_fact(fact_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT r.*,
                fa.entity as src_entity, fa.attribute as src_attr,
                fa.canonical_value as src_value, fa.period as src_period,
                fb.entity as tgt_entity, fb.attribute as tgt_attr,
                fb.canonical_value as tgt_value, fb.period as tgt_period,
                da.original_filename as src_doc, db.original_filename as tgt_doc
               FROM relationships r
               JOIN facts fa ON r.source_fact_id = fa.id
               JOIN facts fb ON r.target_fact_id = fb.id
               JOIN documents da ON fa.document_id = da.id
               JOIN documents db ON fb.document_id = db.id
               WHERE r.source_fact_id=? OR r.target_fact_id=?""",
            (fact_id, fact_id),
        ).fetchall()
    return [dict(r) for r in rows]


def get_extraction_failures(document_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Return logged extraction failures, optionally filtered by document."""
    with get_db() as conn:
        if document_id:
            rows = conn.execute(
                """SELECT ef.*, d.original_filename
                   FROM extraction_failures ef
                   JOIN documents d ON ef.document_id = d.id
                   WHERE ef.document_id=?
                   ORDER BY ef.created_at DESC LIMIT ?""",
                (document_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ef.*, d.original_filename
                   FROM extraction_failures ef
                   JOIN documents d ON ef.document_id = d.id
                   ORDER BY ef.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
