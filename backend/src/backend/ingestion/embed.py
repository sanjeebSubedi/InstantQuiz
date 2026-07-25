from google.genai import types
from qdrant_client.models import Distance, PointStruct, VectorParams


def get_embedding(client, text, emb_model="gemini-embedding-2"):
    result = client.models.embed_content(
        model=emb_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=1536),
    )

    return result.embeddings[0].values


def store_embeddings(qdrant_client, collection_name, data_to_embed):

    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    pointstructs = []
    for i, data in enumerate(data_to_embed):
        embedding = get_embedding(data["text"])
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
