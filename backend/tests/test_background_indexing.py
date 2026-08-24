import logging
import threading
import time

from backend.core.config import config
from backend.ingestion.chunking import build_chunks
from backend.ingestion.embed import (
    SENTINEL_POINT_ID,
    create_collection,
    mark_index_status,
    read_index_status,
    run_background_indexing,
)
from backend.services.quiz_service import slugify_title
from tests.fakes import ARTICLE_TITLE, TOPIC, FakeWikipediaClient, fake_get_embedding


def collection_name():
    return f"{config.QDRANT_COLLECTION_PREFIX}-{slugify_title(ARTICLE_TITLE)}"


def wait_for_status(qdrant_client, name, status, timeout=5.0):
    deadline = time.monotonic() + timeout
    current = None
    while time.monotonic() < deadline:
        current = read_index_status(qdrant_client, name)
        if current == status:
            break
        time.sleep(0.01)
    return current


def test_collection_flips_to_ready_with_all_chunk_points(harness):
    harness.run_service()

    name = collection_name()
    assert wait_for_status(harness.qdrant_client, name, "ready") == "ready"

    points, _ = harness.qdrant_client.scroll(collection_name=name, with_payload=True)
    sentinel = [p for p in points if str(p.id) == SENTINEL_POINT_ID]
    chunk_points = [p for p in points if str(p.id) != SENTINEL_POINT_ID]

    assert len(sentinel) == 1
    # 4 sections in the canned article, each its own chunk.
    assert sentinel[0].payload["_chunk_count"] == 4
    assert len(chunk_points) == 4
    assert all(p.payload["raw_text"] for p in chunk_points)


def test_cold_start_generates_without_awaiting_embedding(harness, monkeypatch):
    from backend.ingestion import embed as embed_module

    embed_started = threading.Event()
    release_embedding = threading.Event()

    def gated_get_embedding(client, text, emb_model="gemini-embedding-2"):
        embed_started.set()
        release_embedding.wait(timeout=10)
        return fake_get_embedding(client, text)

    monkeypatch.setattr(embed_module, "get_embedding", gated_get_embedding)

    outcome = {}

    def run():
        outcome["result"], outcome["batches"] = harness.run_service()

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert embed_started.wait(timeout=5), "background indexer never started"

        deadline = time.monotonic() + 5
        while harness.llm.planner_calls == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        # Planning and generation proceed while embedding is still blocked.
        assert harness.llm.planner_calls == 1
    finally:
        release_embedding.set()
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert outcome["result"]["question_count"] == 10
    assert len(outcome["batches"]) == 3


def test_concurrent_request_while_indexing_does_not_spawn_second_indexer(
    harness, monkeypatch
):
    from backend.ingestion import embed as embed_module

    embed_texts = []
    embed_started = threading.Event()
    release_embedding = threading.Event()

    def gated_get_embedding(client, text, emb_model="gemini-embedding-2"):
        embed_texts.append(text)
        embed_started.set()
        release_embedding.wait(timeout=10)
        return fake_get_embedding(client, text)

    monkeypatch.setattr(embed_module, "get_embedding", gated_get_embedding)

    first_outcome = {}
    first = threading.Thread(
        target=lambda: first_outcome.update(
            zip(("result", "batches"), harness.run_service())
        )
    )
    first.start()
    try:
        assert embed_started.wait(timeout=5), "background indexer never started"
        name = collection_name()
        assert read_index_status(harness.qdrant_client, name) == "indexing"

        # Second request generates immediately from its own chunks...
        second_result, second_batches = harness.run_service()
        assert second_result["question_count"] == 10
        assert len(second_batches) == 3
        # ...while the first indexer is still mid-flight.
        assert read_index_status(harness.qdrant_client, name) == "indexing"
    finally:
        release_embedding.set()
    first.join(timeout=10)

    assert not first.is_alive()
    assert first_outcome["result"]["question_count"] == 10
    # Exactly one indexer ran: one embed call per chunk, no duplicates.
    deadline = time.monotonic() + 5
    while len(embed_texts) < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(embed_texts) == 4
    assert wait_for_status(harness.qdrant_client, name, "ready") == "ready"


def make_chunks():
    wiki = FakeWikipediaClient()
    article = wiki.resolve_topic_to_article(TOPIC)
    sections = wiki.parse_sections(article["content"])
    return build_chunks(sections, ARTICLE_TITLE)


def prepare_indexing_collection(qdrant_client, name, chunks):
    """Recreate what spawn_background_indexing does before spawning."""
    create_collection(qdrant_client, name)
    mark_index_status(qdrant_client, name, "indexing", chunk_count=len(chunks))


def test_indexing_failure_is_retried_once(harness, monkeypatch, caplog):
    from backend.ingestion import embed as embed_module

    monkeypatch.setattr(embed_module, "INDEXING_RETRY_BACKOFF_SECONDS", 0)
    embed_calls = []

    def flaky_get_embedding(client, text, emb_model="gemini-embedding-2"):
        embed_calls.append(text)
        if len(embed_calls) == 1:
            raise RuntimeError("gemini 429")
        return fake_get_embedding(client, text)

    monkeypatch.setattr(embed_module, "get_embedding", flaky_get_embedding)

    chunks = make_chunks()
    name = collection_name()
    prepare_indexing_collection(harness.qdrant_client, name, chunks)

    with caplog.at_level(logging.WARNING):
        run_background_indexing(name, chunks)

    # The first pass died early; a full second pass completed the indexing.
    assert len(embed_calls) > len(chunks)
    assert read_index_status(harness.qdrant_client, name) == "ready"
    assert any("retrying" in message for message in caplog.messages)


def test_terminal_failure_deletes_failed_collection(harness, monkeypatch):
    from backend.ingestion import embed as embed_module

    monkeypatch.setattr(embed_module, "INDEXING_RETRY_BACKOFF_SECONDS", 0)
    embed_calls = []

    def dead_get_embedding(client, text, emb_model="gemini-embedding-2"):
        embed_calls.append(text)
        raise RuntimeError("gemini down")

    monkeypatch.setattr(embed_module, "get_embedding", dead_get_embedding)

    chunks = make_chunks()
    name = collection_name()
    prepare_indexing_collection(harness.qdrant_client, name, chunks)

    run_background_indexing(name, chunks)

    # Exactly one retry, then the collection is removed for a clean cold start.
    assert len(embed_calls) == 2
    assert read_index_status(harness.qdrant_client, name) == "absent"
    assert not harness.qdrant_client.collection_exists(name)


def test_failed_collection_survives_concurrent_flip_to_ready(harness, monkeypatch):
    from backend.ingestion import embed as embed_module

    monkeypatch.setattr(embed_module, "INDEXING_RETRY_BACKOFF_SECONDS", 0)

    def dead_get_embedding(client, text, emb_model="gemini-embedding-2"):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(embed_module, "get_embedding", dead_get_embedding)

    def ready_read(qdrant_client, collection_name):
        return "ready"

    monkeypatch.setattr(embed_module, "read_index_status", ready_read)

    chunks = make_chunks()
    name = collection_name()
    prepare_indexing_collection(harness.qdrant_client, name, chunks)

    run_background_indexing(name, chunks)

    # Another indexer flipped the marker between our failed-mark and the
    # re-read, so deletion is skipped and the ready collection survives.
    assert harness.qdrant_client.collection_exists(name)


def test_existing_collection_is_not_reindexed(harness, monkeypatch):
    from backend.ingestion import embed as embed_module

    embed_calls = []

    def counting_get_embedding(client, text, emb_model="gemini-embedding-2"):
        embed_calls.append(text)
        return fake_get_embedding(client, text)

    monkeypatch.setattr(embed_module, "get_embedding", counting_get_embedding)

    harness.run_service()
    name = collection_name()
    assert wait_for_status(harness.qdrant_client, name, "ready") == "ready"
    assert len(embed_calls) == 4

    # A ready collection falls through unchanged: no second indexing pass.
    harness.run_service()
    assert len(embed_calls) == 4
