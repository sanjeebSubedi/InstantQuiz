import logging
import re
from time import perf_counter

from qdrant_client import QdrantClient

from backend.agents.generator import generate_quiz
from backend.agents.llm import get_llm_client
from backend.agents.planner import plan_quiz
from backend.core.config import config
from backend.ingestion.chunking import build_chunks
from backend.ingestion.embed import store_embeddings
from backend.ingestion.outline import build_outline
from backend.retrieval.retriever import retrieve_chunks
from backend.sources.wikipedia.client import WikipediaClient

logger = logging.getLogger(__name__)


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
    qdrant_client = QdrantClient(url=config.QDRANT_URL)

    article = wikipedia_client.resolve_topic_to_article(topic)
    article_title = article.get("title", "")
    sections = wikipedia_client.parse_sections(article.get("content", ""))

    chunks = build_chunks(sections, article_title)
    qdrant_collection_name = f"{config.QDRANT_COLLECTION_PREFIX}-{slugify_title(article_title)}"
    store_embeddings(qdrant_client, qdrant_collection_name, chunks)

    outline = build_outline(chunks, article_title)

    llm_client = get_llm_client()
    planned = plan_quiz(llm_client, outline, topic, difficulty, question_count)
    blueprint = retrieve_chunks(qdrant_client, qdrant_collection_name, planned)

    logger.info("Retrieval and planning done in %.2fs", perf_counter() - start)

    source_by_index = {
        index: item["source_url"]
        for index, item in enumerate(blueprint, start=1)
    }

    generated = 0
    for batch in generate_quiz(llm_client, blueprint):
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

    if generated != question_count:
        logger.warning(
            "Planned %d questions but generated %d",
            question_count,
            generated,
        )
    logger.info(
        "Pipeline finished: %d questions for '%s' in %.2fs",
        generated,
        article_title,
        perf_counter() - start,
    )

    return {
        "topic": topic,
        "article_title": article_title,
        "difficulty": difficulty,
        "question_count": generated,
    }