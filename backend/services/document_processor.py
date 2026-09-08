import fitz  # PyMuPDF
from pathlib import Path
from models.document import PageContent
from utils.logger import get_logger

log = get_logger("document_processor")


def _extract_tables_as_text(page) -> str:
    """Extract tables from a page using PyMuPDF's table finder and format as text."""
    try:
        tabs = page.find_tables()
        if not tabs or not tabs.tables:
            return ""
        parts = []
        for table in tabs.tables:
            rows = table.extract()
            if not rows:
                continue
            # Format: header row + data rows as pipe-separated text
            formatted = []
            for row in rows:
                cells = [str(c).strip() if c is not None else "" for c in row]
                formatted.append(" | ".join(cells))
            parts.append("[TABLE]\n" + "\n".join(formatted) + "\n[/TABLE]")
        return "\n\n".join(parts)
    except Exception:
        return ""


def extract_pages(file_path: str) -> list[PageContent]:
    """Extract text from every page of a PDF, preserving page numbers."""
    pages: list[PageContent] = []
    doc = fitz.open(file_path)
    log.info("Extracting pages from %s", file_path)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            table_text = _extract_tables_as_text(page)
            # Append table text after regular text so Gemini sees structured data
            if table_text:
                text = text + "\n\n" + table_text if text else table_text
            if text:
                pages.append(PageContent(
                    page_number=page_num + 1,
                    text=text,
                    char_count=len(text),
                ))
    finally:
        doc.close()
    log.info("Extracted %d non-empty pages from %s", len(pages), file_path)
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
