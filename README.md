# FactForge — Explainable Fact Knowledge Layer

FactForge converts uploaded PDFs into a structured knowledge layer where every extracted fact is a first-class object with identity, canonical representation, source evidence, confidence score, and cross-document relationships.

This is not a PDF summarizer or a generic RAG chatbot. The knowledge layer is the product.

---

## Video Demo

> 🎥 [Demo video link — to be added]

---

## Setup and Run Instructions

### Prerequisites

- Python 3.9+
- Node.js 18+
- No API keys required — fully local, zero external dependencies

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Download spaCy English model (one-time, ~12MB)
python -m spacy download en_core_web_sm

uvicorn main:app --reload
# API running at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

> On first startup, `sentence-transformers` will download `all-MiniLM-L6-v2` (~90MB) automatically and cache it locally. Subsequent starts are instant.

### Frontend

```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:3000
```

---

## Approach

### The Core Idea

Important facts are scattered across documents, stated differently, and sometimes contradict each other. The goal was to build a system where every fact is a first-class object — not just a chunk of text — with its own identity, source evidence, canonical form, and relationships to other facts.

### Fact Extraction — Rule-Based, No LLM

The initial design used Google Gemini for fact extraction. During development, the free tier quota (20 requests/day) was exhausted by a single 27-page PDF, making it unusable for any real workflow.

The replacement is a fully local, zero-quota extraction pipeline:

- **spaCy `en_core_web_sm`** — NER for entity detection (ORG, PERSON, GPE). Falls back to a proper noun regex when spaCy misses company names not in its training data (e.g. "Delhivery")
- **Regex patterns** — money values (`Rs/₹/INR/USD + crore/lakh/million/billion`), percentages, and operational units (employees, warehouses, cities, shipments)
- **Period detection** — `FY2024`, `Q3 FY24`, `H1 2024`, `March 2024` — all caught with a single compiled pattern
- **Attribute classification** — 27 keyword-mapped attribute types (Revenue, EBITDA, Net Profit, Employees, Warehouses, etc.)
- **Per-page deduplication** — `entity|attribute|value` fingerprint prevents duplicate facts within a document

This runs in milliseconds per page, works offline, and never hits a rate limit.

### Relationship Detection — Fully Deterministic

Relationships between facts are detected with pure logic — no LLM involved at any stage:

- **Corroborated** — same entity, same attribute, same period, values within 5% tolerance
- **Contradiction** — same entity, same attribute, same period, values differ beyond tolerance
- **Reconciled** — same entity, same attribute, different periods (temporal change, not a real conflict)
- **Related** — different entities, same attribute (benchmark comparison)

Per-attribute tolerances are configured separately — headcount requires exact match, financial figures allow 5%, macroeconomic rates allow 0.1-0.2%.

Every relationship includes a step-by-step reasoning chain (entity match → attribute match → period comparison → value comparison → source documents → classification) built deterministically from the fact data.

### Semantic Similarity — Local Embeddings

FAISS similarity search uses `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally). Embeddings are computed once per fact and persisted to disk — no recomputation on restart. The relationship engine uses FAISS to find candidate fact pairs before running deterministic checks, keeping the comparison space manageable as the knowledge layer grows.

### Canonicalization

Before storage, every fact is normalized:
- Units: `2192 crore` → `21920000000` (base value in rupees)
- Periods: `FY24`, `FY 2024`, `2023-24` → `FY2024`
- Attributes: `turnover`, `net sales`, `income from operations` → `Revenue`

This ensures facts from different documents can be compared even when expressed differently.

### Chat — Structured Fact Retrieval

Chat uses FAISS semantic search to retrieve the most relevant facts for a question, then formats them as a structured response with entity, attribute, value, source document, and page number. Every answer includes a CITATIONS section. No LLM is involved — the answer is assembled directly from the knowledge layer.

### Dynamic Schema

There is no hardcoded list of attributes. Every attribute the extractor discovers is registered in `attribute_registry` with a canonical form and occurrence count. The system works identically for financial reports, legal documents, medical data, or any other domain.

### Incremental Indexing

- `document_pages.processed` flag — pages are never re-processed
- Fact fingerprints (`entity|attribute|value|period`) — duplicate facts are skipped
- Relationship engine only analyzes facts not yet present as a source in the relationships table
- Re-uploading a completed document returns the existing record immediately

---

## Architecture

```
factforge/
├── backend/                        # FastAPI application
│   ├── api/                        # Route handlers
│   │   ├── documents.py            # Upload, list, delete, status
│   │   ├── facts.py                # Fact explorer + stats
│   │   ├── relationships.py        # Relationship explorer + reasoning
│   │   ├── timeline.py             # Chronological fact grouping
│   │   ├── chat.py                 # Knowledge-grounded Q&A
│   │   ├── knowledge.py            # Canonical facts layer
│   │   └── progress.py             # SSE live processing stream
│   ├── agents/
│   │   └── qa_agent.py             # FAISS retrieval → structured answer
│   ├── services/
│   │   ├── document_processor.py   # PyMuPDF page extraction
│   │   ├── rule_extractor.py       # spaCy + regex fact extraction (local)
│   │   ├── local_embedder.py       # sentence-transformers embeddings (local)
│   │   ├── fact_miner.py           # Orchestrates extraction + storage
│   │   ├── canonicalizer.py        # Unit/period/alias normalization
│   │   ├── relationship_engine.py  # Deterministic relationship detection
│   │   ├── vector_store.py         # FAISS index management
│   │   ├── knowledge_layer.py      # Canonical fact merging
│   │   ├── timeline_service.py     # Chronological grouping
│   │   └── incremental_indexer.py  # Deduplication + incremental processing
│   ├── models/                     # Pydantic request/response models
│   ├── database/                   # SQLite connection + schema + migrations
│   └── utils/                      # Config, logger, rate limiter
│
└── frontend/                       # Next.js 15 application
    ├── app/
    │   ├── page.tsx                # Dashboard with live stats
    │   ├── upload/                 # Drag-and-drop upload with SSE progress
    │   ├── facts/                  # Fact explorer + canonical fact detail
    │   ├── relationships/          # Relationship explorer with reasoning chain
    │   ├── timeline/               # Chronological timeline
    │   └── chat/                   # Knowledge-grounded chat with citations
    ├── components/                 # Reusable UI components
    ├── hooks/                      # React Query + SSE hooks
    ├── lib/api/                    # Typed API client
    └── types/                      # Shared TypeScript interfaces
```

### Processing Pipeline

```
Upload PDF
    ↓
PyMuPDF — page-by-page text extraction (preserves page numbers)
    ↓
Store pages in document_pages (processed=0)
    ↓
rule_extractor — spaCy NER + regex per page
    ↓
Canonicalization — units, periods, attribute aliases
    ↓
Deduplication — fingerprint check
    ↓
Store facts + evidence (entity, attribute, value, page, snippet)
    ↓
local_embedder — sentence-transformers embedding per fact
    ↓
FAISS similarity search — find candidate fact pairs
    ↓
Deterministic relationship detection — corroboration/contradiction/reconciliation
    ↓
Template-based explanation + reasoning chain stored
    ↓
SSE progress stream updated throughout
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `documents` | Uploaded PDFs with processing status |
| `document_pages` | Raw page text with `processed` flag for incremental indexing |
| `facts` | Extracted facts with canonical values |
| `evidence` | Page + snippet linking every fact to its source |
| `relationships` | Cross-document corroboration, contradiction, reconciliation |
| `relationship_reasoning` | Step-by-step reasoning chain per relationship |
| `attribute_registry` | Dynamically discovered attributes with occurrence counts |
| `canonical_facts` | Merged facts across documents with conflict counts |
| `chat_sessions` | Chat session metadata |
| `chat_messages` | Full message history with citations |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, React Query, Framer Motion |
| Backend | FastAPI, Python 3.9+, Pydantic v2, Uvicorn |
| Fact Extraction | spaCy `en_core_web_sm` + regex (fully local) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (fully local, 384-dim) |
| PDF Parsing | PyMuPDF (fitz) |
| Vector Search | FAISS `IndexFlatIP` with cosine normalization |
| Storage | SQLite (WAL mode) |
| Deployment | Vercel (frontend), Render (backend) |

**No external AI API required. No API keys. No rate limits.**

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload a PDF |
| GET | `/api/documents` | List all documents |
| GET | `/api/documents/{id}/status` | Processing status |
| GET | `/api/documents/{id}/progress` | SSE live progress stream |
| GET | `/api/facts` | List facts (filterable by document, attribute, entity) |
| GET | `/api/facts/stats` | Dashboard counts |
| GET | `/api/facts/{id}` | Fact with full evidence |
| GET | `/api/relationships` | List relationships |
| GET | `/api/relationships/summary` | Counts by type |
| GET | `/api/timeline` | Chronological fact timeline |
| POST | `/api/chat` | Ask a question against the knowledge layer |
| GET | `/api/attributes` | Discovered attribute registry |

Full interactive docs at `/docs` when running locally.

---

## The Four Required Cases

### 1. Corroborated Fact
A revenue figure reported in both the annual report and the quarterly results document. Same entity, same attribute, same period, values within tolerance → classified as **corroborated** with confidence 0.95. The reasoning chain shows: entity match ✓ → attribute match ✓ → period match ✓ → value within 5% ✓.

### 2. Genuine Contradiction
The same metric reported with conflicting values in two documents covering the same period. Same entity, same attribute, same period, values differ beyond tolerance → classified as **contradiction** with confidence 0.90. Both source snippets are shown with page numbers.

### 3. Apparent Contradiction Explained by Context
Two revenue figures that look contradictory but cover different fiscal years (e.g. FY2023 vs FY2024). The period comparison step in the reasoning chain catches this — different periods → classified as **reconciled** (temporal change) rather than contradiction, with confidence 0.88.

### 4. Extraction / Reasoning Failure
**What failed:** spaCy's `en_core_web_sm` does not recognize domain-specific company names like "Delhivery" as ORG entities — it was trained on general web text, not financial documents. This caused entity detection to fail for sentences where the company name was the only entity.

**How it was handled:** A three-level fallback was built:
1. spaCy NER (ORG, PERSON, GPE)
2. Most frequent ORG across the full page (document-level context)
3. First capitalized proper noun in the sentence, excluding common financial adjectives (Net, Gross, Total, Operating)

**What would improve it:** Fine-tuning spaCy on financial documents, or using a larger model (`en_core_web_lg`) which has better coverage of company names. Alternatively, extracting the document title/company name from the PDF metadata and injecting it as a known entity hint before processing.

---

## Engineering Decisions

### Why no LLM for extraction?
The original design used Gemini. The free tier limit of 20 requests/day was exhausted by a single 27-page PDF during development. Rather than switching to a paid tier or a different LLM API, the extraction was rebuilt as a local rule-based system. This has a real trade-off: LLMs extract implicit and contextual facts that regex cannot. But for structured financial documents with consistent patterns, rule-based extraction is fast, deterministic, and reliable — and it never fails due to quota.

### Why deterministic relationship detection?
LLMs are non-deterministic — the same two facts could be classified differently on different runs. Corroboration, contradiction, and reconciliation have clear logical definitions. Implementing them deterministically means the reasoning is fully auditable and reproducible. The step-by-step reasoning chain is built from the same logic that made the classification decision, so it is always consistent.

### Why SQLite?
Zero infrastructure overhead. WAL mode enables concurrent reads during background processing. The entire knowledge layer is a single portable file. For a prototype at this scale, it is the right choice. PostgreSQL would be needed for concurrent multi-user production use.

### Why FAISS locally?
Avoids external vector database costs and latency. `IndexFlatIP` with cosine normalization gives exact nearest-neighbor search. The index is persisted to disk and loaded incrementally — no rebuild on restart.

### Why sentence-transformers over a cloud embedding API?
Same reason as extraction — no quota, no latency, no cost. `all-MiniLM-L6-v2` is 90MB, downloads once, and runs in ~5ms per embedding on CPU.

---

## Limitations and Next Steps

### Current Limitations

- **Entity detection accuracy** — spaCy `en_core_web_sm` misses domain-specific company names. The proper noun fallback works but can pick incorrect words in complex sentences
- **Table extraction** — financial tables extracted by PyMuPDF often produce rows like `Revenue 2,192 3,456` with no sentence structure. The regex matches the numbers but attribute/entity assignment is weaker
- **Implicit facts** — rule-based extraction only captures explicitly stated values. An LLM would also extract implied facts ("revenue grew 23% YoY" → both the growth rate and the implied prior year value)
- **Chat is structured, not conversational** — responses are formatted fact lists, not natural language prose. No conversational context across turns
- **Single-language** — extraction patterns are English-only

### Next Steps

- Replace `en_core_web_sm` with `en_core_web_lg` or a finance-domain NER model for better entity coverage
- Add PDF metadata extraction (title, author) to seed the entity hint before page processing
- Integrate an optional LLM (Groq free tier: 14,400 req/day) as an enhancement layer on top of rule extraction — rules run first, LLM fills gaps
- OCR support via pytesseract for scanned PDFs
- Fact confidence recalibration — corroborated facts get higher confidence, contradicted facts get lower
- Export knowledge layer as JSON/CSV
- PostgreSQL + pgvector for production multi-user scale

---

## Additional Notes

The system is designed to generalize. There are no hardcoded facts, filenames, entity names, or document-specific rules anywhere in the codebase. The attribute registry grows dynamically with every new PDF. The relationship engine works on any domain — financial reports, legal documents, medical records — as long as facts share entities and attributes.

The most interesting engineering constraint was the quota problem. Hitting a hard wall mid-development forced a decision: pay for API access, switch providers, or build locally. Building locally turned out to produce a more robust system — faster, auditable, and with no external dependencies.

---

## AI Tools Used in Development

- **Amazon Q (IDE)** — used throughout development for code generation, debugging, and architectural decisions
- **spaCy `en_core_web_sm`** — NER model for entity detection at runtime
- **sentence-transformers `all-MiniLM-L6-v2`** — embedding model for semantic similarity at runtime

No generative AI API is called at runtime. All extraction, relationship detection, and response generation is deterministic.
