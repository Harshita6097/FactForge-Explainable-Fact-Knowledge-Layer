from pydantic import BaseModel
from typing import Optional


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    page_count: int
    status: str
    uploaded_at: str
    processed_at: Optional[str] = None
    project_id: Optional[str] = None


class PageContent(BaseModel):
    page_number: int
    text: str
    char_count: int


class ProcessingStatus(BaseModel):
    document_id: str
    status: str
    page_count: int
    current_page: Optional[int] = None
    facts_found: int = 0
    relationships_found: int = 0
    error: Optional[str] = None
