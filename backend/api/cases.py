"""
Cases API
---------
Returns one real example of each of the four required cases:
  1. Corroborated fact
  2. Genuine contradiction
  3. Reconciled (apparent contradiction explained by context)
  4. Extraction failure

Each case includes full source evidence and the reasoning chain.
"""
import json
from fastapi import APIRouter, Query, Depends
from database.db import get_db
from utils.auth import get_current_user

router = APIRouter()

_USER_PROJECT_SUBQ = "SELECT id FROM projects WHERE user_id=?"


def _enrich_rel(row: dict) -> dict:
    """Attach source/target fact details + reasoning steps to a relationship row."""
    with get_db() as conn:
        src = conn.execute(
            """SELECT f.*, e.page_number, e.snippet, d.original_filename
               FROM facts f
               LEFT JOIN evidence e ON e.fact_id = f.id
               LEFT JOIN documents d ON d.id = f.document_id
               WHERE f.id=? LIMIT 1""",
            (row["source_fact_id"],),
        ).fetchone()
        tgt = conn.execute(
            """SELECT f.*, e.page_number, e.snippet, d.original_filename
               FROM facts f
               LEFT JOIN evidence e ON e.fact_id = f.id
               LEFT JOIN documents d ON d.id = f.document_id
               WHERE f.id=? LIMIT 1""",
            (row["target_fact_id"],),
        ).fetchone()
        reasoning = conn.execute(
            "SELECT steps FROM relationship_reasoning WHERE relationship_id=?",
            (row["id"],),
        ).fetchone()
    return {
        **row,
        "source_fact": dict(src) if src else None,
        "target_fact": dict(tgt) if tgt else None,
        "reasoning_steps": json.loads(reasoning["steps"]) if reasoning else [],
    }


_NOISE_ATTRS = "('Metric', 'Description', 'Location', 'Date')"


def _best_rel(rel_type: str, user_id: str, project_id: str | None) -> dict | None:
    """Return the best cross-document relationship of the given type.
    Prefers: cross-document > has real canonical values > not a noise attribute.
    """
    with get_db() as conn:
        user_filter = f"r.source_fact_id IN (SELECT f.id FROM facts f JOIN documents d ON f.document_id=d.id WHERE d.project_id IN ({_USER_PROJECT_SUBQ}))"
        base_filter = f"""
            AND fa.canonical_value IS NOT NULL
            AND fb.canonical_value IS NOT NULL
            AND fa.attribute NOT IN {_NOISE_ATTRS}
            AND fb.attribute NOT IN {_NOISE_ATTRS}
        """
        if project_id:
            # Try cross-document first
            row = conn.execute(
                f"""SELECT r.* FROM relationships r
                    JOIN facts fa ON r.source_fact_id=fa.id
                    JOIN facts fb ON r.target_fact_id=fb.id
                    JOIN documents da ON fa.document_id=da.id
                    JOIN documents db ON fb.document_id=db.id
                    WHERE da.project_id=? AND {user_filter}
                      AND r.relationship_type=?
                      AND da.id != db.id
                      {base_filter}
                    ORDER BY r.confidence DESC LIMIT 1""",
                (project_id, user_id, rel_type),
            ).fetchone()
            # Fall back to any relationship in project
            if not row:
                row = conn.execute(
                    f"""SELECT r.* FROM relationships r
                        JOIN facts fa ON r.source_fact_id=fa.id
                        JOIN facts fb ON r.target_fact_id=fb.id
                        JOIN documents da ON fa.document_id=da.id
                        WHERE da.project_id=? AND {user_filter}
                          AND r.relationship_type=?
                          {base_filter}
                        ORDER BY r.confidence DESC LIMIT 1""",
                    (project_id, user_id, rel_type),
                ).fetchone()
        else:
            row = conn.execute(
                f"""SELECT r.* FROM relationships r
                    JOIN facts fa ON r.source_fact_id=fa.id
                    JOIN facts fb ON r.target_fact_id=fb.id
                    JOIN documents da ON fa.document_id=da.id
                    JOIN documents db ON fb.document_id=db.id
                    WHERE {user_filter}
                      AND r.relationship_type=?
                      AND da.id != db.id
                      {base_filter}
                    ORDER BY r.confidence DESC LIMIT 1""",
                (user_id, rel_type),
            ).fetchone()
    return _enrich_rel(dict(row)) if row else None


def _best_failure(user_id: str, project_id: str | None) -> dict | None:
    """Return the most illustrative extraction failure for this user."""
    with get_db() as conn:
        if project_id:
            row = conn.execute(
                """SELECT ef.*, d.original_filename FROM extraction_failures ef
                   JOIN documents d ON ef.document_id=d.id
                   WHERE d.project_id=?
                     AND d.project_id IN (SELECT id FROM projects WHERE user_id=?)
                   ORDER BY ef.created_at DESC LIMIT 1""",
                (project_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT ef.*, d.original_filename FROM extraction_failures ef
                   JOIN documents d ON ef.document_id=d.id
                   WHERE d.project_id IN (SELECT id FROM projects WHERE user_id=?)
                   ORDER BY ef.created_at DESC LIMIT 1""",
                (user_id,),
            ).fetchone()
    return dict(row) if row else None


@router.get("/cases")
def get_cases(
    project_id: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Return one real example of each of the four required cases.
    All data comes from the knowledge layer — no hardcoded examples.
    """
    uid = user["id"]
    return {
        "corroborated": _best_rel("corroborated", uid, project_id),
        "contradiction": _best_rel("contradiction", uid, project_id),
        "reconciled":    _best_rel("reconciled",    uid, project_id),
        "extraction_failure": _best_failure(uid, project_id),
    }
