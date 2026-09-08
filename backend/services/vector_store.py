import os
import json
import numpy as np
from pathlib import Path
from typing import Optional

from utils.config import get_settings
from utils.logger import get_logger

log = get_logger("vector_store")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    log.warning("faiss-cpu not available — semantic search disabled")

settings = get_settings()

_INDEX_FILE = Path(settings.faiss_index_dir) / "facts.index"
_META_FILE = Path(settings.faiss_index_dir) / "facts_meta.json"
_DIM = 384  # all-MiniLM-L6-v2 dimension

_index: Optional[object] = None
_meta: list[dict] = []  # [{fact_id, entity, attribute, period}]


def _load_index():
    global _index, _meta
    if not FAISS_AVAILABLE:
        return
    if _INDEX_FILE.exists() and _META_FILE.exists():
        _index = faiss.read_index(str(_INDEX_FILE))
        with open(_META_FILE) as f:
            _meta = json.load(f)
        log.info("Loaded FAISS index: %d vectors", _index.ntotal)
    else:
        _index = faiss.IndexFlatIP(_DIM)  # Inner product (cosine after normalizing)
        _meta = []
        log.info("Created new FAISS index")


def _save_index():
    if not FAISS_AVAILABLE or _index is None:
        return
    Path(settings.faiss_index_dir).mkdir(exist_ok=True)
    faiss.write_index(_index, str(_INDEX_FILE))
    with open(_META_FILE, "w") as f:
        json.dump(_meta, f)
    log.debug("FAISS index saved: %d vectors", _index.ntotal)


def _normalize(vec: list[float]) -> np.ndarray:
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.reshape(1, -1)


def add_fact_embedding(fact_id: str, entity: str, attribute: str, period: Optional[str], embedding: list[float]):
    global _index, _meta
    if not FAISS_AVAILABLE:
        return
    if _index is None:
        _load_index()

    vec = _normalize(embedding)
    _index.add(vec)
    _meta.append({"fact_id": fact_id, "entity": entity, "attribute": attribute, "period": period})
    _save_index()
    log.debug("Added embedding for fact %s | total=%d", fact_id, _index.ntotal)


def search_similar(embedding: list[float], top_k: int = 10, threshold: float = 0.75) -> list[dict]:
    """Return top_k most similar facts above threshold. Returns list of {fact_id, score, ...}"""
    if not FAISS_AVAILABLE or _index is None or _index.ntotal == 0:
        return []

    vec = _normalize(embedding)
    k = min(top_k, _index.ntotal)
    scores, indices = _index.search(vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1 or float(score) < threshold:
            continue
        results.append({**_meta[idx], "score": float(score)})
    return results


def get_index_size() -> int:
    if not FAISS_AVAILABLE or _index is None:
        return 0
    return _index.ntotal


def rebuild_index_from_db():
    """Rebuild the full FAISS index from all facts in DB. Used for recovery."""
    global _index, _meta
    if not FAISS_AVAILABLE:
        return

    from database.db import get_db
    from services.local_embedder import get_embedding

    _index = faiss.IndexFlatIP(_DIM)
    _meta = []

    with get_db() as conn:
        facts = conn.execute(
            "SELECT id, entity, attribute, period, canonical_value, raw_value FROM facts"
        ).fetchall()

    log.info("Rebuilding FAISS index for %d facts", len(facts))
    for fact in facts:
        text = f"{fact['entity']} {fact['attribute']} {fact['canonical_value'] or fact['raw_value']}"
        try:
            emb = get_embedding(text)
            add_fact_embedding(fact["id"], fact["entity"], fact["attribute"], fact["period"], emb)
        except Exception as e:
            log.warning("Failed to embed fact %s: %s", fact["id"], e)

    log.info("FAISS index rebuilt: %d vectors", _index.ntotal)


# Load on module import
if FAISS_AVAILABLE:
    _load_index()
