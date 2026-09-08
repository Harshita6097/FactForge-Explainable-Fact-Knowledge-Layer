import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.db import get_db
from agents.qa_agent import answer_question
from utils.logger import get_logger

log = get_logger("chat_api")
router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[dict]
    facts_used: int
    has_answer: bool


def _get_or_create_session(session_id: str | None) -> str:
    with get_db() as conn:
        if session_id:
            row = conn.execute(
                "SELECT id FROM chat_sessions WHERE id=?", (session_id,)
            ).fetchone()
            if row:
                return session_id

        new_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO chat_sessions (id, created_at) VALUES (?, ?)",
            (new_id, datetime.now(timezone.utc).isoformat()),
        )
        return new_id


def _save_message(session_id: str, role: str, content: str,
                  citations: list | None = None, facts_used: int = 0) -> str:
    msg_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO chat_messages
               (id, session_id, role, content, citations, facts_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id, session_id, role, content,
                json.dumps(citations or []),
                facts_used,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return msg_id


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    session_id = _get_or_create_session(request.session_id)
    log.info("Chat | session=%s | question=%s", session_id[:8], request.question[:80])

    # Save user message
    _save_message(session_id, "user", request.question)

    # Get answer from QA agent
    result = answer_question(request.question)

    # Save assistant message
    msg_id = _save_message(
        session_id, "assistant",
        result["answer"],
        result["citations"],
        result["facts_used"],
    )

    return ChatResponse(
        session_id=session_id,
        message_id=msg_id,
        answer=result["answer"],
        citations=result["citations"],
        facts_used=result["facts_used"],
        has_answer=result["has_answer"],
    )


@router.get("/chat/sessions")
def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.id, s.created_at, s.title,
                      COUNT(m.id) as message_count
               FROM chat_sessions s
               LEFT JOIN chat_messages m ON m.session_id = s.id
               GROUP BY s.id
               ORDER BY s.created_at DESC""",
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/chat/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    with get_db() as conn:
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = conn.execute(
            """SELECT id, role, content, citations, facts_used, created_at
               FROM chat_messages WHERE session_id=? ORDER BY created_at""",
            (session_id,),
        ).fetchall()

    result = []
    for m in messages:
        row = dict(m)
        row["citations"] = json.loads(row["citations"] or "[]")
        result.append(row)
    return result


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
    return {"message": "Session deleted"}
