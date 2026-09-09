import re
import spacy
from utils.logger import get_logger

log = get_logger("rule_extractor")

_nlp = None

# Sentences matching these patterns are skipped before any extraction
_SKIP_SENTENCE_RE = re.compile(
    r"""
    ^\d+$                                      # bare page/volume number
    |\d+\(\d+\):\d+[-–]\d+                    # journal citation e.g. 83(6):2411-2451
    |^[\d/\s]+Data\b                           # table header artifact e.g. "1/ Data"
    |^\s*\d+\s*/\s*\w                          # "3 / Something"
    |\b(?:ibid|op\.?\s*cit|et\s+al\.?|pp?\.\s*\d)  # bibliographic markers
    """,
    re.IGNORECASE | re.VERBOSE,
)

# DATE entity values that are relative/vague — not absolute periods
_RELATIVE_DATE_TERMS = frozenset([
    "this year", "last year", "next year", "recent", "recently",
    "seasonally", "annual", "annually", "one-month-ahead", "short-term",
    "long-term", "recent decades", "historically", "over time",
    "in the past", "going forward", "near term", "medium term",
])

# Entity strings that look like bibliographic artifacts
_BIBLIO_ENTITY_RE = re.compile(
    r'^\d+$'           # pure number
    r'|\d+\(\d+\)'     # volume(issue) format
    r'|^[A-Z]{1,3}\d'  # e.g. "B3", "IMF2"
    r'|\d+[-–]\d{4,}'  # page range
)

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


# Sentences that describe demographic, geographic, or disaster impact data
# — must not be reclassified as employee counts or financial metrics
_DEMOGRAPHIC_RE = re.compile(
    r'\b(urban|rural|household|houses?\s+damaged|families|population|district|village|'
    r'beneficiar|flood|cyclone|drought|disaster|affected\s+area|crop\s+loss|'
    r'mortality|morbidity|literacy|poverty|below\s+poverty)\b',
    re.IGNORECASE,
)

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


def _detect_attribute_for_match(sentence: str, match_start: int, match_end: int) -> str:
    """
    Detect attribute using only the clause immediately surrounding a numeric match.
    Looks at a 120-char window centred on the match to avoid associating a number
    with a header or category name from a different part of the sentence.
    """
    window_start = max(0, match_start - 80)
    window_end = min(len(sentence), match_end + 40)
    clause = sentence[window_start:window_end]
    attr = _detect_attribute(clause)
    # Fall back to full sentence if clause gives no signal
    return attr if attr != "Metric" else _detect_attribute(sentence)


def _is_absolute_date(date_text: str) -> bool:
    """Return True only if the date resolves to a specific year/period."""
    lower = date_text.lower().strip()
    if any(term in lower for term in _RELATIVE_DATE_TERMS):
        return False
    return bool(re.search(r'\b(19|20)\d{2}\b|fy\s*\d{2,4}|q[1-4]\s*fy', lower, re.IGNORECASE))


def _detect_period(sentence: str) -> str | None:
    m = _PERIOD_RE.search(sentence)
    if m:
        return m.group(0).strip()
    return None


def _get_sentences(text: str) -> list[str]:
    nlp = _get_nlp()
    doc = nlp(text[:50000])
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]


# Words that must never be returned as an entity name from the proper-noun fallback
_ENTITY_SKIP = frozenset([
    "the", "a", "an", "this", "that", "these", "those", "its", "their",
    "net", "gross", "total", "operating", "adjusted", "reported", "based",
    "profit", "loss", "revenue", "income", "ebitda", "margin", "growth",
    "sales", "cost", "expense", "asset", "liability", "equity", "cash",
    "debt", "capex", "dividend", "share", "stock", "return", "rate",
    "quarter", "annual", "fiscal", "year", "period", "date", "page",
    "india", "indian",  # too generic for financial docs — kept as GPE only
])


def _extract_entity_from_sentence(
    sent_doc,
    doc_orgs: list[str],
    sentence: str,
    doc_entity_hint: str | None = None,
) -> str | None:
    """Return the most relevant ORG or PERSON entity from a sentence."""
    # 1. spaCy NER
    for ent in sent_doc.ents:
        if ent.label_ in ("ORG", "PERSON", "GPE"):
            return ent.text.strip()
    # 2. Document-level entity hint (injected from PDF metadata/heading)
    if doc_entity_hint:
        hint_lower = doc_entity_hint.lower()
        if hint_lower in sentence.lower():
            return doc_entity_hint
        # Even if not literally present, use as fallback before generic ORGs
        return doc_entity_hint
    # 3. Most frequent ORG across the full page
    if doc_orgs:
        return doc_orgs[0]
    # 4. Last resort: first capitalized proper noun, with strict skip list
    for m in _PROPER_NOUN_RE.finditer(sentence):
        word = m.group(1)
        if word.lower() not in _ENTITY_SKIP and len(word) > 2:
            return word
    return None


def _extract_facts_from_sentence(
    sentence: str,
    page_number: int,
    doc_orgs: list[str],
    doc_entity_hint: str | None = None,
) -> list[dict]:
    # Skip demographic/geographic/disaster sentences — do not reclassify as
    # employee counts or financial metrics (anti-hallucination rule)
    if _DEMOGRAPHIC_RE.search(sentence):
        return []

    nlp = _get_nlp()
    sent_doc = nlp(sentence)
    facts = []
    period = _detect_period(sentence)
    entity = _extract_entity_from_sentence(sent_doc, doc_orgs, sentence, doc_entity_hint)

    if not entity or _BIBLIO_ENTITY_RE.search(entity):
        return []

    snippet = re.sub(r'\s+', ' ', sentence[:300]).strip()

    # Money + unit matches — attribute scoped to clause around the match
    for m in _MONEY_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = m.group(2).strip()
        attribute = _detect_attribute_for_match(sentence, m.start(), m.end())
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.88,
            "snippet": snippet,
            "page_number": page_number,
        })

    # Percentage matches
    for m in _PERCENT_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = "%"
        attribute = _detect_attribute_for_match(sentence, m.start(), m.end())
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.85,
            "snippet": snippet,
            "page_number": page_number,
        })

    # Plain numeric with operational units
    for m in _PLAIN_NUM_RE.finditer(sentence):
        raw_value = m.group(0).strip()
        unit = m.group(2).strip()
        attribute = _detect_attribute_for_match(sentence, m.start(), m.end())
        facts.append({
            "entity": entity,
            "attribute": attribute,
            "raw_value": raw_value,
            "unit": unit,
            "period": period,
            "confidence": 0.80,
            "snippet": snippet,
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
                    "snippet": snippet,
                    "page_number": page_number,
                })

    # Fallback: if no numeric facts found, extract entity-relationship facts
    # This handles non-financial PDFs (e.g. general reports, presentations)
    if not facts and entity:
        lower = sentence.lower()
        # Location facts
        for ent in sent_doc.ents:
            if ent.label_ == "GPE" and ent.text.strip() != entity:
                facts.append({
                    "entity": entity,
                    "attribute": "Location",
                    "raw_value": ent.text.strip(),
                    "unit": None,
                    "period": period,
                    "confidence": 0.70,
                    "snippet": sentence[:300],
                    "page_number": page_number,
                })
                break
        # Date facts — only accept absolute, resolvable dates
        for ent in sent_doc.ents:
            if ent.label_ == "DATE" and not period and _is_absolute_date(ent.text):
                facts.append({
                    "entity": entity,
                    "attribute": "Date",
                    "raw_value": ent.text.strip(),
                    "unit": None,
                    "period": ent.text.strip(),
                    "confidence": 0.65,
                    "snippet": snippet,
                    "page_number": page_number,
                })
                break
        # Key statement facts — sentences with ORG + action verbs
        if not facts and len(sentence) > 30:
            action_kws = ["provides", "offers", "operates", "develops", "manufactures",
                          "launched", "announced", "partnered", "acquired", "raised",
                          "aims", "focuses", "specializes", "serves", "supports"]
            if any(kw in lower for kw in action_kws):
                attr = _detect_attribute(sentence)
                if attr == "Metric":
                    attr = "Description"
                facts.append({
                    "entity": entity,
                    "attribute": attr,
                    "raw_value": re.sub(r'\s+', ' ', sentence[:150]).strip(),
                    "unit": None,
                    "period": period,
                    "confidence": 0.60,
                    "snippet": snippet,
                    "page_number": page_number,
                })

    return facts


def extract_facts_from_page(
    text: str,
    page_number: int,
    doc_entity_hint: str | None = None,
) -> list[dict]:
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
        if _SKIP_SENTENCE_RE.search(sentence):
            continue
        for fact in _extract_facts_from_sentence(sentence, page_number, doc_orgs, doc_entity_hint):
            key = f"{fact['entity']}|{fact['attribute']}|{fact['raw_value']}"
            if key not in seen:
                seen.add(key)
                facts.append(fact)

    log.debug("Page %d: extracted %d facts", page_number, len(facts))
    return facts


def extract_facts_from_pages(
    pages: list[dict],
    doc_entity_hint: str | None = None,
) -> list[dict]:
    """Extract facts from a batch of pages."""
    all_facts = []
    for page in pages:
        facts = extract_facts_from_page(page["text"], page["page_number"], doc_entity_hint)
        all_facts.extend(facts)
    return all_facts
