import re
import spacy
from utils.logger import get_logger

log = get_logger("rule_extractor")

_nlp = None

# Patterns for numeric values with units
_MONEY_RE = re.compile(
    r"(?:₹|Rs\.?\s*|INR\s*|USD\s*|\$\s*)?(\d[\d,]*\.?\d*)\s*"
    r"(crore|lakh|million|billion|thousand|cr\b|mn\b|bn\b)",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*(%|percent|bps|basis points)", re.IGNORECASE)
_PLAIN_NUM_RE = re.compile(r"\b(\d[\d,]*\.?\d*)\s*(units?|tonnes?|kg|km|sqft|sq\.?\s*ft|employees?|warehouses?|centers?|shipments?|orders?|users?|customers?|stores?|cities|pins?|pincodes?)\b", re.IGNORECASE)

# Period patterns
_PERIOD_RE = re.compile(
    r"\b(FY\s*\d{2,4}(?:[–\-]\d{2,4})?|Q[1-4]\s*(?:FY)?\s*\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}|"
    r"H[12]\s*(?:FY)?\s*\d{2,4}|(?:19|20)\d{2}(?:[–\-]\d{2,4})?)\b",
    re.IGNORECASE,
)

# Attribute keyword mapping — sentence keywords → canonical attribute name
_ATTR_KEYWORDS = [
    (["revenue", "turnover", "income from operations", "net sales"], "Revenue"),
    (["ebitda"], "EBITDA"),
    (["ebit"], "EBIT"),
    (["net profit", "net income", "pat", "profit after tax"], "Net Profit"),
    (["gross profit"], "Gross Profit"),
    (["pbt", "profit before tax"], "PBT"),
    (["operating profit"], "Operating Profit"),
    (["market cap", "market capitalisation", "market capitalization"], "Market Cap"),
    (["employee", "headcount", "staff", "workforce", "people"], "Employees"),
    (["warehouse", "fulfillment center", "fulfilment center", "facility", "facilities"], "Warehouses"),
    (["shipment", "parcel", "delivery", "order"], "Shipments"),
    (["customer", "client", "merchant", "seller"], "Customers"),
    (["city", "cities", "location", "pin", "pincode", "serviceable"], "Coverage"),
    (["founded", "incorporated", "established"], "Founded"),
    (["ceo", "chief executive", "managing director", "md"], "CEO"),
    (["cfo", "chief financial"], "CFO"),
    (["chairman"], "Chairman"),
    (["growth", "yoy", "year-on-year", "increase", "decline", "decrease"], "Growth Rate"),
    (["margin"], "Margin"),
    (["debt", "borrowing", "loan"], "Debt"),
    (["cash", "liquidity"], "Cash"),
    (["capex", "capital expenditure"], "Capex"),
    (["dividend"], "Dividend"),
    (["ipo", "listing"], "IPO"),
    (["share", "stock", "equity"], "Share Price"),
    (["return", "roe", "roce", "roa"], "Returns"),
    (["asset"], "Assets"),
    (["liability"], "Liabilities"),
]


# Capitalized word that looks like a proper noun (company/person name)
_PROPER_NOUN_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')


def _get_nlp():
    global _nlp
    if _nlp is None:
        log.info("Loading spaCy model")
        _nlp = spacy.load("en_core_web_sm")
        log.info("spaCy model loaded")
    return _nlp


def _detect_attribute(sentence: str) -> str:
    lower = sentence.lower()
    for keywords, attr in _ATTR_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return attr
    return "Metric"


def _detect_period(sentence: str) -> str | None:
    m = _PERIOD_RE.search(sentence)
    if m:
        return m.group(0).strip()
    return None


def _get_sentences(text: str) -> list[str]:
    nlp = _get_nlp()
    doc = nlp(text[:50000])
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]


def _extract_entity_from_sentence(sent_doc, doc_orgs: list[str], sentence: str) -> str | None:
    """Return the most relevant ORG or PERSON entity from a sentence."""
    for ent in sent_doc.ents:
        if ent.label_ in ("ORG", "PERSON", "GPE"):
            return ent.text.strip()
    # Fall back to most frequent ORG in the document
    if doc_orgs:
        return doc_orgs[0]
    # Last resort: first capitalized proper noun in sentence
    m = _PROPER_NOUN_RE.search(sentence)
    if m:
        word = m.group(1)
        skip = {"the", "a", "an", "this", "that", "these", "those", "its", "their",
                "net", "gross", "total", "operating", "adjusted", "reported", "based"}
        if word.lower() not in skip and len(word) > 2:
            return word
    return None


def _extract_facts_from_sentence(
    sentence: str,
    page_number: int,
    doc_orgs: list[str],
) -> list[dict]:
    nlp = _get_nlp()
    sent_doc = nlp(sentence)
    facts = []
    period = _detect_period(sentence)
    attribute = _detect_attribute(sentence)
    entity = _extract_entity_from_sentence(sent_doc, doc_orgs, sentence)

    if not entity:
        return []

    # Money + unit matches
    for m in _MONEY_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = m.group(2).strip()
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.88,
            "snippet": sentence[:300],
            "page_number": page_number,
        })

    # Percentage matches
    for m in _PERCENT_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = "%"
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.85,
            "snippet": sentence[:300],
            "page_number": page_number,
        })

    # Plain numeric with operational units
    for m in _PLAIN_NUM_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = m.group(2).strip()
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.80,
            "snippet": sentence[:300],
            "page_number": page_number,
        })

    # Named entity facts (CEO, Chairman, etc.) — no numeric value needed
    for ent in sent_doc.ents:
        if ent.label_ == "PERSON" and ent.text.strip() != entity:
            attr = _detect_attribute(sentence)
            if attr in ("CEO", "CFO", "Chairman") or any(
                kw in sentence.lower() for kw in ["appointed", "joined", "named", "is the", "serves as"]
            ):
                facts.append({
                    "entity": entity,
                    "attribute": attr,
                    "raw_value": ent.text.strip(),
                    "unit": None,
                    "period": period,
                    "confidence": 0.75,
                    "snippet": sentence[:300],
                    "page_number": page_number,
                })

    return facts


def extract_facts_from_page(text: str, page_number: int) -> list[dict]:
    """Extract structured facts from a single page of text."""
    nlp = _get_nlp()
    doc = nlp(text[:50000])

    # Collect dominant ORGs across the whole page for entity fallback
    org_counts: dict[str, int] = {}
    for ent in doc.ents:
        if ent.label_ in ("ORG", "GPE"):
            org_counts[ent.text.strip()] = org_counts.get(ent.text.strip(), 0) + 1
    doc_orgs = sorted(org_counts, key=lambda x: -org_counts[x])

    facts = []
    seen: set[str] = set()

    for sent in doc.sents:
        sentence = sent.text.strip()
        if len(sentence) < 15:
            continue
        for fact in _extract_facts_from_sentence(sentence, page_number, doc_orgs):
            key = f"{fact['entity']}|{fact['attribute']}|{fact['raw_value']}"
            if key not in seen:
                seen.add(key)
                facts.append(fact)

    log.debug("Page %d: extracted %d facts", page_number, len(facts))
    return facts


def extract_facts_from_pages(pages: list[dict]) -> list[dict]:
    """Extract facts from a batch of pages."""
    all_facts = []
    for page in pages:
        facts = extract_facts_from_page(page["text"], page["page_number"])
        all_facts.extend(facts)
    return all_facts
