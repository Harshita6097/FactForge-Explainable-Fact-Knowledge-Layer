# FactForge — Explainable Fact Knowledge Layer

FactForge converts uploaded PDFs into a structured knowledge layer where every extracted fact is a first-class object with identity, canonical representation, source evidence, confidence score, and cross-document relationships.

This is not a PDF summarizer or a generic RAG chatbot. The knowledge layer is the product.

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

### Environment Files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

The backend `.env` only needs `JWT_SECRET` set to any random string. No external API keys are required.

---

## Approach

### The Original Design — LLM Agent Architecture

The intended architecture was an LLM-orchestrated agent system with three agents:

- An **extraction agent** would receive each PDF page and return structured JSON: `{ entity, attribute, value, period, confidence, evidence_snippet }`
- A **relationship agent** would receive pairs of facts and classify them as corroborated / contradiction / reconciled / related, with a natural-language reasoning chain explaining each decision
- A **chat agent** would answer questions in natural language prose with citations, grounded in the knowledge layer

This is the right architecture. LLMs handle implicit facts, ambiguous phrasing, table structure, and multi-sentence context in ways that regex cannot. The reasoning chains would be genuinely explanatory, generated from the LLM's understanding of the facts rather than assembled from a fixed template.

**Why it was not built this way:** The Gemini free tier allows 20 requests/day — exhausted by a single 27-page PDF in one test run. Groq's free tier (14,400 req/day) sounds generous, but at one request per page the 100-page starter documents would consume the quota in a single session, and the relationship analysis phase would consume the rest. Paying for API access was not an option within the assignment constraints.

The decision was: build the system correctly as an architecture, implement the deterministic services that would sit underneath the LLM agents, and be honest about what the LLM layer would add.

### What Was Actually Built

A fully local, zero-quota pipeline that produces the same data model the LLM agent would have produced.

**Fact Extraction — Rule-Based**

- **spaCy `en_core_web_sm`** — NER for entity detection (ORG, PERSON, GPE). Falls back to a three-level hierarchy when spaCy misses domain-specific names (e.g. "Delhivery" is not in its training data):
  1. spaCy NER
  2. Most frequent ORG across the full page
  3. First capitalized proper noun, excluding common financial adjectives
- **Regex patterns** — money values (`Rs/₹/INR/USD + crore/lakh/million/billion`), percentages, operational units (employees, warehouses, cities, shipments)
- **Period detection** — `FY2024`, `Q3 FY24`, `H1 2024`, `March 2024` — single compiled pattern
- **Attribute classification** — 27 keyword-mapped attribute types (Revenue, EBITDA, Net Profit, Employees, Warehouses, etc.)
- **Demographic guard** — sentences about population, casualties, disasters are skipped before extraction
- **Clause-scoped detection** — attribute keywords are matched within an 80-character window around each numeric match, not across the full sentence

**Relationship Detection — Fully Deterministic**

All four criteria must be satisfied before any classification:

1. Entity match (same canonical entity)
2. Attribute match (same canonical attribute)
3. Period match (same fiscal period)
4. Unit compatibility (`%` vs `INR` are never compared)

Relationship types:
- **Corroborated** — all four match, values within tolerance (5% for financials, exact for headcount, 0.1–0.2% for macro rates)
- **Contradiction** — all four match, values differ beyond tolerance
- **Reconciled** — entity + attribute match, periods differ (temporal change, not a real conflict)
- **Related** — different entities, same attribute (benchmark comparison)

Every relationship includes a step-by-step reasoning chain built deterministically from the fact data: entity match → attribute match → period comparison → unit compatibility → value comparison → classification.

**Semantic Similarity — Local Embeddings**

FAISS similarity search uses `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally). Embeddings are computed once per fact and persisted to disk. The relationship engine uses FAISS to find candidate pairs before running deterministic checks, keeping the comparison space manageable as the knowledge layer grows.

**Canonicalization**

Before storage, every fact is normalized:
- Units: `2192 crore` → `21920000000` (base value in rupees)
- Periods: `FY24`, `FY 2024`, `2023-24` → `FY2024`
- Attributes: `turnover`, `net sales`, `income from operations` → `Revenue`

**Chat — Structured Fact Retrieval**

Chat uses FAISS semantic search to retrieve the most relevant facts for a question, then formats them as a structured response with entity, attribute, value, source document, and page number. Every answer includes a CITATIONS section. No LLM is involved — the answer is assembled directly from the knowledge layer.

**Dynamic Schema**

There is no hardcoded list of attributes. Every attribute the extractor discovers is registered in `attribute_registry` with a canonical form and occurrence count. The system works identically for financial reports, legal documents, or medical data.

**Incremental Indexing**

- `document_pages.processed` flag — pages are never re-processed
- Fact fingerprints (`entity|attribute|value|period`) — duplicate facts are skipped
- Relationship engine only analyzes facts not yet present as a source in the relationships table
- Re-uploading a completed document returns the existing record immediately

### Architecture

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
│   │   ├── cases.py                # Four required cases endpoint
│   │   └── progress.py             # SSE live processing stream
│   ├── agents/
│   │   └── qa_agent.py             # FAISS retrieval → structured answer
│   ├── services/
│   │   ├── document_processor.py   # PyMuPDF page extraction
│   │   ├── rule_extractor.py       # spaCy + regex fact extraction
│   │   ├── local_embedder.py       # sentence-transformers embeddings
│   │   ├── fact_miner.py           # Orchestrates extraction + storage
│   │   ├── canonicalizer.py        # Unit/period/alias normalization
│   │   ├── relationship_engine.py  # Deterministic relationship detection
│   │   ├── vector_store.py         # FAISS index management
│   │   ├── knowledge_layer.py      # Canonical fact merging
│   │   ├── timeline_service.py     # Chronological grouping
│   │   └── incremental_indexer.py  # Deduplication + incremental processing
│   ├── prompts/                    # Prompt templates (ready for LLM integration)
│   ├── models/                     # Pydantic request/response models
│   ├── database/                   # SQLite connection + schema + migrations
│   └── utils/                      # Config, logger, auth, rate limiter
│
├── frontend/                       # Next.js 15 application
│   ├── app/
│   │   ├── page.tsx                # Dashboard with live stats
│   │   ├── upload/                 # Drag-and-drop upload with SSE progress
│   │   ├── facts/                  # Fact explorer + canonical fact detail
│   │   ├── relationships/          # Relationship explorer with reasoning chain
│   │   ├── timeline/               # Chronological timeline
│   │   └── chat/                   # Knowledge-grounded chat with citations
│   ├── components/                 # Reusable UI components
│   ├── hooks/                      # React Query + SSE hooks
│   ├── lib/api/                    # Typed API client
│   └── types/                      # Shared TypeScript interfaces
│
└── starter-datasets/               # Sample PDFs for testing
    ├── delhivery/                  # Prospectus, annual report, earnings presentation
    └── india-macroeconomy/         # Economic Survey, RBI Annual Report, IMF Article IV
```

### Processing Pipeline

```
Upload PDF
    ↓
PyMuPDF — page-by-page text extraction (preserves page numbers)
    ↓
Store pages in document_pages (processed=0)
    ↓
rule_extractor — demographic guard → spaCy NER + regex per page
    ↓
Canonicalization — units, periods, attribute aliases
    ↓
Deduplication — fingerprint check (entity|attribute|value|period)
    ↓
Store facts + evidence (entity, attribute, value, page, snippet)
    ↓
local_embedder — sentence-transformers embedding per fact
    ↓
FAISS similarity search — find candidate fact pairs
    ↓
Deterministic relationship detection — all-four-criteria enforcement
    ↓
Deterministic reasoning chain assembled and stored
    ↓
SSE progress stream updated throughout
```

### Key Engineering Decisions

**No LLM for extraction** — The original design used Gemini. The free tier limit was exhausted by a single 27-page PDF. Rather than switching to a paid tier, extraction was rebuilt as a local rule-based system. The trade-off is real: LLMs extract implicit and contextual facts that regex cannot. But for structured financial documents with consistent patterns, rule-based extraction is fast, deterministic, and reliable.

**Deterministic relationship detection** — LLMs are non-deterministic; the same two facts could be classified differently on different runs. Corroboration, contradiction, and reconciliation have clear logical definitions. Implementing them deterministically means the reasoning is fully auditable and reproducible.

**SQLite** — Zero infrastructure overhead. WAL mode enables concurrent reads during background processing. The entire knowledge layer is a single portable file. PostgreSQL would be needed for concurrent multi-user production use.

**FAISS locally** — Avoids external vector database costs and latency. `IndexFlatIP` with cosine normalization gives exact nearest-neighbor search. The index is persisted to disk and loaded incrementally.

**sentence-transformers over a cloud embedding API** — No quota, no latency, no cost. `all-MiniLM-L6-v2` is 90MB, downloads once, and runs in ~5ms per embedding on CPU.

### AI Tools Used in Development

- **Amazon Q Developer (IDE)** — used throughout development for code generation, debugging, and architectural decisions. All significant implementation was done with Amazon Q assistance.
- **spaCy `en_core_web_sm`** — NER model for entity detection at runtime
- **sentence-transformers `all-MiniLM-L6-v2`** — embedding model for semantic similarity at runtime

No generative AI API is called at runtime. All extraction, relationship detection, and response generation is deterministic.

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

**What would improve it:** Fine-tuning spaCy on financial documents, or using `en_core_web_lg` which has better coverage of company names. Alternatively, extracting the document title/company name from PDF metadata and injecting it as a known entity hint before processing.

---

## Database Schema

| Table | Purpose |
|---|---|
| `documents` | Uploaded PDFs with processing status |
| `document_pages` | Raw page text with `processed` flag for incremental indexing |
| `facts` | Extracted facts with canonical values |
| `evidence` | Page + snippet linking every fact to its source |
| `relationships` | Cross-document and intra-document corroboration, contradiction, reconciliation |
| `relationship_reasoning` | Step-by-step reasoning chain per relationship |
| `attribute_registry` | Dynamically discovered attributes with occurrence counts |
| `canonical_facts` | Merged facts across documents with conflict counts |
| `chat_sessions` | Chat session metadata |
| `chat_messages` | Full message history with citations |
| `projects` | User-scoped project groupings |
| `extraction_failures` | Pages where extraction produced no facts |

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
| Auth | JWT (local, no external provider) |
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
| POST | `/api/documents/{id}/analyze` | Re-run relationship analysis (`?reset=true` to clear existing) |
| GET | `/api/facts` | List facts (filterable by document, attribute, entity) |
| GET | `/api/facts/stats` | Dashboard counts |
| GET | `/api/facts/{id}` | Fact with full evidence |
| GET | `/api/relationships` | List relationships |
| GET | `/api/relationships/summary` | Counts by type |
| GET | `/api/timeline` | Chronological fact timeline |
| POST | `/api/chat` | Ask a question against the knowledge layer |
| GET | `/api/attributes` | Discovered attribute registry |
| GET | `/api/cases` | The four required cases with live examples |

Full interactive docs at `/docs` when running locally.

---

## Limitations and Next Steps

### What Does Not Work Well

- **Entity detection accuracy** — spaCy `en_core_web_sm` misses domain-specific company names. The proper noun fallback works but can pick incorrect words in complex sentences. Estimated wrong entity assignment rate: 15–25% of extracted facts.
- **Table extraction** — financial tables extracted by PyMuPDF often produce rows like `Revenue 2,192 3,456` with no sentence structure. The regex matches the numbers but attribute/entity assignment is weaker for table-sourced facts.
- **Implicit facts** — rule-based extraction only captures explicitly stated values. "Revenue grew 23% YoY" extracts the growth rate but not the implied prior-year absolute value.
- **Chat is structured, not conversational** — responses are formatted fact lists, not natural language prose. No conversational context across turns. This is the most visible gap from the intended LLM-agent design.
- **Single-language** — extraction patterns are English-only.
- **No LLM at runtime** — the chat experience is structured retrieval, not natural language generation. This is the direct consequence of the quota constraint.

### What Would Be Built Next

1. **LLM extraction layer** — An LLM (Claude being the natural fit given its strong document understanding) as an optional enhancement on top of rule extraction. Rules run first; LLM fills gaps for sentences where rules produced no facts. This keeps token usage low while improving coverage.
2. **Finance-domain NER** — Replace `en_core_web_sm` with a model fine-tuned on financial documents, or use PDF metadata (title, author) to seed known entity names before page processing. A custom-trained NER model on financial filings would be a meaningful accuracy improvement — this is a tractable fine-tuning task, not a theoretical one.
3. **Natural language chat** — Replace the structured formatter in `qa_agent.py` with an LLM call that receives the retrieved facts as context and generates a prose answer.
4. **OCR support** — pytesseract for scanned PDFs.
6. **Export** — Knowledge layer as JSON/CSV for downstream use.
7. **PostgreSQL + pgvector** — For production multi-user scale.

---

## Additional Notes

### Honesty About the Approach

The system was designed as an LLM-agent architecture and rebuilt as a deterministic pipeline when the quota constraint made the LLM approach unworkable. The data model, API surface, and frontend are all designed for the LLM version — the `prompts/` directory contains the prompt templates that would be used, and `qa_agent.py` is structured to swap in an LLM call with minimal changes. The rule-based services are the fallback implementation, not the intended one.

The extraction accuracy is lower than an LLM would achieve. The chat experience is structured retrieval, not natural language. These are real limitations that would be resolved by the LLM layer.

What the deterministic implementation does well: it is fast, auditable, reproducible, and works offline with no external dependencies. The relationship detection logic is correct — the four-criteria enforcement, unit compatibility guard, and per-attribute tolerances produce reliable classifications on the facts that are correctly extracted.

### Generalization

There are no hardcoded facts, filenames, entity names, or document-specific rules anywhere in the codebase. The attribute registry grows dynamically with every new PDF. The relationship engine works on any domain — financial reports, legal documents, medical records — as long as facts share entities and attributes.

### The Quota Problem as a Design Constraint

Hitting a hard wall mid-development forced a decision: pay for API access, switch providers, or build locally. Building locally produced a more robust system in some ways — faster, auditable, no external dependencies — but it is not the right long-term answer for a system whose core value proposition is intelligent fact extraction. The honest next step is to integrate an LLM with a usage strategy that keeps costs manageable: batch processing, response caching, and a rules-first approach where the LLM only handles sentences that rules could not resolve.
