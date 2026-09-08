import uuid
from datetime import datetime, timezone
from typing import Optional

from database.db import get_db
from models.fact import RawExtractedFact
from prompts.fact_extraction import BATCH_FACT_EXTRACTION_PROMPT
from services.gemini_client import generate_text, parse_json_response
from utils.config import get_settings

settings = get_settings()

# Pages per Gemini call — keeps prompts focused and memory low
BATCH_SIZE = 3


def _build_pages_text(pages: list[dict]) -> str:
    parts = []
    for p in pages:
        parts.append(f"[Page {p['page_number']}]\n{p['text'][:3000]}")
    return "\n\n---\n\n".join(parts)


def _parse_facts(raw: list, default_page: Optional[int] = None) -> list[RawExtractedFact]:
    facts = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            if "page_number" not in item or item["page_number"] is None:
                item["page_number"] = default_page
            facts.append(RawExtractedFact(**item))
        except Exception:
            continue
    return facts


def _store_fact_with_evidence(
    fact: RawExtractedFact,
    document_id: str,
    page_number: int,
) -> str:
    fact_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO facts
               (id, document_id, entity, attribute, raw_value, unit, period, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact_id, document_id, fact.entity.strip(), fact.attribute.strip(),
                fact.raw_value.strip(), fact.unit, fact.period,
                round(fact.confidence, 3), now,
            ),
        )
        conn.execute(
            """INSERT INTO evidence (id, fact_id, document_id, page_number, snippet)
               VALUES (?, ?, ?, ?, ?)""",
            (evidence_id, fact_id, document_id, page_number, fact.snippet.strip()),
        )
    return fact_id


def mine_facts_for_document(document_id: str, filename: str) -> int:
    """
    Extract facts from all unprocessed pages of a document.
    Processes pages in small batches for memory efficiency.
    Returns total facts stored.
    """
    with get_db() as conn:
        pages = conn.execute(
            """SELECT page_number, text FROM document_pages
               WHERE document_id=? AND processed=0
               ORDER BY page_number""",
            (document_id,),
        ).fetchall()

    if not pages:
        return 0

    pages = [dict(p) for p in pages]
    total_facts = 0

    for i in range(0, len(pages), BATCH_SIZE):
        batch = pages[i : i + BATCH_SIZE]
        pages_text = _build_pages_text(batch)
        first_page = batch[0]["page_number"]

        prompt = BATCH_FACT_EXTRACTION_PROMPT.format(pages_text=pages_text)

        try:
            response = generate_text(prompt, temperature=0.1)
            raw_list = parse_json_response(response)
            if not isinstance(raw_list, list):
                raw_list = []
        except Exception:
            raw_list = []

        facts = _parse_facts(raw_list, default_page=first_page)

        for fact in facts:
            page_num = fact.page_number or first_page
            _store_fact_with_evidence(fact, document_id, page_num)
            total_facts += 1

        # Mark pages as processed
        page_numbers = [p["page_number"] for p in batch]
        with get_db() as conn:
            conn.execute(
                f"""UPDATE document_pages SET processed=1
                    WHERE document_id=? AND page_number IN ({','.join('?' * len(page_numbers))})""",
                [document_id] + page_numbers,
            )

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
