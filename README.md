# FactForge — Explainable Fact Knowledge Layer

FactForge converts uploaded PDFs into a structured knowledge layer where every extracted fact is a first-class object with identity, canonical representation, source evidence, confidence score, and cross-document relationships.

This is not a PDF summarizer or a generic RAG chatbot. The knowledge layer is the product.

---

## Features

- **Fact Extraction** — Gemini extracts structured facts (numbers, percentages, money, dates, people, organizations, metrics) from every page
- **Evidence Grounding** — every fact is linked to its exact source document, page number, and supporting sentence
- **Canonicalization** — values normalized across units (crore/lakh/million/billion), currencies (₹/$), and periods (FY24 → FY2024)
- **Dynamic Schema** — new attributes discovered automatically from any PDF, no hardcoded schema
- **Relationship Engine** — detects corroboration, contradiction, and reconciliation across documents using deterministic logic + FAISS similarity
- **Timeline** — facts organized chronologically by period with relationship markers
- **Knowledge-Grounded Chat** — answers only from uploaded documents, every response includes citations
- **Incremental Indexing** — re-uploading or adding new PDFs only processes new content
- **Live Processing** — SSE streams real-time progress (pages processed, facts found, relationships detected)
- **Duplicate Detection** — identical documents and duplicate facts are skipped automatically

---

## Architecture

```
factforge/
├── backend/                  # FastAPI application
│   ├── api/                  # Route handlers (documents, facts, relationships, timeline, chat, progress)
│   ├── agents/               # QA agent (FAISS retrieval → Gemini answer)
│   ├── services/             # Business logic
│   │   ├── document_processor.py   # PyMuPDF page extraction
│   │   ├── fact_miner.py           # Gemini fact extraction + storage
│   │   ├── canonicalizer.py        # Unit/period/alias normalization
│   │   ├── relationship_engine.py  # Corroboration/contradiction/reconciliation
│   │   ├── vector_store.py         # FAISS index management
│   │   ├── timeline_service.py     # Chronological fact grouping
│   │   └── incremental_indexer.py  # Deduplication + incremental processing
│   ├── models/               # Pydantic models
│   ├── prompts/              # Gemini prompt templates
│   ├── database/             # SQLite connection + schema
│   └── utils/                # Config, logger
│
└── frontend/                 # Next.js 15 application
    ├── app/                  # App Router pages
    │   ├── page.tsx          # Dashboard with live stats
    │   ├── upload/           # Drag-and-drop upload with SSE progress
    │   ├── facts/            # Fact explorer + detail with evidence
    │   ├── relationships/    # Relationship explorer with type filters
    │   ├── timeline/         # Chronological timeline
    │   └── chat/             # Knowledge-grounded chat
    ├── components/           # Reusable UI components
    ├── hooks/                # React Query + SSE hooks
    ├── lib/api/              # Typed API client functions
    └── types/                # Shared TypeScript interfaces
```

### Processing Pipeline

```
Upload PDF
    ↓
PyMuPDF page extraction (page-by-page, preserves page numbers)
    ↓
Store pages in document_pages (processed=0)
    ↓
Gemini fact extraction (dynamic batch size based on page density)
    ↓
Canonicalization (units, periods, aliases)
    ↓
Deduplication (fingerprint check)
    ↓
Store facts + evidence
    ↓
FAISS embedding + similarity search
    ↓
Relationship detection (deterministic) → Gemini explanation
    ↓
Store relationships
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
| `attribute_registry` | Dynamically discovered attributes with occurrence counts |
| `chat_sessions` | Chat session metadata |
| `chat_messages` | Full message history with citations |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, React Query, Framer Motion |
| Backend | FastAPI, Python 3.11+, Pydantic, Uvicorn |
| AI | Google Gemini 1.5 Flash (extraction + chat), Gemini text-embedding-004 |
| PDF | PyMuPDF (fitz) |
| Storage | SQLite (WAL mode), FAISS (local vector search) |
| Deployment | Vercel (frontend), Render (backend) |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [Gemini API key](https://aistudio.google.com/app/apikey)

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

uvicorn main:app --reload
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install

# .env.local is already configured for local dev
# NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
# App running at http://localhost:3000
```

---

## Deployment

### Frontend → Vercel

1. Push to GitHub
2. Import repo in [Vercel](https://vercel.com)
3. Set root directory to `frontend`
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-backend.onrender.com`
5. Deploy

### Backend → Render

1. Create a new **Web Service** in [Render](https://render.com)
2. Connect your GitHub repo
3. Set root directory to `backend`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from `.env.example`
7. Add a **Disk** (1 GB) mounted at `/opt/render/project/src/backend` for SQLite + uploads

Or use the included `render.yaml` for one-click deploy.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload a PDF |
| GET | `/api/documents` | List all documents |
| GET | `/api/documents/{id}/status` | Processing status |
| GET | `/api/documents/{id}/progress` | SSE live progress stream |
| GET | `/api/facts` | List facts (filterable) |
| GET | `/api/facts/stats` | Dashboard counts |
| GET | `/api/facts/{id}` | Fact with evidence |
| GET | `/api/relationships` | List relationships |
| GET | `/api/relationships/summary` | Counts by type |
| GET | `/api/timeline` | Chronological fact timeline |
| POST | `/api/chat` | Ask a question |
| GET | `/api/attributes` | Discovered attribute registry |

Full interactive docs at `/docs` when running locally.

---

## Engineering Decisions

### Why SQLite?
Sufficient for the scale of this application, zero infrastructure overhead, WAL mode enables concurrent reads during background processing, and the entire knowledge layer is a single portable file.

### Why FAISS locally?
Avoids external vector database costs and latency. `IndexFlatIP` with cosine normalization gives exact nearest-neighbor search. The index is persisted to disk and loaded incrementally — no rebuild needed when new facts are added.

### Why deterministic relationship detection?
LLMs are expensive and non-deterministic. Corroboration, contradiction, and reconciliation are detected using exact entity/attribute matching, numeric comparison with 5% tolerance, and period comparison — all deterministic. Gemini is called only once per detected relationship to generate a human-readable explanation.

### Dynamic schema
There is no hardcoded list of attributes. Every attribute Gemini extracts is registered in `attribute_registry` with a canonical form. The system works identically for financial reports, medical documents, agricultural data, or any other domain.

### Incremental indexing
The `document_pages.processed` flag ensures pages are never re-processed. Fact fingerprints (`entity|attribute|value|period`) prevent duplicate storage. The relationship engine only analyzes facts not yet present as a source in the relationships table. Re-uploading a completed document returns the existing record immediately.

### Large PDF handling
Pages are extracted and stored first, then processed in small batches. Batch size is computed dynamically from average page text density (dense pages → smaller batches to stay within Gemini token limits). This keeps memory usage flat regardless of PDF size.

---

## Limitations

- Gemini API rate limits may slow processing of very large PDFs (100+ pages)
- SQLite is not suitable for concurrent multi-user production deployments — migrate to PostgreSQL for that
- FAISS index is in-memory during runtime; very large fact sets (100k+) may require an approximate index
- OCR for scanned PDFs is not enabled by default (pytesseract can be added)
- Chat does not maintain conversational context across turns (each question is independent)

---

## Future Improvements

- Streaming chat responses via SSE
- OCR support for scanned PDFs
- Multi-user authentication
- PostgreSQL + pgvector for production scale
- Fact confidence recalibration based on corroboration signals
- Export knowledge layer as JSON/CSV
- Webhook notifications when processing completes

---

## AI Tools Used

- **Google Gemini 1.5 Flash** — fact extraction from page text, relationship explanation generation, knowledge-grounded QA
- **Google text-embedding-004** — semantic embeddings for FAISS similarity search

All AI calls are minimal and purposeful. Canonicalization, relationship detection, timeline organization, and deduplication are fully deterministic.
