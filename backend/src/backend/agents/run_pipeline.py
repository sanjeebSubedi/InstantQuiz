from qdrant_client import QdrantClient

from backend.ingestion.chunking import build_chunks
from backend.ingestion.embed import store_embeddings
from backend.ingestion.outline import (
    build_outline,
    create_outline_table,
    get_connection,
    get_outline,
    save_outline,
)
from backend.sources.wikipedia.client import WikipediaClient


def main():
    wikipedia_client = WikipediaClient()
    qdrant_client = QdrantClient(url="http://localhost:6333")
    qdrant_collection_name = "Quiz-App-Dev-Collection"
    # topic = input("Enter a topic: ")
    topic = "Linux"

    article = wikipedia_client.resolve_topic_to_article(topic)
    article_title = article.get("title", "")
    sections = wikipedia_client.parse_sections(article.get("content", ""))

    chunks = build_chunks(sections, article.get("title", ""))
    store_embeddings(qdrant_client, qdrant_collection_name, chunks)

    outline = build_outline(chunks, article_title)
    conn = get_connection()
    create_outline_table(conn)
    article_id = save_outline(conn, article_title, outline)
    cached = get_outline(conn, article_title)
    print(cached)


if __name__ == "__main__":
    main()
