from pydantic import BaseModel, Field
from typing import Optional, Any


class RawExtractedFact(BaseModel):
    """Shape Gemini returns for each fact."""
    entity: str
    attribute: str
    raw_value: str
    unit: Optional[str] = None
    period: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    snippet: str
    page_number: Optional[int] = None


class FactResponse(BaseModel):
    id: str
    document_id: str
    entity: str
    attribute: str
    canonical_value: Optional[str] = None
    raw_value: str
    unit: Optional[str] = None
    period: Optional[str] = None
    confidence: float
    created_at: str


class EvidenceResponse(BaseModel):
    id: str
    fact_id: str
    document_id: str
    page_number: int
    snippet: str
    document_name: Optional[str] = None


class FactWithEvidence(FactResponse):
    evidence: list[EvidenceResponse] = []
    confidence_breakdown: list[dict[str, Any]] = []
