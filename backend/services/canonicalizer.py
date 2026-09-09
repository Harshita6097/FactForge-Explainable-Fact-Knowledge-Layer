import re
from typing import Optional
from utils.logger import get_logger

log = get_logger("canonicalizer")

# ---------------------------------------------------------------------------
# Numeric unit multipliers — convert everything to a base unit
# ---------------------------------------------------------------------------
_UNIT_MULTIPLIERS: dict[str, float] = {
    "crore": 1e7,
    "cr": 1e7,
    "cr.": 1e7,
    "lakh": 1e5,
    "lac": 1e5,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "billion": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "trillion": 1e12,
    "tn": 1e12,
    "thousand": 1e3,
    "k": 1e3,
}

# Currency symbols to normalize
_CURRENCY_MAP: dict[str, str] = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "$": "USD",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}

# ---------------------------------------------------------------------------
# Semantic attribute aliases — maps variants → canonical attribute name
# Only applied when context strongly supports equivalence
# ---------------------------------------------------------------------------
_ATTRIBUTE_ALIASES: dict[str, str] = {
    "turnover": "Revenue",
    "net revenue": "Revenue",
    "total revenue": "Revenue",
    "sales": "Revenue",
    "sales income": "Revenue",
    "income from operations": "Revenue",
    "net sales": "Revenue",
    "gross revenue": "Revenue",
    "total income": "Revenue",
    "net profit": "Net Income",
    "profit after tax": "Net Income",
    "pat": "Net Income",
    "net earnings": "Net Income",
    "profit before tax": "PBT",
    "pbt": "PBT",
    "ebitda margin": "EBITDA Margin",
    "operating margin": "Operating Margin",
    "operating profit margin": "Operating Margin",
    "headcount": "Employees",
    "total employees": "Employees",
    "workforce": "Employees",
    "staff strength": "Employees",
    "number of employees": "Employees",
    "gdp growth": "GDP Growth Rate",
    "gdp growth rate": "GDP Growth Rate",
    "economic growth": "GDP Growth Rate",
    "real gdp growth": "GDP Growth Rate",
    "inflation rate": "Inflation",
    "cpi inflation": "Inflation",
    "consumer price inflation": "Inflation",
    "wpi inflation": "WPI Inflation",
    "repo rate": "Repo Rate",
    "policy rate": "Repo Rate",
    "chief executive officer": "CEO",
    "managing director": "MD",
    "chief financial officer": "CFO",
    "market capitalisation": "Market Cap",
    "market capitalization": "Market Cap",
    "mcap": "Market Cap",
}

# ---------------------------------------------------------------------------
# Period normalization patterns
# ---------------------------------------------------------------------------
_FY_SHORT = re.compile(r"\bfy\s*(\d{2})\b", re.IGNORECASE)
_FY_LONG = re.compile(r"\bfy\s*(\d{4})\b", re.IGNORECASE)
_FY_RANGE = re.compile(r"\bfy\s*(\d{4})[/-](\d{2,4})\b", re.IGNORECASE)
_Q_PERIOD = re.compile(r"\bq([1-4])\s*fy\s*(\d{2,4})\b", re.IGNORECASE)
_YEAR_ONLY = re.compile(r"\b(19|20)(\d{2})\b")
_YEAR_RANGE = re.compile(r"\b(20\d{2})[/-](20\d{2}|\d{2})\b")

# Relative/vague period strings that must not be stored as canonical periods
_RELATIVE_PERIOD_RE = re.compile(
    r'\b(this year|last year|next year|recent(?:ly)?|annually?|seasonal(?:ly)?|'
    r'one.month.ahead|short.term|long.term|recent decades|'
    r'historically|over time|in the past|going forward|near term|medium term)\b',
    re.IGNORECASE,
)


def normalize_period(period: Optional[str]) -> Optional[str]:
    """Normalize period strings to a canonical form."""
    if not period:
        return period

    p = period.strip()

    # Reject relative/vague periods immediately
    if _RELATIVE_PERIOD_RE.search(p):
        return None
    # Q1 FY24 → Q1 FY2024
    m = _Q_PERIOD.search(p)
    if m:
        q, yr = m.group(1), m.group(2)
        yr = _expand_year(yr)
        return f"Q{q} FY{yr}"

    # FY2023-24 → FY2024 (must check range BEFORE plain FY)
    m = _FY_RANGE.search(p)
    if m:
        base = m.group(1)
        end = m.group(2)
        if len(end) == 2:
            end = base[:2] + end
        return f"FY{end}"

    # FY24 → FY2024
    m = _FY_SHORT.search(p)
    if m:
        yr = _expand_year(m.group(1))
        return f"FY{yr}"

    # FY2024 already canonical
    m = _FY_LONG.search(p)
    if m:
        return f"FY{m.group(1)}"

    # 2024-25 → FY2025
    m = _YEAR_RANGE.search(p)
    if m:
        base = m.group(1)
        end = m.group(2)
        if len(end) == 2:
            end = base[:2] + end
        return f"FY{end}"

    return p


def _expand_year(yr: str) -> str:
    """Convert 2-digit year to 4-digit: 24 → 2024."""
    if len(yr) == 2:
        n = int(yr)
        return f"20{yr}" if n <= 50 else f"19{yr}"
    return yr


# ---------------------------------------------------------------------------
# Value + unit normalization
# ---------------------------------------------------------------------------
_NUMBER_RE = re.compile(r"[\d,]+\.?\d*")


def _parse_number(value: str) -> Optional[float]:
    """Extract the first number from a string."""
    clean = value.replace(",", "")
    m = _NUMBER_RE.search(clean)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


# Bibliographic/artifact value patterns that must not be stored
_BIBLIO_VALUE_RE = re.compile(
    r'^\d{4,5}$'        # bare 4-5 digit number (volume/page number)
    r'|\d+\(\d+\):\d+'  # journal citation format e.g. 83(6):2411
    r'|^[A-Z]\d+$'      # e.g. "B3475"
)


def normalize_value(raw_value: str, unit: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (canonical_value, canonical_unit).
    Converts crore/lakh/million/billion to a base numeric string.
    Normalizes currency symbols.
    """
    if not raw_value:
        return None, unit

    # Reject bibliographic artifacts before any numeric processing
    if _BIBLIO_VALUE_RE.match(raw_value.strip()):
        return None, None

    unit_lower = (unit or "").lower().strip()
    value_lower = raw_value.lower().strip()

    # Detect currency prefix in value string (e.g. "₹8,450 Crore")
    canonical_currency = None
    for sym, canon in _CURRENCY_MAP.items():
        if sym in value_lower or (unit_lower and sym in unit_lower):
            canonical_currency = canon
            break

    # Detect multiplier in unit or value
    multiplier = 1.0
    canonical_unit = unit

    for word, mult in _UNIT_MULTIPLIERS.items():
        if word in unit_lower or word in value_lower:
            multiplier = mult
            # Build canonical unit label
            if canonical_currency:
                canonical_unit = f"{canonical_currency} ({_multiplier_label(mult)})"
            else:
                canonical_unit = _multiplier_label(mult)
            break
    else:
        # No multiplier found — just normalize currency in unit
        if canonical_currency and unit:
            canonical_unit = canonical_currency

    num = _parse_number(raw_value)
    if num is None:
        return None, canonical_unit

    if multiplier != 1.0:
        canonical_value = f"{num * multiplier:,.0f}"
    else:
        canonical_value = f"{num:g}"

    return canonical_value, canonical_unit


def _multiplier_label(mult: float) -> str:
    labels = {1e3: "Thousands", 1e5: "Lakhs", 1e6: "Millions",
               1e7: "Crores", 1e9: "Billions", 1e12: "Trillions"}
    return labels.get(mult, str(mult))


# ---------------------------------------------------------------------------
# Attribute canonicalization
# ---------------------------------------------------------------------------
def canonicalize_attribute(attribute: str) -> str:
    """Map attribute variants to canonical names using alias table."""
    key = attribute.lower().strip()
    canonical = _ATTRIBUTE_ALIASES.get(key)
    if canonical:
        log.debug("Attribute alias: '%s' → '%s'", attribute, canonical)
        return canonical
    # Title-case the attribute for consistency
    return attribute.strip().title()


# ---------------------------------------------------------------------------
# Dynamic attribute registry — discovers new attributes automatically
# ---------------------------------------------------------------------------
def register_attribute(attribute: str) -> None:
    """
    Register a newly discovered attribute in the DB.
    This is how the schema evolves dynamically — no hardcoded list.
    """
    from database.db import get_db
    canonical = canonicalize_attribute(attribute)
    with get_db() as conn:
        existing = conn.execute(
            "SELECT attribute FROM attribute_registry WHERE attribute=?",
            (attribute.strip(),)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE attribute_registry SET occurrence_count = occurrence_count + 1 WHERE attribute=?",
                (attribute.strip(),)
            )
        else:
            conn.execute(
                """INSERT INTO attribute_registry (attribute, canonical_attribute, first_seen)
                   VALUES (?, ?, datetime('now'))""",
                (attribute.strip(), canonical),
            )
            log.info("New attribute discovered: '%s' → '%s'", attribute, canonical)


# ---------------------------------------------------------------------------
# Main entry point — canonicalize a full fact
# ---------------------------------------------------------------------------
def canonicalize_fact(
    entity: str,
    attribute: str,
    raw_value: str,
    unit: Optional[str],
    period: Optional[str],
) -> dict:
    """
    Returns a dict with canonical_attribute, canonical_value, canonical_unit, canonical_period.
    """
    canonical_attribute = canonicalize_attribute(attribute)
    canonical_value, canonical_unit = normalize_value(raw_value, unit)
    canonical_period = normalize_period(period)

    log.debug(
        "Canonicalized | entity=%s | attr=%s→%s | value=%s→%s | period=%s→%s",
        entity, attribute, canonical_attribute,
        raw_value, canonical_value,
        period, canonical_period,
    )

    return {
        "canonical_attribute": canonical_attribute,
        "canonical_value": canonical_value,
        "canonical_unit": canonical_unit,
        "canonical_period": canonical_period,
    }
