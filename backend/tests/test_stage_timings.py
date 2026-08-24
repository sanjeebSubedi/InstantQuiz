"""Stage-timing observability: INFO logs must expose per-stage durations and
counts so cold vs warm runs and the concurrent-generation win are verifiable.
Observability is log-only; response shapes are covered by the other suites.
"""

import logging
import time

from backend.agents.models import QuizOutline
from backend.core.config import config
from backend.ingestion.embed import read_index_status
from backend.services.quiz_service import slugify_title
from tests.fakes import ARTICLE_TITLE

STAGES = (
    "wikipedia fetch",
    "parse+chunk",
    "outline",
    "plan",
    "local resolve",
    "first batch",
    "tail batches",
    "total=",
)


def collection_name():
    return f"{config.QDRANT_COLLECTION_PREFIX}-{slugify_title(ARTICLE_TITLE)}"


def wait_for_ready(qdrant_client, timeout=5.0):
    """Let the daemon indexer finish so its INFO lines land before we assert."""
    name = collection_name()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if read_index_status(qdrant_client, name) == "ready":
            return True
        time.sleep(0.01)
    return False


def test_foreground_stages_and_counts_are_logged(harness, caplog):
    with caplog.at_level(logging.INFO):
        harness.run_service()
        assert wait_for_ready(harness.qdrant_client), "indexer never became ready"

    text = "\n".join(caplog.messages)
    for stage in STAGES:
        assert stage in text, f"missing timing for stage '{stage}'"
    # Counts that make cold-vs-warm and batching behavior comparable.
    assert "chunks=" in text
    assert "planned_sections=3" in text
    # 3 batches, each answering fully on its first attempt.
    assert "3 LLM calls (0 retries) across 3 batches" in text
    assert "shortfall=0" in text
    # Cold run: background indexing ran and reported its duration.
    assert "Background index" in text


def test_warm_run_reuses_collection_without_background_indexing(harness, caplog):
    with caplog.at_level(logging.INFO):
        harness.run_service()
        assert wait_for_ready(harness.qdrant_client)
        result, batches = harness.run_service()

    assert result["question_count"] == 10
    assert len(batches) == 3
    # Exactly one indexing pass across the cold + warm pair.
    assert sum("Background index" in m for m in caplog.messages) == 1
    # Both runs still carry foreground timings for comparison.
    assert sum("wikipedia fetch" in m for m in caplog.messages) >= 2


def test_shortfall_is_counted_when_a_tail_batch_is_lost(harness, monkeypatch, caplog):
    from backend.services import quiz_service as quiz_service_module

    class FailingTailLlmClient(harness.llm.__class__):
        def create(self, messages=None, response_model=None, extra_body=None, **kwargs):
            if response_model != list[QuizOutline]:
                prompt = next(m["content"] for m in messages if m["role"] == "user")
                if "Breadcrumb: History" in prompt:
                    raise RuntimeError("provider outage")
            return super().create(
                messages=messages,
                response_model=response_model,
                extra_body=extra_body,
                **kwargs,
            )

    monkeypatch.setattr(
        quiz_service_module, "get_llm_client", lambda *a, **k: FailingTailLlmClient()
    )

    with caplog.at_level(logging.INFO):
        result, _ = harness.run_service()

    # History (4 questions) is forfeited by the hard tail failure.
    assert result["question_count"] == 6
    assert any("shortfall=4" in m for m in caplog.messages)
