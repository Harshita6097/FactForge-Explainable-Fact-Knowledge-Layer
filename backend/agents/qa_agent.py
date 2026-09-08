import re
from database.db import get_db
from services.gemini_client import get_embedding
from services.vector_store import search_similar
from utils.logger import get_logger

log = get_logger("qa_agent")

_TOP_K = 12
_SIMILARITY_THRESHOLD = 0.65

# Keywords that indicate a meta question about relationships — answer from DB directly
_META_KEYWORDS = [
    "contradiction", "contradict", "conflict", "corrobor", "reconcil",
    "disagree", "inconsisten", "mismatch", "differ", "relationship",
]


def _is_meta_question(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _META_KEYWORDS)


def _answer_meta_question(question: str) -> dict:
    """Answer questions about relationships directly from the relationships table."""
    q = question.lower()

    # Determine which relationship types to fetch
    if "contradict" in q or "conflict" in q or "inconsisten" in q or "mismatch" in q:
        types = ("contradiction",)
        label = "contradictions"
    elif "corrobor" in q or "agree" in q or "confirm" in q:
        types = ("corroborated",)
        label = "corroborations"
    elif "reconcil" in q:
        types = ("reconciled",)
        label = "reconciliations"
    else:
        types = ("contradiction", "corroborated", "reconciled")
        label = "relationships"

    with get_db() as conn:
        ph = ",".join("?" * len(types))
        rows = conn.execute(
            f"""SELECT r.relationship_type, r.explanation, r.confidence,
                       fa.entity as src_entity, fa.attribute as src_attr,
                       fa.canonical_value as src_value, fa.period as src_period,
                       da.original_filename as src_doc, ea.page_number as src_page,
                       fb.entity as tgt_entity, fb.attribute as tgt_attr,
                       fb.canonical_value as tgt_value, fb.period as tgt_period,
                       db.original_filename as tgt_doc, eb.page_number as tgt_page
                FROM relationships r
                JOIN facts fa ON r.source_fact_id=fa.id
                JOIN facts fb ON r.target_fact_id=fb.id
                JOIN documents da ON fa.document_id=da.id
                JOIN documents db ON fb.document_id=db.id
                LEFT JOIN evidence ea ON ea.fact_id=fa.id
                LEFT JOIN evidence eb ON eb.fact_id=fb.id
                WHERE r.relationship_type IN ({ph})
                GROUP BY r.id
                ORDER BY r.confidence DESC
                LIMIT 10""",
            types,
        ).fetchall()

    rows = [dict(r) for r in rows]

    if not rows:
        return {
            "answer": f"No {label} detected across the uploaded documents.",
            "citations": [], "facts_used": 0, "has_answer": True, "conflicts": [],
        }

    lines = [f"Found {len(rows)} {label} across the uploaded documents:\n"]
    citations = []
    for i, r in enumerate(rows, 1):
        rel = r['relationship_type'].upper()
        p_a = f" ({r['src_period']})" if r['src_period'] else ""
        p_b = f" ({r['tgt_period']})" if r['tgt_period'] else ""
        lines.append(
            f"[{i}] {rel} — {r['src_entity']} {r['src_attr']}: "
            f"{r['src_value']}{p_a} ({r['src_doc']}, p.{r['src_page']}) "
            f"vs {r['tgt_value']}{p_b} ({r['tgt_doc']}, p.{r['tgt_page']})"
        )
        if r['explanation']:
            lines.append(f"     → {r['explanation']}")
        citations.append({
            "fact_id": "",
            "document_name": r['src_doc'],
            "page_number": r['src_page'],
            "snippet": r['explanation'] or "",
            "entity": r['src_entity'],
            "attribute": r['src_attr'],
            "value": r['src_value'] or "",
        })

    lines.append("\nCITATIONS:")
    for r in rows:
        lines.append(f"- {r['src_entity']} {r['src_attr']}: {r['src_value']} — {r['src_doc']}, Page {r['src_page']}")

    return {
        "answer": "\n".join(lines),
        "citations": citations,
        "facts_used": len(rows),
        "has_answer": True,
        "conflicts": rows if label == "contradictions" else [],
    }


def _retrieve_relevant_facts(question: str) -> list[dict]:
    """
    Retrieve relevant facts using FAISS semantic search.
    No keyword fallback — relies entirely on semantic retrieval.
    """
    try:
        embedding = get_embedding(question)
        candidates = search_similar(embedding, top_k=_TOP_K, threshold=_SIMILARITY_THRESHOLD)
        fact_ids = [c["fact_id"] for c in candidates]
    except Exception as e:
        log.warning("FAISS retrieval failed: %s", e)
        return []

    if not fact_ids:
        return []

    with get_db() as conn:
        placeholders = ",".join("?" * len(fact_ids))
        facts = conn.execute(
            f"""SELECT f.*, e.page_number, e.snippet, d.original_filename
                FROM facts f
                LEFT JOIN evidence e ON e.fact_id = f.id
                LEFT JOIN documents d ON d.id = f.document_id
                WHERE f.id IN ({placeholders})""",
            fact_ids,
        ).fetchall()
    return [dict(f) for f in facts]


def _get_conflicts_for_facts(fact_ids: list[str]) -> list[dict]:
    """Find any contradiction relationships among the retrieved facts."""
    if not fact_ids:
        return []
    with get_db() as conn:
        placeholders = ",".join("?" * len(fact_ids))
        rels = conn.execute(
            f"""SELECT r.relationship_type, r.explanation,
                       fa.entity as src_entity, fa.attribute as src_attr,
                       fa.canonical_value as src_value, fa.period as src_period,
                       da.original_filename as src_doc,
                       fb.entity as tgt_entity, fb.attribute as tgt_attr,
                       fb.canonical_value as tgt_value, fb.period as tgt_period,
                       db.original_filename as tgt_doc
                FROM relationships r
                JOIN facts fa ON r.source_fact_id=fa.id
                JOIN facts fb ON r.target_fact_id=fb.id
                JOIN documents da ON fa.document_id=da.id
                JOIN documents db ON fb.document_id=db.id
                WHERE (r.source_fact_id IN ({placeholders})
                   OR r.target_fact_id IN ({placeholders}))
                AND r.relationship_type IN ('contradiction', 'reconciled')""",
            fact_ids + fact_ids,
        ).fetchall()
    return [dict(r) for r in rels]


def _format_answer(facts: list[dict], conflicts: list[dict], question: str) -> str:
    """Build a structured answer directly from retrieved facts — no LLM."""
    lines = [f"Based on the uploaded documents, here is what I found for: '{question}'\n"]
    for i, f in enumerate(facts, 1):
        value = f.get("canonical_value") or f.get("raw_value", "")
        unit = f.get("unit") or ""
        period = f.get("period") or ""
        doc = f.get("original_filename", "Unknown")
        page = f.get("page_number", "?")
        period_str = f" ({period})" if period else ""
        unit_str = f" {unit}" if unit else ""
        lines.append(f"[{i}] {f['entity']} — {f['attribute']}: {value}{unit_str}{period_str}")
        lines.append(f"     Source: {doc}, Page {page}")
    if conflicts:
        lines.append("\nConflicts / Reconciliations:")
        for c in conflicts[:3]:
            lines.append(
                f"  • {c['src_entity']} {c['src_attr']}: {c['src_value']} ({c['src_period']}, {c['src_doc']}) "
                f"vs {c['tgt_value']} ({c['tgt_period']}, {c['tgt_doc']}) — {c['relationship_type']}"
            )
    lines.append("\nCITATIONS:")
    for f in facts:
        value = f.get("canonical_value") or f.get("raw_value", "")
        lines.append(f"- {f['entity']} {f['attribute']}: {value} — {f.get('original_filename', '')}, Page {f.get('page_number', '?')}")
    return "\n".join(lines)


def _parse_citations(answer: str, facts: list[dict]) -> list[dict]:
    """
    Extract citations from the answer text and match them back to fact records.
    Returns a list of evidence dicts for the frontend to display.
    """
    citations = []
    seen_ids = set()

    # Look for CITATIONS section
    citation_section = ""
    if "CITATIONS:" in answer:
        citation_section = answer.split("CITATIONS:")[-1]

    # Match fact references by document name + page number
    for fact in facts:
        doc = fact.get("original_filename", "")
        page = fact.get("page_number")
        fact_id = fact.get("id", "")

        if fact_id in seen_ids:
            continue

        # Check if this fact's document/page appears in the answer or citation section
        if doc and (doc in answer or (page and f"Page {page}" in answer)):
            citations.append({
                "fact_id": fact_id,
                "document_name": doc,
                "page_number": page,
                "snippet": fact.get("snippet", ""),
                "entity": fact.get("entity", ""),
                "attribute": fact.get("attribute", ""),
                "value": fact.get("canonical_value") or fact.get("raw_value", ""),
            })
            seen_ids.add(fact_id)

    # If no citations matched, include top 3 retrieved facts as implicit citations
    if not citations:
        for fact in facts[:3]:
            fact_id = fact.get("id", "")
            if fact_id not in seen_ids:
                citations.append({
                    "fact_id": fact_id,
                    "document_name": fact.get("original_filename", ""),
                    "page_number": fact.get("page_number"),
                    "snippet": fact.get("snippet", ""),
                    "entity": fact.get("entity", ""),
                    "attribute": fact.get("attribute", ""),
                    "value": fact.get("canonical_value") or fact.get("raw_value", ""),
                })
                seen_ids.add(fact_id)

    return citations


def answer_question(question: str) -> dict:
    """
    Main QA entry point. Queries the knowledge layer.
    Returns {answer, citations, facts_used, has_answer, conflicts}.
    """
    log.info("QA question: %s", question[:100])

    # Meta questions about relationships answered directly from DB
    if _is_meta_question(question):
        return _answer_meta_question(question)

    facts = _retrieve_relevant_facts(question)
    log.info("Retrieved %d relevant facts", len(facts))

    if not facts:
        return {
            "answer": "I don't have enough information in the uploaded documents to answer this.",
            "citations": [],
            "facts_used": 0,
            "has_answer": False,
            "conflicts": [],
        }

    fact_ids = [f["id"] for f in facts]
    conflicts = _get_conflicts_for_facts(fact_ids)

    answer = _format_answer(facts, conflicts, question)

    citations = _parse_citations(answer, facts)
    has_answer = "don't have enough information" not in answer.lower()

    log.info("QA complete | facts_used=%d | citations=%d | conflicts=%d | has_answer=%s",
             len(facts), len(citations), len(conflicts), has_answer)

    return {
        "answer": answer,
        "citations": citations,
        "facts_used": len(facts),
        "has_answer": has_answer,
        "conflicts": conflicts,
    }
