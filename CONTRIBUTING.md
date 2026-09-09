# Contributing to FactForge

## Dev Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env            # set JWT_SECRET
uvicorn main:app --reload

# Frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

TypeScript check: `cd frontend && npx tsc --noEmit`

---

## Adding a New Attribute Type

Edit `backend/services/rule_extractor.py` — the `_ATTRIBUTE_KEYWORDS` dict:

```python
_ATTRIBUTE_KEYWORDS = {
    ...
    "New Attribute": ["keyword1", "keyword2"],
}
```

The canonicalizer alias map in `backend/services/canonicalizer.py` maps surface forms to canonical names:

```python
_ATTRIBUTE_ALIASES = {
    ...
    "keyword1": "New Attribute",
}
```

---

## Adding a New Regex Pattern

Numeric patterns are in `rule_extractor.py` under `_MONEY_RE`, `_PCT_RE`, `_UNIT_RE`. Each pattern must have a named group `value` and optionally `unit`.

---

## Database Migrations

Migrations are additive SQL statements in `backend/database/db.py` inside `_run_migrations()`. Add new `ALTER TABLE` or `CREATE TABLE IF NOT EXISTS` statements at the end of the list. Never modify existing migration statements.

---

## Integrating an LLM

The `backend/prompts/` directory has prompt templates ready. To activate:

1. Add `GROQ_API_KEY` or `GEMINI_API_KEY` to `.env`
2. In `backend/services/fact_miner.py`, replace the `rule_extractor.extract_facts()` call with a call to the LLM client using `prompts/fact_extraction.py`
3. In `backend/agents/qa_agent.py`, replace the structured formatter with an LLM call using `prompts/chat_prompts.py`

The relationship engine is intentionally kept deterministic — LLM classification of relationships would reduce auditability.

---

## Code Style

- Python: no formatter enforced, follow existing style (snake_case, type hints on public functions)
- TypeScript: ESLint config in `frontend/eslint.config.mjs`
- Keep service functions pure where possible — side effects (DB writes, FAISS updates) belong in the orchestrator (`fact_miner.py`, `relationship_engine.py`)
