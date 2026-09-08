"""
LLM client — fully local, no external API calls.
generate_text: not used anymore (fact extraction and relationship explanation are rule-based)
get_embedding: sentence-transformers via local_embedder
parse_json_response: kept for any legacy callers
"""
import json
import re
from utils.logger import get_logger
from services.local_embedder import get_embedding as _local_embed, get_embeddings_batch as _local_batch

log = get_logger("llm_client")


def generate_text(prompt: str, temperature: float = 0.1, max_retries: int = 1) -> str:
    """No-op — all text generation replaced with deterministic logic."""
    raise NotImplementedError("generate_text is disabled. All extraction is rule-based.")


def parse_json_response(text: str) -> list | dict:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()
    start = min(
        (text.find("[") if text.find("[") != -1 else len(text)),
        (text.find("{") if text.find("{") != -1 else len(text)),
    )
    if start == len(text):
        return []
    bracket = text[start]
    end_bracket = "]" if bracket == "[" else "}"
    end = text.rfind(end_bracket)
    if end == -1:
        return []
    return json.loads(text[start: end + 1])


def get_embedding(text: str) -> list[float]:
    return _local_embed(text)


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    return _local_batch(texts)
