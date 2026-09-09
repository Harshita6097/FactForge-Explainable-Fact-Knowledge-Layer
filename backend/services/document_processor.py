import re
import fitz  # PyMuPDF
from pathlib import Path
from models.document import PageContent
from utils.logger import get_logger

log = get_logger("document_processor")

# Words that are never a primary entity name
_HEADING_SKIP = frozenset([
    "annual", "report", "limited", "private", "public", "incorporated",
    "prospectus", "results", "presentation", "earnings", "quarterly",
    "financial", "statements", "excerpt", "summary", "overview",
    "the", "a", "an", "and", "of", "for", "in", "on", "at", "to",
    "fy", "q1", "q2", "q3", "q4", "h1", "h2",
])


def extract_primary_entity(file_path: str) -> str | None:
    """
    Extract the most likely primary entity (company/org name) from a PDF.
    Strategy:
      1. PDF metadata title field
      2. First non-trivial heading line on page 1
    Returns None if nothing useful found.
    """
    try:
        doc = fitz.open(file_path)
        # 1. Metadata title
        title = (doc.metadata or {}).get("title", "").strip()
        if title and len(title) > 3 and not title.isdigit():
            doc.close()
            # Strip common suffixes like "Annual Report FY2024"
            clean = re.split(r'\s*[-–|:]\s*', title)[0].strip()
            if len(clean) > 3:
                log.info("Entity hint from metadata: '%s'", clean)
                return clean

        # 2. First page — find the largest/first bold-looking line
        if len(doc) > 0:
            page = doc[0]
            blocks = page.get_text("dict")["blocks"]
            candidates = []
            for block in blocks:
                if block.get("type") != 0:  # text block
                    continue
                for line in block.get("lines", []):
                    text = " ".join(s["text"] for s in line.get("spans", [])).strip()
                    if not text or len(text) < 4 or len(text) > 80:
                        continue
                    # Must start with a capital letter and contain mostly letters
                    if not re.match(r'^[A-Z]', text):
                        continue
                    words = text.split()
                    skip_count = sum(1 for w in words if w.lower() in _HEADING_SKIP)
                    if skip_count / max(len(words), 1) > 0.5:
                        continue
                    # Prefer lines where most words are capitalized (title case)
                    cap_count = sum(1 for w in words if w and w[0].isupper())
                    if cap_count / max(len(words), 1) >= 0.5:
                        avg_size = sum(s.get("size", 10) for s in line.get("spans", [])) / max(len(line.get("spans", [])), 1)
                        candidates.append((avg_size, text))
            if candidates:
                # Pick the line with the largest font size
                best = max(candidates, key=lambda x: x[0])[1]
                log.info("Entity hint from first page heading: '%s'", best)
                doc.close()
                return best
        doc.close()
    except Exception as e:
        log.warning("Entity hint extraction failed: %s", e)
    return None


def _extract_tables_as_text(page) -> str:
    """
    Extract tables from a page and convert them to natural-language sentences
    that the rule extractor can parse (entity + attribute + value + period).
    Format: "<row_header> <col_header> is <value>."
    """
    try:
        tabs = page.find_tables()
        if not tabs or not tabs.tables:
            return ""
        parts = []
        for table in tabs.tables:
            rows = table.extract()
            if not rows or len(rows) < 2:
                continue

            # First row is the header row
            headers = [str(c).strip() if c else "" for c in rows[0]]

            sentences = []
            for row in rows[1:]:
                cells = [str(c).strip() if c is not None else "" for c in row]
                if not cells or not cells[0]:
                    continue
                row_label = cells[0]  # e.g. "Revenue", "EBITDA"
                for col_idx, cell_val in enumerate(cells[1:], start=1):
                    if not cell_val or cell_val in ("-", "N/A", "nil", "—"):
                        continue
                    col_header = headers[col_idx] if col_idx < len(headers) else ""
                    if col_header:
                        # Emit as a parseable sentence
                        sentences.append(
                            f"{row_label} {col_header} is {cell_val}."
                        )
                    else:
                        sentences.append(f"{row_label} value is {cell_val}.")

            if sentences:
                parts.append("\n".join(sentences))

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
