import logging
import re
import threading
from time import perf_counter

from qdrant_client import QdrantClient

from backend.agents.generator import generate_quiz
from backend.agents.llm import get_llm_client
from backend.agents.planner import plan_quiz
from backend.core.config import config
from backend.ingestion.chunking import build_chunks
from backend.ingestion.embed import (
    create_collection,
    mark_index_status,
    read_index_status,
    run_background_indexing,
)
from backend.ingestion.outline import build_outline
from backend.retrieval.retriever import resolve_chunks_locally
from backend.sources.wikipedia.client import WikipediaClient

logger = logging.getLogger(__name__)

# Serializes the absent→indexing transition per collection so concurrent
# requests for the same article spawn exactly one background indexer.
_indexing_locks: dict[str, threading.Lock] = {}
_indexing_locks_guard = threading.Lock()


def _indexing_lock(collection_name):
    with _indexing_locks_guard:
        return _indexing_locks.setdefault(collection_name, threading.Lock())


def spawn_background_indexing(collection_name, chunks):
    """Index ``chunks`` off the critical path when the collection is absent.

    Creates the collection and marks it ``indexing`` synchronously so a second
    concurrent request observes the in-progress marker immediately, then hands
    embedding to a daemon thread. Requests arriving while ``indexing`` (or on
    an existing ``ready``/``failed`` collection) fall through without spawning.

    Known limitation: a process crash mid-indexing leaves the sentinel at
    ``indexing`` forever, blocking re-indexing of that collection until
    stale-sentinel recovery exists.
    """
    with _indexing_lock(collection_name):
        client = QdrantClient(url=config.QDRANT_URL)
        if read_index_status(client, collection_name) != "absent":
            return
        create_collection(client, collection_name)
        mark_index_status(client, collection_name, "indexing", chunk_count=len(chunks))

    threading.Thread(
        target=run_background_indexing,
        args=(collection_name, chunks),
        daemon=True,
        name=f"index-{collection_name}",
    ).start()


def slugify_title(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def generate_quiz_for_topic(
    topic, on_batch, difficulty=config.DEFAULT_DIFFICULTY, question_count=config.DEFAULT_QUESTION_COUNT
):
    """Build and generate a quiz for a topic, streaming question batches to ``on_batch``."""
    logger.info(
        "Processing topic '%s' (difficulty=%s, %d questions)",
        topic,
        difficulty,
        question_count,
    )
    start = perf_counter()

    wikipedia_client = WikipediaClient()

    article = wikipedia_client.resolve_topic_to_article(topic)
    fetch_done = perf_counter()

    article_title = article.get("title", "")
    sections = wikipedia_client.parse_sections(article.get("content", ""))
    chunks = build_chunks(sections, article_title)
    chunk_done = perf_counter()

    qdrant_collection_name = f"{config.QDRANT_COLLECTION_PREFIX}-{slugify_title(article_title)}"
    spawn_background_indexing(qdrant_collection_name, chunks)

    outline = build_outline(chunks, article_title)
    outline_done = perf_counter()

    llm_client = get_llm_client()
    planned = plan_quiz(llm_client, outline, topic, difficulty, question_count)
    plan_done = perf_counter()

    blueprint = resolve_chunks_locally(chunks, planned)
    resolve_done = perf_counter()

    logger.info("Planning done in %.2fs", plan_done - start)
    logger.info(
        "Stage timings: wikipedia fetch=%.2fs parse+chunk=%.2fs outline=%.2fs "
        "plan=%.2fs local resolve=%.2fs (chunks=%d planned_sections=%d)",
        fetch_done - start,
        chunk_done - fetch_done,
        outline_done - chunk_done,
        plan_done - outline_done,
        resolve_done - plan_done,
        len(chunks),
        len(planned),
    )

    source_by_index = {
        index: item["source_url"]
        for index, item in enumerate(blueprint, start=1)
    }

    generated = 0
    for batch in generate_quiz(llm_client, blueprint):
        unmapped = {q.section_index for q in batch} - source_by_index.keys()
        if unmapped:
            logger.warning(
                "No source URL mapped for section_index %s", sorted(unmapped)
            )
        api_batch = [
            {
                "section_index": q.section_index,
                "question": q.question,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "source_url": source_by_index.get(q.section_index, ""),
            }
            for q in batch
        ]
        on_batch(api_batch)
        generated += len(api_batch)

    if generated == 0:
        raise RuntimeError(f"Generated no questions for topic '{topic}'")
    shortfall = max(question_count - generated, 0)
    if generated != question_count:
        logger.warning(
            "Planned %d questions but generated %d",
            question_count,
            generated,
        )
    logger.info(
        "Pipeline finished: %d questions for '%s' total=%.2fs "
        "(shortfall=%d)",
        generated,
        article_title,
        perf_counter() - start,
        shortfall,
    )

    return {
        "topic": topic,
        "article_title": article_title,
        "difficulty": difficulty,
        "question_count": generated,
    }