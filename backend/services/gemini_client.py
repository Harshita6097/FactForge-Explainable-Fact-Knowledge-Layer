import json
import re
import google.generativeai as genai
from utils.config import get_settings

settings = get_settings()

_model = None
_embed_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _embed_model = "models/text-embedding-004"
    return _embed_model


def generate_text(prompt: str, temperature: float = 0.1) -> str:
    """Call Gemini and return raw text response."""
    model = _get_model()
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=temperature),
    )
    return response.text.strip()


def parse_json_response(text: str) -> list | dict:
    """Robustly extract JSON from Gemini response even if wrapped in markdown."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

    # Find the first [ or { and last ] or }
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

    return json.loads(text[start : end + 1])


def get_embedding(text: str) -> list[float]:
    """Get embedding vector for a text string."""
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model=_get_embed_model(),
        content=text[:2000],  # cap to avoid token limits
        task_type="retrieval_document",
    )
    return result["embedding"]


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts."""
    return [get_embedding(t) for t in texts]
