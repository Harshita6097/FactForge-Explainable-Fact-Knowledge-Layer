import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from utils.config import get_settings
from utils.logger import get_logger
from database.db import init_db
from api.health import router as health_router
from api.documents import router as documents_router
from api.facts import router as facts_router
from api.relationships import router as relationships_router
from api.timeline import router as timeline_router
from api.chat import router as chat_router
from api.progress import router as progress_router
from api.knowledge import router as knowledge_router
from api.projects import router as projects_router
from api.auth import router as auth_router
from api.cases import router as cases_router

settings = get_settings()
log = get_logger("main")


def _recover_stuck_documents():
    """Reset documents stuck in transient states back to pending on startup."""
    from database.db import get_db
    stuck = ("processing", "extracted", "mining", "analyzing")
    with get_db() as conn:
        result = conn.execute(
            f"UPDATE documents SET status='pending' WHERE status IN ({','.join('?'*len(stuck))})",
            stuck,
        )
        if result.rowcount:
            log.info("Recovered %d stuck document(s) → pending", result.rowcount)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.faiss_index_dir, exist_ok=True)
    init_db()
    _recover_stuck_documents()
    log.info("FactForge API started | db=%s | uploads=%s",
             settings.database_url, settings.upload_dir)
    yield
    log.info("FactForge API shutting down")


app = FastAPI(
    title="FactForge API",
    description="Explainable Fact Knowledge Layer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(projects_router, prefix="/api", tags=["projects"])
app.include_router(documents_router, prefix="/api", tags=["documents"])
app.include_router(facts_router, prefix="/api", tags=["facts"])
app.include_router(relationships_router, prefix="/api", tags=["relationships"])
app.include_router(timeline_router, prefix="/api", tags=["timeline"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(progress_router, prefix="/api", tags=["progress"])
app.include_router(knowledge_router, prefix="/api", tags=["knowledge"])
app.include_router(cases_router, prefix="/api", tags=["cases"])


@app.get("/")
def root():
    return {"message": "FactForge API is running"}
