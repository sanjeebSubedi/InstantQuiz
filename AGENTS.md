# AGENTS.md

A RAG-based quiz generator. The user supplies a topic; the system picks a Wikipedia article on it,
chunks and embeds the article into Qdrant, builds a section outline, and then plans and generates
multiple-choice quiz questions via an LLM. The flow is driven through a shared service used by both
the CLI and a FastAPI job API (batches are streamed to the client as they are generated).
Everything lives under `backend/`; repo root has no code.

## Structure & stack

- Everything lives under `backend/`. Repo root has no code.
- Python 3.13, managed with `uv`. `uv.lock` is the source of truth for deps.
- `src` layout: `backend/src/backend/{app.py, agents, api, core, ingestion, retrieval, services, sources, storage}`.
  Import as `backend.*` - do NOT move package files to repo root.
- `backend/notebooks/` holds exploratory Jupyter work that predates the packaged modules.

### Entrypoints
- `agents/run_pipeline.py:main()` - the end-to-end CLI runner. Reads a topic from stdin and drives fetch -> chunk -> embed -> outline -> plan -> retrieve -> generate via the service.
- `services/quiz_service.py:generate_quiz_for_topic()` - the shared pipeline orchestrator (used by both the CLI and the API). Takes an `on_batch` callback that receives each generated batch of API-shaped questions as it completes, so callers can stream partial results.
- `app.py` - FastAPI app. Serves the quiz API: `POST /api/quizzes` (creates a job, returns `job_id` with `202`), `GET /api/quizzes/{job_id}` (poll status + questions). Jobs run in a background thread and stream question batches into SQLite as they are generated, so a poll during `running` may already return partial `questions`.
- `agents/llm.py:get_llm_client()` - builds the OpenRouter `instructor` client used by planner and generator (default model `deepseek/deepseek-v4-flash`).

API DTOs live in `api/models.py`; endpoint wiring in `api/routes.py`. Persistence is stdlib `sqlite3` in `storage/db.py`.

## Key data flow

1. `sources/wikipedia/client.py` - resolve a topic to a Wikipedia article and parse its sections (drops boilerplate headers, tracks a hierarchical breadcrumb per section).
2. `ingestion/chunking.py` - split sections into token-bounded chunks with 1-paragraph overlap.
3. `ingestion/embed.py` - `store_embeddings` creates the article's collection and embeds chunks (Gemini `gemini-embedding-2`, 1536-dim) then upserts them. It is idempotent: if the collection already exists it returns early, so a previously indexed article is reused (no re-embedding).
4. `ingestion/outline.py` - build a lightweight outline of the article (section breadcrumb, preview, token count) for the planner.
5. `agents/planner.py` - an LLM decides which sections get questions and how many each (`plan_quiz`), producing a blueprint.
6. `retrieval/retriever.py` - pull each selected section's text back out of Qdrant by breadcrumb.
7. `agents/generator.py` - an LLM writes MCQs per batch of sections. Batches are streamed to the caller as they complete, and a batch is retried if it comes back under its requested question count. Each batch is yielded in small chunks (3, then 4) so the first questions reach the user quickly. Every blueprint section gets a stable `section_index` used in the prompt, so questions can be mapped back to their section's `source_url`.

Generator prompts and prompt builders live in `agents/prompts.py`; the plan/quiz response models live in `agents/models.py`. The service strips `explanation` from questions before handing them to callers, and attaches each question's `source_url` by `section_index`.

## Services & config

- **Qdrant** at `http://localhost:6333`, COSINE. Each article gets its own collection named `quiz_app-<slugified-title>` (prefix from `QDRANT_COLLECTION_PREFIX`); if a collection already exists the article's embeddings are reused across runs. `docker-compose.yml` is EMPTY - start Qdrant manually, there is no compose setup.
- **API keys** in repo-root `.env` (gitignored):
  - `GEMINI_API_KEY` - embeddings (`ingestion/embed.py`).
  - `OPENROUTER_API_KEY` - LLM calls (`agents/llm.py`).
  - `EMAIL` - sent as the Wikipedia `User-Agent` (Wikipedia requires a non-default UA).
- **Config** (`core/config.py`, pydantic-settings) loads `.env` and carries system defaults: `DEFAULT_DIFFICULTY=medium`, `DEFAULT_QUESTION_COUNT=10`, `QDRANT_URL` falling back to `http://localhost:6333`, `QDRANT_COLLECTION_PREFIX=quiz_app`, and `QUIZ_DB_PATH` (SQLite file, default `quiz.db` at repo root). `.env` is resolved from the module file, not from the working directory.

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