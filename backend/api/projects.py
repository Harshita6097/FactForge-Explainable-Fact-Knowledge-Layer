import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database.db import get_db
from utils.auth import get_current_user

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str
    document_count: int = 0
    fact_count: int = 0
    user_id: Optional[str] = None


@router.post("/projects", response_model=ProjectResponse)
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at, user_id) VALUES (?,?,?,?,?,?)",
            (pid, body.name.strip(), body.description, now, now, user["id"]),
        )
    return ProjectResponse(id=pid, name=body.name.strip(), description=body.description,
                           created_at=now, updated_at=now, user_id=user["id"])


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (user["id"],)
        ).fetchall()
        result = []
        for r in rows:
            doc_count = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE project_id=?", (r["id"],)
            ).fetchone()[0]
            fact_count = conn.execute(
                """SELECT COUNT(*) FROM facts f
                   JOIN documents d ON f.document_id = d.id
                   WHERE d.project_id=?""",
                (r["id"],),
            ).fetchone()[0]
            result.append(ProjectResponse(**dict(r), document_count=doc_count, fact_count=fact_count))
    return result


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Project not found")
        doc_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        fact_count = conn.execute(
            """SELECT COUNT(*) FROM facts f
               JOIN documents d ON f.document_id = d.id
               WHERE d.project_id=?""",
            (project_id,),
        ).fetchone()[0]
    return ProjectResponse(**dict(r), document_count=doc_count, fact_count=fact_count)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, body: ProjectCreate, user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Project not found")
        conn.execute(
            "UPDATE projects SET name=?, description=?, updated_at=? WHERE id=?",
            (body.name.strip(), body.description, now, project_id),
        )
        doc_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        fact_count = conn.execute(
            """SELECT COUNT(*) FROM facts f
               JOIN documents d ON f.document_id = d.id
               WHERE d.project_id=?""",
            (project_id,),
        ).fetchone()[0]
    return ProjectResponse(id=project_id, name=body.name.strip(), description=body.description,
                           created_at=r["created_at"], updated_at=now,
                           document_count=doc_count, fact_count=fact_count)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        r = conn.execute("SELECT id FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Project not found")
        # Cascade: delete all documents in project (documents.py delete logic handles facts/rels)
        doc_ids = [row[0] for row in conn.execute(
            "SELECT id FROM documents WHERE project_id=?", (project_id,)
        ).fetchall()]
        for doc_id in doc_ids:
            fact_ids = [row[0] for row in conn.execute(
                "SELECT id FROM facts WHERE document_id=?", (doc_id,)
            ).fetchall()]
            if fact_ids:
                ph = ",".join("?" * len(fact_ids))
                rel_ids = [row[0] for row in conn.execute(
                    f"SELECT id FROM relationships WHERE source_fact_id IN ({ph}) OR target_fact_id IN ({ph})",
                    fact_ids + fact_ids,
                ).fetchall()]
                if rel_ids:
                    rph = ",".join("?" * len(rel_ids))
                    conn.execute(f"DELETE FROM relationship_reasoning WHERE relationship_id IN ({rph})", rel_ids)
                    conn.execute(f"DELETE FROM relationships WHERE id IN ({rph})", rel_ids)
                conn.execute(f"DELETE FROM canonical_facts WHERE source_fact_ids LIKE ?", (f'%{doc_id}%',))
                conn.execute("DELETE FROM evidence WHERE document_id=?", (doc_id,))
                conn.execute("DELETE FROM document_pages WHERE document_id=?", (doc_id,))
                conn.execute("DELETE FROM facts WHERE document_id=?", (doc_id,))
            conn.execute("DELETE FROM extraction_failures WHERE document_id=?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.execute("DELETE FROM chat_sessions WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"message": "Project deleted"}


@router.get("/projects/{project_id}/stats")
def project_stats(project_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        r = conn.execute("SELECT id FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Project not found")
        docs = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        facts = conn.execute(
            "SELECT COUNT(*) FROM facts f JOIN documents d ON f.document_id=d.id WHERE d.project_id=?",
            (project_id,),
        ).fetchone()[0]
        corroborated = conn.execute(
            """SELECT COUNT(*) FROM relationships r
               JOIN facts f ON r.source_fact_id=f.id
               JOIN documents d ON f.document_id=d.id
               WHERE d.project_id=? AND r.relationship_type='corroborated'""",
            (project_id,),
        ).fetchone()[0]
        contradictions = conn.execute(
            """SELECT COUNT(*) FROM relationships r
               JOIN facts f ON r.source_fact_id=f.id
               JOIN documents d ON f.document_id=d.id
               WHERE d.project_id=? AND r.relationship_type='contradiction'""",
            (project_id,),
        ).fetchone()[0]
        reconciled = conn.execute(
            """SELECT COUNT(*) FROM relationships r
               JOIN facts f ON r.source_fact_id=f.id
               JOIN documents d ON f.document_id=d.id
               WHERE d.project_id=? AND r.relationship_type='reconciled'""",
            (project_id,),
        ).fetchone()[0]
    return {
        "documents": docs, "facts": facts,
        "corroborated": corroborated, "contradictions": contradictions, "reconciled": reconciled,
    }
