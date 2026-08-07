import logging
from time import perf_counter

from google import genai
from google.genai import types
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.core.config import config

logger = logging.getLogger(__name__)


def get_embedding(client, text, emb_model="gemini-embedding-2"):
    result = client.models.embed_content(
        model=emb_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=1536),
    )

    return result.embeddings[0].values


def store_embeddings(qdrant_client, collection_name, data_to_embed):
    if qdrant_client.collection_exists(collection_name):
        logger.info("Collection '%s' already exists; skipping embed", collection_name)
        return

    gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    start = perf_counter()
    pointstructs = []
    for i, data in enumerate(data_to_embed):
        embedding = get_embedding(gemini_client, data["text"])
        pointstructs.append(
            PointStruct(
                id=i,
                vector=embedding,
                payload={
                    "article_title": data["article_title"],
                    "section_title": data["section_title"],
                    "section_breadcrumb": data["section_breadcrumb"],
                    "source_url": data["source_url"],
                    "raw_text": data["raw_text"],
                },
            )
        )

    qdrant_client.upsert(
        collection_name=collection_name, wait=True, points=pointstructs
    )
    logger.info(
        "Embedded %d chunks into collection '%s' in %.2fs",
        len(pointstructs),
        collection_name,
        perf_counter() - start,
    )
