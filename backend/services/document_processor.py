import fitz  # PyMuPDF
from pathlib import Path
from models.document import PageContent


def extract_pages(file_path: str) -> list[PageContent]:
    """Extract text from every page of a PDF, preserving page numbers."""
    pages: list[PageContent] = []
    doc = fitz.open(file_path)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                pages.append(PageContent(
                    page_number=page_num + 1,
                    text=text,
                    char_count=len(text),
                ))
    finally:
        doc.close()
    return pages


def get_page_count(file_path: str) -> int:
    doc = fitz.open(file_path)
    count = len(doc)
    doc.close()
    return count


def is_valid_pdf(file_path: str) -> bool:
    try:
        doc = fitz.open(file_path)
        valid = doc.is_pdf
        doc.close()
        return valid
    except Exception:
        return False


def extract_page_snippet(file_path: str, page_number: int, search_text: str, context_chars: int = 300) -> str:
    """Find the best matching snippet for a piece of text on a specific page."""
    doc = fitz.open(file_path)
    try:
        if page_number < 1 or page_number > len(doc):
            return search_text[:context_chars]
        page = doc[page_number - 1]
        full_text = page.get_text("text")
        idx = full_text.lower().find(search_text.lower()[:50])
        if idx == -1:
            return full_text[:context_chars].strip()
        start = max(0, idx - 50)
        end = min(len(full_text), idx + context_chars)
        return full_text[start:end].strip()
    finally:
        doc.close()
