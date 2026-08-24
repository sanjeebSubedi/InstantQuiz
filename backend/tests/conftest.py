"""Shared test harness for the quiz generation pipeline.

Patches the orchestration service's external dependencies in place:
Wikipedia, Qdrant (in-memory instance), Gemini embeddings, and the LLM
client. Tests exercise either ``generate_quiz_for_topic`` directly (service
seam) or the HTTP polling contract via ``TestClient`` (API seam).
"""

import os

# Config requires these at import time; provide dummies so the suite runs on
# machines/CI without a root .env. Real env vars take precedence.
os.environ.setdefault("EMAIL", "test@example.com")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from backend.agents import llm as llm_module
from backend.core.config import config
from backend.ingestion import embed as embed_module
from backend.services import quiz_service as quiz_service_module

from tests.fakes import (
    ARTICLE_TITLE,
    FakeLlmClient,
    FakeWikipediaClient,
    TOPIC,
    fake_get_embedding,
)


class QuizHarness:
    """Handle over the fakes for a single test run."""

    def __init__(self, qdrant_client):
        self.qdrant_client = qdrant_client
        self._llm = FakeLlmClient()

    @property
    def llm(self):
        return self._llm

    def run_service(self, topic=TOPIC, difficulty="medium", question_count=10):
        """Run generate_quiz_for_topic at the service seam; collect batches."""
        batches = []
        result = quiz_service_module.generate_quiz_for_topic(
            topic, batches.append, difficulty, question_count
        )
        return result, batches

    def api_client(self):
        from backend.app import app

        return TestClient(app)


@pytest.fixture
def harness(monkeypatch, tmp_path):
    qdrant_client = QdrantClient(":memory:")

    monkeypatch.setattr(
        quiz_service_module, "QdrantClient", lambda url=None: qdrant_client
    )
    monkeypatch.setattr(quiz_service_module, "WikipediaClient", FakeWikipediaClient)
    # Background indexer builds its own clients; route them to the same fake.
    monkeypatch.setattr(embed_module, "QdrantClient", lambda url=None: qdrant_client)
    monkeypatch.setattr(
        quiz_service_module, "get_llm_client", lambda *args, **kwargs: harness.llm
    )
    # Embeddings: deterministic vectors, no Gemini client construction.
    monkeypatch.setattr(embed_module.genai, "Client", lambda **kwargs: None)
    monkeypatch.setattr(embed_module, "get_embedding", fake_get_embedding)

    # Job storage stays local to the test.
    monkeypatch.setattr(config, "QUIZ_DB_PATH", str(tmp_path / "quiz.db"))

    harness = QuizHarness(qdrant_client)
    yield harness


__all__ = ["QuizHarness", "harness"]
