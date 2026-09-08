from sentence_transformers import SentenceTransformer
from utils.logger import get_logger

log = get_logger("local_embedder")

_model = None
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading sentence-transformer model: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        log.info("Model loaded")
    return _model


def get_embedding(text: str) -> list[float]:
    model = _get_model()
    vec = model.encode(text[:512], normalize_embeddings=True)
    return vec.tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vecs = model.encode([t[:512] for t in texts], normalize_embeddings=True)
    return [v.tolist() for v in vecs]
