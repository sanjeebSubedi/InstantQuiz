# AGENTS.md

A RAG-based quiz generator. The user supplies a topic; the system picks a Wikipedia article on it,
chunks and embeds the article into Qdrant, builds a section outline, and then plans and generates
multiple-choice quiz questions via an LLM. The whole flow is driven through a single entrypoint.

## Structure & stack

- Everything lives under `backend/`. Repo root has no code.
- Python 3.13, managed with `uv`. `uv.lock` is the source of truth for deps.
- `src` layout: `backend/src/backend/{app.py, agents, core, ingestion, retrieval, sources}`.
  Import as `backend.*` - do NOT move package files to repo root.
- `backend/notebooks/` holds exploratory Jupyter work that predates the packaged modules.

### Entrypoints
- `agents/run_pipeline.py:main()` - the end-to-end runner. Reads a topic from stdin and drives fetch -> chunk -> embed -> outline -> plan -> retrieve -> generate.
- `app.py` - FastAPI app, currently just `{"Hello": "World"}`.
- `agents/llm.py:get_llm_client()` - builds the OpenRouter `instructor` client used by planner and generator (default model `deepseek/deepseek-v4-flash`).

## Key data flow

1. `sources/wikipedia/client.py` - resolve a topic to a Wikipedia article and parse its sections (drops boilerplate headers, tracks a hierarchical breadcrumb per section).
2. `ingestion/chunking.py` - split sections into token-bounded chunks with 1-paragraph overlap.
3. `ingestion/embed.py` - embed chunks (Gemini `gemini-embedding-2`, 1536-dim) and upsert to Qdrant.
4. `ingestion/outline.py` - build a lightweight outline of the article (section breadcrumb, preview, token count) for the planner.
5. `agents/planner.py` - an LLM decides which sections get questions and how many each (`plan_quiz`), producing a blueprint.
6. `retrieval/retriever.py` - pull each selected section's text back out of Qdrant by breadcrumb.
7. `agents/generator.py` - an LLM writes MCQs per batch of sections. Batches are streamed to the caller as they complete, and a batch is retried if it comes back under its requested question count.

Generator prompts and prompt builders live in `agents/prompts.py`; the plan/quiz response models live in `agents/models.py`.

## Services & config

- **Qdrant** at `http://localhost:6333` (collection `Quiz-App-Dev-Collection`, COSINE). `docker-compose.yml` is EMPTY - start Qdrant manually, there is no compose setup.
- **API keys** in repo-root `.env` (gitignored):
  - `GEMINI_API_KEY` - embeddings (`ingestion/embed.py`).
  - `OPENROUTER_API_KEY` - LLM calls (`agents/llm.py`).
  - `EMAIL` - sent as the Wikipedia `User-Agent` (Wikipedia requires a non-default UA).
- **Config** (`core/config.py`, pydantic-settings) loads `.env` and carries system defaults: `DEFAULT_DIFFICULTY=medium`, `DEFAULT_QUESTION_COUNT=10`, and `QDRANT_URL` falling back to `http://localhost:6333`. `.env` is resolved from the module file, not from the working directory.

## Notes

- The repo has no CWD-relative paths, so the pipeline runs from any directory (e.g. `cd backend && uv run python -m backend.agents.run_pipeline`).
- Progress is reported through stdlib `logging` (INFO level); each stage, count, and duration is logged.

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