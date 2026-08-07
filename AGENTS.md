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
- `backend/notebooks/` has exploratory Jupyter work.

### Key data flow
`sources/wikipedia/client.py` (fetch + parse sections) -> `ingestion/chunking.py` (token-bounded chunks, 1-paragraph overlap)
-> `ingestion/embed.py` (Gemini `gemini-embedding-2`, 1536-dim, upsert to Qdrant)
-> `ingestion/outline.py` (build a section outline from chunks)
-> `agents/planner.py` (LLM selects sections + per-section question counts, via `plan_quiz`)
-> `retrieval/retriever.py` (pull each section's text back from Qdrant by breadcrumb)
-> `agents/generator.py` (LLM writes MCQs per batch, streams each completed batch via a generator
   and retries a batch if the LLM under-produces below its requested question count).

## Services required
- **Qdrant** running at `http://localhost:6333` (collection `Quiz-App-Dev-Collection`, 1536-dim COSINE).
  `docker-compose.yml` is EMPTY - no compose setup exists yet; start Qdrant manually.
- **API keys** (from repo-root `.env`, gitignored):
  - `GEMINI_API_KEY` - embeddings (`ingestion/embed.py`).
  - `OPENROUTER_API_KEY` - LLM calls (`agents/llm.py`, default `deepseek/deepseek-v4-flash`).
  - `EMAIL` - sent as the Wikipedia `User-Agent` (Wikipedia requires a non-default UA).
- Config (`core/config.py`, pydantic-settings) reads `.env` and has system defaults:
  `DEFAULT_DIFFICULTY=medium`, `DEFAULT_QUESTION_COUNT=10`, `QDRANT_URL` falls back to
  `http://localhost:6333`. `.env` is located by walking up from the module file, NOT relative to CWD.

## Gotchas heavy caches
- The repo has no CWD-relative paths anymore: `core/config.py` locates `.env` from the module file,
  so the pipeline runs from any directory (e.g. `cd backend && uv run python -m backend.agents.run_pipeline`).

## Commands
- Install / run: `cd backend && uv run python -m backend.agents.run_pipeline`
- Dev server: `cd backend && uv run uvicorn backend.app:app --reload`
- No tests, linter, formatter, or typecheck config exists yet. Don't assume one.

## Guidelines
- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.
