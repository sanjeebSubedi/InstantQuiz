from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from backend.ingestion.embed import mark_index_status, read_index_status


def make_collection(client, name, size=8):
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=size, distance=Distance.COSINE),
    )


def test_absent_when_collection_missing():
    client = QdrantClient(":memory:")

    assert read_index_status(client, "quiz_app-everest") == "absent"


def test_absent_when_collection_has_no_sentinel():
    client = QdrantClient(":memory:")
    make_collection(client, "quiz_app-everest")

    assert read_index_status(client, "quiz_app-everest") == "absent"


def test_full_lifecycle():
    client = QdrantClient(":memory:")
    make_collection(client, "quiz_app-everest")

    mark_index_status(client, "quiz_app-everest", "indexing", chunk_count=12)
    assert read_index_status(client, "quiz_app-everest") == "indexing"

    mark_index_status(client, "quiz_app-everest", "ready", chunk_count=12)
    assert read_index_status(client, "quiz_app-everest") == "ready"

    mark_index_status(client, "quiz_app-everest", "failed")
    assert read_index_status(client, "quiz_app-everest") == "failed"


def test_sentinel_is_independent_of_chunk_points():
    from qdrant_client.models import PointStruct

    client = QdrantClient(":memory:")
    make_collection(client, "quiz_app-everest")
    client.upsert(
        collection_name="quiz_app-everest",
        points=[
            PointStruct(id=0, vector=[0.1] * 8, payload={"section_breadcrumb": "History"}),
            PointStruct(id=1, vector=[0.2] * 8, payload={"section_breadcrumb": "Etymology"}),
        ],
    )

    mark_index_status(client, "quiz_app-everest", "indexing", chunk_count=2)

    assert read_index_status(client, "quiz_app-everest") == "indexing"
