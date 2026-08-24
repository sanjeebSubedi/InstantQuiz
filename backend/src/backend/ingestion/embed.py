import logging
from datetime import datetime, timezone
from time import perf_counter

from google import genai
from google.genai import types
from qdrant_client import QdrantClient
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


def create_collection(qdrant_client, collection_name):
    """Create an empty collection sized for the embedding vectors."""
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )


def run_background_indexing(collection_name, chunks):
    """Daemon-thread body: embed ``chunks`` and flip the sentinel to ``ready``.

    Builds its own Qdrant and Gemini clients so background work shares nothing
    with the request path. Chunk points go up with ``wait=False`` (eventual
    consistency); only afterwards does the sentinel flip to ``ready`` with
    ``wait=True``, so ``ready`` is never advertised before the data exists.
    Any failure marks the sentinel ``failed`` instead of raising on a thread.
    """
    try:
        start = perf_counter()
        qdrant_client = QdrantClient(url=config.QDRANT_URL)
        gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

        pointstructs = [
            PointStruct(
                id=i,
                vector=get_embedding(gemini_client, data["text"]),
                payload={
                    "article_title": data["article_title"],
                    "section_title": data["section_title"],
                    "section_breadcrumb": data["section_breadcrumb"],
                    "source_url": data["source_url"],
                    "raw_text": data["raw_text"],
                },
            )
            for i, data in enumerate(chunks)
        ]
        qdrant_client.upsert(
            collection_name=collection_name, wait=False, points=pointstructs
        )
        mark_index_status(
            qdrant_client, collection_name, "ready", chunk_count=len(pointstructs)
        )
        logger.info(
            "Indexed %d chunks into collection '%s' in %.2fs",
            len(pointstructs),
            collection_name,
            perf_counter() - start,
        )
    except Exception:
        logger.exception("Background indexing of '%s' failed", collection_name)
        try:
            mark_index_status(
                QdrantClient(url=config.QDRANT_URL), collection_name, "failed"
            )
        except Exception:
            logger.exception("Could not mark '%s' as failed", collection_name)
