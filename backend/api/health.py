from fastapi import APIRouter
from database.db import get_db

router = APIRouter()


@router.get("/health")
def health_check():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "FactForge API",
        "version": "1.0.0",
        "database": db_status,
    }
