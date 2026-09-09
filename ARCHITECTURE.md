# FactForge — Architecture

## System Overview

FactForge is a local-first fact knowledge layer. Every extracted fact is a first-class object with identity, canonical form, source evidence, confidence score, and cross-document relationships. The system is designed to be LLM-ready — the data model, API surface, and prompt templates are all in place — but the current runtime is fully deterministic with no external API calls.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 15)                 │
│  Dashboard · Upload · Facts · Relationships · Timeline · Chat│
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP + SSE
┌────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend                          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐  │
│  │ documents│  │  facts   │  │relationships│  │  chat    │  │
│  │ projects │  │ timeline │  │  knowledge  │  │  cases   │  │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘  └────┬─────┘  │
│       │              │              │               │        │
│  ┌────▼──────────────▼──────────────▼───────────────▼─────┐ │
│  │                    Services Layer                        │ │
│  │                                                          │ │
│  │  document_processor  →  rule_extractor  →  canonicalizer│ │
│  │         ↓                                               │ │
│  │     fact_miner  →  incremental_indexer                  │ │
│  │         ↓                                               │ │
│  │   local_embedder  →  vector_store (FAISS)               │ │
│  │         ↓                                               │ │
│  │  relationship_engine  →  knowledge_layer                │ │
│  │         ↓                                               │ │
│  │    timeline_service        qa_agent                     │ │
│  └──────────────────────────────────────────────────────── ┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────── ┐ │
│  │              SQLite (WAL) + FAISS Index                  │ │
│  └──────────────────────────────────────────────────────── ┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Processing Pipeline (per document)

```
1. Upload PDF
   └─ PyMuPDF extracts text page-by-page, preserving page numbers
   └─ Pages stored in document_pages with processed=0

2. Extraction (rule_extractor.py)
   └─ Demographic guard — skip population/disaster sentences
   └─ spaCy NER → entity candidates (ORG, PERSON, GPE)
   └─ Three-level entity fallback if spaCy misses domain names
   └─ Regex patterns → numeric matches (money, %, operational units)
   └─ Clause-scoped attribute detection (80-char window per match)
   └─ Period detection (FY2024, Q3 FY24, H1 2024, March 2024)

3. Canonicalization (canonicalizer.py)
   └─ Units: 2192 crore → 21920000000
   └─ Periods: FY24 / FY 2024 / 2023-24 → FY2024
   └─ Attributes: turnover / net sales → Revenue

4. Deduplication (incremental_indexer.py)
   └─ Fingerprint: entity|attribute|value|period
   └─ Skip if fingerprint already exists for this document

5. Storage
   └─ facts table: entity, attribute, canonical_value, period, confidence
   └─ evidence table: page_number, snippet, document_id → fact_id

6. Embedding (local_embedder.py)
   └─ sentence-transformers all-MiniLM-L6-v2 (384-dim)
   └─ Persisted to FAISS index on disk

7. Relationship Detection (relationship_engine.py)
   └─ FAISS similarity search → candidate fact pairs
   └─ Four-criteria enforcement:
       entity match → attribute match → period match → unit compatibility
   └─ Value comparison with per-attribute tolerance
   └─ Classification: corroborated / contradiction / reconciled / related
   └─ Reasoning chain stored in relationship_reasoning

8. Knowledge Layer (knowledge_layer.py)
   └─ canonical_facts: merged view across documents
   └─ Conflict count updated per canonical fact
```

---

## Data Model

### Core Tables

**facts**
```
id, document_id, entity, attribute, raw_value, canonical_value,
unit, period, confidence, fingerprint, created_at
```

**evidence**
```
id, fact_id, document_id, page_number, snippet
```

**relationships**
```
id, fact_a_id, fact_b_id, relationship_type, confidence,
value_a, value_b, unit_a, unit_b, created_at
```

**relationship_reasoning**
```
id, relationship_id, step_number, step_name, step_result, detail
```

**canonical_facts**
```
id, entity, attribute, canonical_value, unit, period,
occurrence_count, conflict_count, last_updated
```

---

## Relationship Detection Logic

```python
# All four criteria must pass before any classification
entity_match     = normalize(fact_a.entity) == normalize(fact_b.entity)
attribute_match  = fact_a.attribute == fact_b.attribute
period_match     = normalize_period(fact_a.period) == normalize_period(fact_b.period)
units_compatible = _unit_type(fact_a.unit) == _unit_type(fact_b.unit)

if not (entity_match and attribute_match and units_compatible):
    → related (different entity or attribute) or skip

if entity_match and attribute_match and not period_match:
    → reconciled (temporal change)

if entity_match and attribute_match and period_match and units_compatible:
    delta = abs(val_a - val_b) / max(val_a, val_b)
    if delta <= tolerance[attribute]:
        → corroborated
    else:
        → contradiction
```

Per-attribute tolerances:
- Financial figures (Revenue, EBITDA, etc.): 5%
- Headcount (Employees): exact match (0%)
- Macroeconomic rates (GDP Growth, Inflation): 0.1–0.2%

---

## Intended LLM Architecture (not yet implemented)

The `prompts/` directory contains the templates for the intended LLM layer:

**fact_extraction.py** — System prompt for per-page fact extraction:
```
Given this page of text, extract all facts as JSON:
[{ entity, attribute, value, unit, period, confidence, evidence_snippet }]
Rules: only extract explicitly stated values, one fact per numeric claim...
```

**relationship_prompts.py** — System prompt for relationship classification:
```
Given these two facts, classify their relationship and explain your reasoning...
```

**chat_prompts.py** — System prompt for knowledge-grounded Q&A:
```
You are a fact retrieval assistant. Answer using only the provided facts.
Always cite your sources with document name and page number...
```

To activate the LLM layer, `rule_extractor.py` would be replaced with a Groq/Gemini call using `fact_extraction.py`, and `qa_agent.py` would pass retrieved facts to the LLM using `chat_prompts.py`.

---

## SSE Progress Stream

The upload endpoint starts a background task and returns immediately. The frontend connects to `/api/documents/{id}/progress` (Server-Sent Events) and receives real-time updates:

```
data: {"stage": "extracting", "page": 12, "total_pages": 27, "facts_found": 34}
data: {"stage": "embedding", "progress": 0.6}
data: {"stage": "analyzing", "relationships_found": 8}
data: {"stage": "complete", "facts": 67, "relationships": 12}
```

---

## Auth

JWT-based auth with local SQLite user store. Tokens are signed with `JWT_SECRET` from the environment. All fact/relationship/chat endpoints are scoped to the authenticated user via `project_id` → `user_id` chain. No external auth provider.

---

## Deployment Notes

- **Backend**: Render free tier with a 1GB persistent disk mounted at the project root. SQLite, uploads, and FAISS index all live on the disk — they survive deploys.
- **Frontend**: Vercel. Set `NEXT_PUBLIC_API_URL` to the Render backend URL.
- **spaCy model**: `python -m spacy download en_core_web_sm` must run as part of the build command, or be added to `requirements.txt` as `https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl`.
- **sentence-transformers**: Downloads `all-MiniLM-L6-v2` (~90MB) on first startup. On Render free tier this can cause a cold-start timeout — the model should be pre-downloaded during the build step.
