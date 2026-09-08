"""
Incremental Indexer
-------------------
Ensures that re-uploading a document or adding new documents never
re-processes already-extracted content. Every operation is idempotent.
"""
from database.db import get_db
from utils.logger import get_logger

log = get_logger("incremental_indexer")


def get_unprocessed_pages(document_id: str) -> list[dict]:
    """Return only pages that haven't been fact-mined yet."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT page_number, text, char_count FROM document_pages
               WHERE document_id=? AND processed=0
               ORDER BY page_number""",
            (document_id,),
        ).fetchall()
    pages = [dict(r) for r in rows]
    log.info("Incremental check | doc=%s | unprocessed_pages=%d", document_id, len(pages))
    return pages


def get_processed_page_count(document_id: str) -> int:
    with get_db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM document_pages WHERE document_id=? AND processed=1",
            (document_id,),
        ).fetchone()[0]


def is_duplicate_document(filename: str, page_count: int) -> str | None:
    """
    Check if a document with the same filename and page count already exists.
    Returns existing document_id if duplicate, else None.
    """
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM documents
               WHERE original_filename=? AND page_count=?
               AND status='completed'""",
            (filename, page_count),
        ).fetchone()
    if row:
        log.info("Duplicate document detected: %s (%d pages) → %s", filename, page_count, row["id"])
        return row["id"]
    return None


def get_existing_fact_fingerprints(document_id: str) -> set[str]:
    """
    Return a set of fingerprints for facts already stored for this document.
    Fingerprint = entity|attribute|canonical_value|period
    Used to skip storing duplicate facts within the same document.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT entity, attribute, canonical_value, period
               FROM facts WHERE document_id=?""",
            (document_id,),
        ).fetchall()
    return {
        f"{r['entity']}|{r['attribute']}|{r['canonical_value']}|{r['period']}"
        for r in rows
    }


def is_fact_duplicate(
    entity: str,
    attribute: str,
    canonical_value: str | None,
    period: str | None,
    existing_fingerprints: set[str],
) -> bool:
    """Check if this exact fact already exists in the current document."""
    fp = f"{entity}|{attribute}|{canonical_value}|{period}"
    return fp in existing_fingerprints


def get_new_facts_since_last_analysis(document_id: str) -> list[str]:
    """
    Return fact IDs from this document that have NOT yet been compared
    in the relationships table. Used for incremental relationship analysis.
    """
    with get_db() as conn:
        all_fact_ids = {
            r["id"] for r in conn.execute(
                "SELECT id FROM facts WHERE document_id=?", (document_id,)
            ).fetchall()
        }
        analyzed_ids = {
            r["source_fact_id"] for r in conn.execute(
                """SELECT DISTINCT source_fact_id FROM relationships r
                   JOIN facts f ON r.source_fact_id = f.id
                   WHERE f.document_id=?""",
                (document_id,),
            ).fetchall()
        }

    new_ids = list(all_fact_ids - analyzed_ids)
    log.info("Incremental relationship check | doc=%s | new_facts=%d / total=%d",
             document_id, len(new_ids), len(all_fact_ids))
    return new_ids


def compute_optimal_batch_size(pages: list[dict]) -> int:
    """
    Dynamically compute batch size based on average page text density.
    Dense pages (lots of text) → smaller batches to stay within token limits.
    Sparse pages → larger batches for efficiency.
    """
    if not pages:
        return 3

    avg_chars = sum(p.get("char_count", len(p.get("text", ""))) for p in pages) / len(pages)

    if avg_chars > 4000:
        return 2   # Very dense — 2 pages per Gemini call
    elif avg_chars > 2000:
        return 3   # Normal density
    elif avg_chars > 800:
        return 5   # Sparse pages (e.g. presentation slides)
    else:
        return 8   # Very sparse (e.g. cover pages, TOC)
