import re
from typing import Optional
from database.db import get_db
from prompts.chat_prompts import CHAT_SYSTEM_PROMPT
from services.gemini_client import generate_text, get_embedding
from services.vector_store import search_similar
from utils.logger import get_logger

log = get_logger("qa_agent")

_TOP_K = 12
_SIMILARITY_THRESHOLD = 0.65


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


def _build_fact_context(facts: list[dict]) -> str:
    """Format retrieved facts into a readable context block for the prompt."""
    if not facts:
        return "No relevant facts found in the uploaded documents."

    lines = []
    for i, f in enumerate(facts, 1):
        value = f.get("canonical_value") or f.get("raw_value", "")
        unit = f.get("unit", "") or ""
        period = f.get("period", "") or ""
        doc = f.get("original_filename", "Unknown")
        page = f.get("page_number", "?")
        snippet = f.get("snippet", "")

        line = f"[{i}] {f['entity']} — {f['attribute']}: {value} {unit}".strip()
        if period:
            line += f" ({period})"
        line += f"\n    Source: {doc}, Page {page}"
        if snippet:
            line += f"\n    Evidence: \"{snippet[:200]}\""
        lines.append(line)

    return "\n\n".join(lines)


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

    fact_context = _build_fact_context(facts)

    # Add conflict context to prompt if any exist
    conflict_context = ""
    if conflicts:
        conflict_lines = []
        for c in conflicts[:5]:
            conflict_lines.append(
                f"  - {c['src_entity']} {c['src_attr']}: {c['src_value']} ({c['src_period']}, {c['src_doc']}) "
                f"vs {c['tgt_value']} ({c['tgt_period']}, {c['tgt_doc']}) — {c['relationship_type']}"
            )
        conflict_context = "\n\nKnown conflicts/reconciliations in this data:\n" + "\n".join(conflict_lines)

    prompt = CHAT_SYSTEM_PROMPT.format(
        fact_context=fact_context + conflict_context,
        question=question,
    )

    try:
        answer = generate_text(prompt, temperature=0.2)
    except Exception as e:
        log.error("Gemini QA failed: %s", e)
        return {
            "answer": "An error occurred while generating the answer. Please try again.",
            "citations": [],
            "facts_used": len(facts),
            "has_answer": False,
            "conflicts": [],
        }

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
