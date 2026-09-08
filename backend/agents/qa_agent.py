import re
from typing import Optional
from database.db import get_db
from prompts.chat_prompts import CHAT_SYSTEM_PROMPT
from services.gemini_client import generate_text, get_embedding
from services.vector_store import search_similar
from utils.logger import get_logger

log = get_logger("qa_agent")

# How many facts to retrieve for context
_TOP_K = 12
_SIMILARITY_THRESHOLD = 0.65  # Lower than relationship engine — cast wider net for chat


def _retrieve_relevant_facts(question: str) -> list[dict]:
    """
    Retrieve the most relevant facts for a question using FAISS.
    Falls back to keyword search in DB if FAISS has no results.
    """
    try:
        embedding = get_embedding(question)
        candidates = search_similar(embedding, top_k=_TOP_K, threshold=_SIMILARITY_THRESHOLD)
        fact_ids = [c["fact_id"] for c in candidates]
    except Exception as e:
        log.warning("FAISS retrieval failed: %s — falling back to keyword search", e)
        fact_ids = []

    if fact_ids:
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

    # Keyword fallback — extract key terms from question
    keywords = [w for w in re.findall(r"\b\w{4,}\b", question.lower()) if w not in {
        "what", "when", "where", "which", "that", "this", "with", "from", "have", "does", "were"
    }]

    if not keywords:
        return []

    with get_db() as conn:
        conditions = " OR ".join(
            ["LOWER(f.entity) LIKE ? OR LOWER(f.attribute) LIKE ? OR LOWER(f.raw_value) LIKE ?"]
            * len(keywords)
        )
        params = []
        for kw in keywords:
            params += [f"%{kw}%", f"%{kw}%", f"%{kw}%"]
        params.append(_TOP_K)

        facts = conn.execute(
            f"""SELECT f.*, e.page_number, e.snippet, d.original_filename
                FROM facts f
                LEFT JOIN evidence e ON e.fact_id = f.id
                LEFT JOIN documents d ON d.id = f.document_id
                WHERE {conditions}
                LIMIT ?""",
            params,
        ).fetchall()

    log.info("Keyword fallback retrieved %d facts for question", len(facts))
    return [dict(f) for f in facts]


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
    Main QA entry point.
    Returns {answer, citations, facts_used, has_answer}.
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
        }

    fact_context = _build_fact_context(facts)
    prompt = CHAT_SYSTEM_PROMPT.format(
        fact_context=fact_context,
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
        }

    citations = _parse_citations(answer, facts)
    has_answer = "don't have enough information" not in answer.lower()

    log.info("QA complete | facts_used=%d | citations=%d | has_answer=%s",
             len(facts), len(citations), has_answer)

    return {
        "answer": answer,
        "citations": citations,
        "facts_used": len(facts),
        "has_answer": has_answer,
    }
