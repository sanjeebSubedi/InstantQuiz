# AGENTS.md

RAG quiz generator: resolve a topic to Wikipedia, index its sections in Qdrant, plan questions with an LLM, and stream generated MCQs through a FastAPI API or CLI. Backend is under `backend/`; frontend under `frontend/`; the repository root has no application code.

## Structure

- **Backend:** Python 3.13, `uv`, `backend/src/backend/` (`agents`, `api`, `core`, `ingestion`, `retrieval`, `services`, `sources`, `storage`). Use `backend.*` imports; keep the src layout.
- **Frontend:** Vite + React 19, plain JavaScript. CSS is in `frontend/src/index.css`; tests use Vitest.
- **Shared pipeline:** `services/quiz_service.py:generate_quiz_for_topic()` orchestrates fetching, chunking, embedding, outlining, planning, retrieval, and generation. `agents/run_pipeline.py` is the CLI entrypoint.
- **API:** `app.py` exposes `POST /api/quizzes` (returns a job ID) and `GET /api/quizzes/{job_id}` (status plus partial/final questions). Jobs run in a background thread and persist streamed batches in SQLite. DTOs: `api/models.py`; routes: `api/routes.py`; DB: `storage/db.py`.
- **LLM:** `agents/llm.py` creates the OpenRouter `instructor` client. Planner: `agents/planner.py`; generator: `agents/generator.py`; prompts/models: `agents/prompts.py`, `agents/models.py`.
- **Wikipedia/RAG:** `sources/wikipedia/client.py` resolves and parses articles; `ingestion/chunking.py` chunks sections; `ingestion/embed.py` stores embeddings; `ingestion/outline.py` creates the planner outline; `retrieval/retriever.py` retrieves selected sections.
- **Frontend flow:** `frontend/src/App.jsx` maps landing/creating/playing/results/failed phases. Session logic is in `src/session/` (`sessionReducer.js`, `controller.js`, `storage.js`, `url.js`, `useSession.js`); views are in `src/views/`.

## Important behavior and configuration

- Generation is streamed in batches; API polls can return questions while a job is still running. Questions are mapped to source URLs using stable blueprint `section_index` values; callers do not receive `explanation`.
- Qdrant runs at `http://localhost:6333`; start it manually (`docker-compose.yml` is empty). Collections are `quiz_app-<slugified-title>` by default and existing collections are reused.
- Root `.env` supplies `GEMINI_API_KEY` (embeddings), `OPENROUTER_API_KEY` (LLM), and `EMAIL` (Wikipedia User-Agent). Settings are defined in `core/config.py` and loaded independently of the working directory.
- Default settings include medium difficulty, 10 questions, Qdrant URL/prefix, and root `quiz.db`.

## Commands

```bash
cd backend && uv run python -m backend.agents.run_pipeline
cd backend && uv run uvicorn backend.app:app --reload
cd frontend && npm run dev
cd frontend && npm test
```

Backend tests live in `backend/tests/` and run with `cd backend && uv run pytest`. There are no lint, formatter, or typecheck commands configured.

## Coding rules

- Avoid speculative abstractions, compatibility layers, fallbacks, and migrations; remove obsolete paths.
- Keep components modular and make surgical changes. Match existing style and remove only unused code introduced by your changes.
- State assumptions and ask when requirements are unclear; do not silently choose between materially different interpretations.
