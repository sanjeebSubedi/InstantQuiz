# Instant Quiz

Instant Quiz is a small retrieval-augmented generation (RAG) application. Enter a topic and it builds a multiple-choice quiz from a matching Wikipedia article.

The backend uses Gemini to create embeddings and Qdrant as its vector database. Article sections are split into chunks, indexed in a collection for that article, and used as source context for quiz planning and question generation. This keeps the questions tied to the source instead of asking the language model to rely only on its general knowledge.

## Demo

[Watch the demo](assets/demo_video.mp4)

## How it works

1. The backend finds a Wikipedia article for the topic.
2. It splits the article into sections and chunks, then stores their embeddings in Qdrant.
3. An OpenRouter model plans questions against the article outline.
4. The generator receives the matching source sections and streams the questions back in batches.
5. The API stores each batch in SQLite while the quiz is being generated.

The API has two endpoints:

- `POST /api/quizzes` starts a quiz and returns a job ID.
- `GET /api/quizzes/{job_id}` returns the job status and any questions generated so far.

## Run with Docker Compose

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
docker compose up --build
```

Open the frontend at http://localhost:3000. Compose starts the React frontend, FastAPI backend, and Qdrant vector database.

The Qdrant data and SQLite database use named Docker volumes, so they survive container restarts. Stop the stack with:

```bash
docker compose down
```

## Run locally

Start Qdrant first:

```bash
docker compose up -d qdrant
```

Run the backend with Python 3.13 and `uv`:

```bash
cd backend
uv run uvicorn backend.app:app --reload
uv run pytest
```

In another terminal, start the Vite frontend:

```bash
cd frontend
npm ci
npm run dev
npm test
```

The development frontend runs at http://localhost:5173 and proxies API requests to the backend at http://localhost:8000.

## Configuration

See `.env.example` for the available settings. The required values are:

- `GEMINI_API_KEY` for embeddings
- `OPENROUTER_API_KEY` for quiz planning and generation
- `EMAIL` for the Wikipedia API User-Agent

`QDRANT_URL`, `CORS_ORIGINS`, and `VITE_API_BASE_URL` change depending on whether the app runs locally or with Docker Compose.

## Project layout

- `backend/` contains the FastAPI app, RAG pipeline, Qdrant integration, and tests.
- `frontend/` contains the React and Vite application.
- `assets/` contains the demo video.

## Next step

The next step is to add more evaluation and observability. The plan is to use Ragas for RAG and generation evals, and LangSmith for traces, latency, failures, and prompt runs.
