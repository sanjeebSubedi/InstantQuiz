import threading
import time

from backend.core.config import config
from backend.ingestion.embed import SENTINEL_POINT_ID, read_index_status
from backend.services.quiz_service import slugify_title
from tests.fakes import ARTICLE_TITLE, TOPIC, fake_get_embedding


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
