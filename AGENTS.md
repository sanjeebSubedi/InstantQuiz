# AGENTS.md

RAG-based quiz generator: picks a topic from Wikipedia, chunks + embeds it into Qdrant, builds a
section outline, then plans/generates quiz questions via an LLM. Early-stage and in active flux:
several modules are still stubs.

## Structure & stack

- Everything lives under `backend/`. Repo root has no code.
- Python 3.13, managed with `uv`. `uv.lock` is the source of truth for deps.
- Layout is a `src` package: `backend/src/backend/{app.py, agents, core, ingestion, retrieval, sources}`.
  Import as `backend.*` (src layout) - do NOT move package files to repo root.
- Entrypoints:
  - `backend/src/backend/agents/run_pipeline.py:main()` - the end-to-end fetch -> chunk -> embed -> outline runner.
  - `backend/src/backend/app.py` - FastAPI app, currently just `{"Hello": "World"}`.
  - `backend/src/backend/agents/llm.py:get_llm_client()` - OpenRouter instructor client, default model `deepseek/deepseek-v4-flash`.
- `backend/notebooks/` has exploratory Jupyter work; `backend/notebooks/questions.txt` is sample output.

### Key data flow
`sources/wikipedia/client.py` (fetch + parse sections) -> `ingestion/chunking.py` (token-bounded chunks, 1-paragraph overlap)
-> `ingestion/embed.py` (Gemini `gemini-embedding-2`, 1536-dim, upsert to Qdrant)
-> `ingestion/outline.py` (build outline, upsert into SQLite `quiz_outlines.db`)
-> `agents/planner.py` / `agents/generator.py` (LLM question generation - NOT YET IMPLEMENTED).

## Services required
- **Qdrant** running at `http://localhost:6333` (collection `Quiz-App-Dev-Collection`, hardcoded 1536-dim COSINE).
  `docker-compose.yml` is EMPTY - no compose setup exists yet; start Qdrant manually.
- **API keys** (from `.env`, gitignored):
  - `GEMINI_API_KEY` - embeddings. NOTE: `embed.py` has a Gemini key hardcoded inline instead of reading config - a bug worth fixing.
  - `OPENROUTER_API_KEY` - LLM calls in `agents/llm.py`.
  - `EMAIL` - sent as the Wikipedia `User-Agent` (Wikipedia requires a non-default UA).
- Config loading: pydantic-settings reads `.env` via relative path (`env_file=".env"`).

## Gotchas / CWD-dependence
- `core/config.py` and `ingestion/outline.py` use **relative paths** (`.env`, `../quiz_outlines.db`).
  They only resolve when run **from `backend/`** (e.g. `cd backend && uv run python -m backend.agents.run_pipeline`).
- `outline.py:get_connection()` defaults DB path to `../quiz_outlines.db` relative to CWD - the committed
  `backend/quiz_outlines.db` is checked in.

## Commands
- Install / run: `cd backend && uv run python -m backend.agents.run_pipeline`
- Dev server: `cd backend && uv run uvicorn backend.app:app --reload`
- No tests, linter, formatter, or typecheck config exists yet. Don't assume one.