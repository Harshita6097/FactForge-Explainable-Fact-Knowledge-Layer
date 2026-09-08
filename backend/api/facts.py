from fastapi import APIRouter, HTTPException, Query
from database.db import get_db
from models.fact import FactResponse, FactWithEvidence, EvidenceResponse

router = APIRouter()


@router.get("/facts", response_model=list[FactResponse])
def list_facts(
    document_id: str | None = Query(None),
    entity: str | None = Query(None),
    attribute: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = []
    params: list = []

    if document_id:
        conditions.append("f.document_id = ?")
        params.append(document_id)
    if entity:
        conditions.append("LOWER(f.entity) LIKE ?")
        params.append(f"%{entity.lower()}%")
    if attribute:
        conditions.append("LOWER(f.attribute) LIKE ?")
        params.append(f"%{attribute.lower()}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT f.* FROM facts f
                {where}
                ORDER BY f.entity, f.attribute
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()

    return [FactResponse(**dict(r)) for r in rows]


@router.get("/facts/stats")
def facts_stats():
    with get_db() as conn:
        total_facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        corroborated = conn.execute(
            "SELECT COUNT(*) FROM relationships WHERE relationship_type='corroborated'"
        ).fetchone()[0]
        contradictions = conn.execute(
            "SELECT COUNT(*) FROM relationships WHERE relationship_type='contradiction'"
        ).fetchone()[0]
        reconciled = conn.execute(
            "SELECT COUNT(*) FROM relationships WHERE relationship_type='reconciled'"
        ).fetchone()[0]
        canonical_facts = conn.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
        multi_doc_facts = conn.execute(
            "SELECT COUNT(*) FROM canonical_facts WHERE supporting_count > 1"
        ).fetchone()[0]

    return {
        "documents": total_docs,
        "facts": total_facts,
        "canonical_facts": canonical_facts,
        "multi_document_facts": multi_doc_facts,
        "corroborated": corroborated,
        "contradictions": contradictions,
        "reconciled": reconciled,
    }


@router.get("/facts/{fact_id}", response_model=FactWithEvidence)
def get_fact(fact_id: str):
    with get_db() as conn:
        fact = conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        if not fact:
            raise HTTPException(status_code=404, detail="Fact not found")
        evidence = conn.execute(
            """SELECT e.*, d.original_filename as document_name
               FROM evidence e
               JOIN documents d ON e.document_id = d.id
               WHERE e.fact_id=?""",
            (fact_id,),
        ).fetchall()
        # Confidence breakdown signals
        corroboration_count = conn.execute(
            """SELECT COUNT(*) FROM relationships
               WHERE (source_fact_id=? OR target_fact_id=?)
               AND relationship_type='corroborated'""",
            (fact_id, fact_id),
        ).fetchone()[0]
        contradiction_count = conn.execute(
            """SELECT COUNT(*) FROM relationships
               WHERE (source_fact_id=? OR target_fact_id=?)
               AND relationship_type='contradiction'""",
            (fact_id, fact_id),
        ).fetchone()[0]

    fact_dict = dict(fact)
    base_confidence = fact_dict["confidence"]

    confidence_breakdown = [
        {"signal": "Gemini extraction confidence", "value": round(base_confidence, 3),
         "weight": "base", "positive": base_confidence >= 0.7},
        {"signal": "Explicit numeric value", "value": 1.0 if fact_dict.get("canonical_value") else 0.0,
         "weight": "+0.05", "positive": bool(fact_dict.get("canonical_value"))},
        {"signal": "Period specified", "value": 1.0 if fact_dict.get("period") else 0.0,
         "weight": "+0.03", "positive": bool(fact_dict.get("period"))},
        {"signal": f"Corroborated by {corroboration_count} relationship(s)",
         "value": min(corroboration_count * 0.05, 0.15),
         "weight": "+0.05 each", "positive": corroboration_count > 0},
        {"signal": f"Contradicted by {contradiction_count} relationship(s)",
         "value": contradiction_count * -0.1,
         "weight": "-0.10 each", "positive": contradiction_count == 0},
    ]

    return FactWithEvidence(
        **fact_dict,
        evidence=[EvidenceResponse(**dict(e)) for e in evidence],
        confidence_breakdown=confidence_breakdown,
    )


@router.get("/attributes")
def list_attributes():
    """Return all dynamically discovered attributes."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT attribute, canonical_attribute, occurrence_count, first_seen FROM attribute_registry ORDER BY occurrence_count DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/documents/{doc_id}/facts", response_model=list[FactResponse])
def get_document_facts(doc_id: str):
    with get_db() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        rows = conn.execute(
            "SELECT * FROM facts WHERE document_id=? ORDER BY entity, attribute",
            (doc_id,),
        ).fetchall()
    return [FactResponse(**dict(r)) for r in rows]
