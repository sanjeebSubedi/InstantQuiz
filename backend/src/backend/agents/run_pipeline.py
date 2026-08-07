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


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    topic = input("Enter a topic: ")
    logger.info("Processing topic '%s'", topic)
    start = perf_counter()

    wikipedia_client = WikipediaClient()
    qdrant_client = QdrantClient(url=config.QDRANT_URL)

    article = wikipedia_client.resolve_topic_to_article(topic)
    article_title = article.get("title", "")
    sections = wikipedia_client.parse_sections(article.get("content", ""))

    chunks = build_chunks(sections, article.get("title", ""))
    qdrant_collection_name = f"{config.QDRANT_COLLECTION_PREFIX}-{slugify_title(article_title)}"
    if qdrant_client.collection_exists(qdrant_collection_name):
        logger.info(
            "Article already indexed; reusing collection '%s'", qdrant_collection_name
        )
    else:
        store_embeddings(qdrant_client, qdrant_collection_name, chunks)

    outline = build_outline(chunks, article_title)

    llm_client = get_llm_client()
    blueprint = plan_quiz(
        llm_client,
        outline,
        topic,
        config.DEFAULT_DIFFICULTY,
        config.DEFAULT_QUESTION_COUNT,
    )

    blueprint = retrieve_chunks(qdrant_client, qdrant_collection_name, blueprint)

    logger.info("Retrieval and planning done in %.2fs", perf_counter() - start)
    question_count = 0
    for batch in generate_quiz(llm_client, blueprint):
        for question in batch:
            question_count += 1
            print(f"\nQ{question_count}: {question.question}")
            for i, option in enumerate(question.options, start=1):
                print(f"   {i}. {option}")
            print(f"   Correct: {question.correct_answer}")

    if question_count != config.DEFAULT_QUESTION_COUNT:
        logger.warning(
            "Planned %d questions but generated %d",
            config.DEFAULT_QUESTION_COUNT,
            question_count,
        )
    logger.info(
        "Pipeline finished: %d questions for '%s' in %.2fs",
        question_count,
        article_title,
        perf_counter() - start,
    )


if __name__ == "__main__":
    main()