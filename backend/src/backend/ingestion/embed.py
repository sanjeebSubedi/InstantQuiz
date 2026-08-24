import logging
from datetime import datetime, timezone
from time import perf_counter

from google import genai
from google.genai import types
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.core.config import config

logger = logging.getLogger(__name__)

# Reserved point id for the collection-level index-status sentinel. Chunk
# points use sequential integer ids, so a UUID can never collide with them.
SENTINEL_POINT_ID = "00000000-0000-0000-0000-000000000000"


def read_index_status(qdrant_client, collection_name):
    """Return the indexing status of a Qdrant collection.

    One of ``absent`` / ``indexing`` / ``ready`` / ``failed``, read from the
    sentinel point stored on the collection itself. A collection that exists
    but carries no sentinel (e.g. created before this marker) is reported as
    ``absent``, i.e. not safe to reuse.
    """
    if not qdrant_client.collection_exists(collection_name):
        return "absent"

    points = qdrant_client.retrieve(
        collection_name=collection_name,
        ids=[SENTINEL_POINT_ID],
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return "absent"
    return points[0].payload.get("_index_status", "absent")


def mark_index_status(qdrant_client, collection_name, status, chunk_count=None):
    """Write the sentinel status point onto an existing collection."""
    collection_info = qdrant_client.get_collection(collection_name)
    vector_size = collection_info.config.params.vectors.size

    payload = {
        "_index_status": status,
        "_started_at": datetime.now(timezone.utc).isoformat(),
    }
    if chunk_count is not None:
        payload["_chunk_count"] = chunk_count

    qdrant_client.upsert(
        collection_name=collection_name,
        wait=True,
        points=[PointStruct(id=SENTINEL_POINT_ID, vector=[0.0] * vector_size, payload=payload)],
    )


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
