import logging

from qdrant_client import models

logger = logging.getLogger(__name__)


def retrieve_chunks(qdrant_client, collection_name, blueprint):
    logger.info("Retrieving context for %d blueprint sections", len(blueprint))
    enriched = []
    for item in blueprint:
        scroll_result = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="section_breadcrumb",
                        match=models.MatchValue(value=item["section_breadcrumb"]),
                    ),
                ]
            ),
        )

        records = scroll_result[0] if scroll_result else []
        if not records:
            logger.warning(
                "No chunk found for breadcrumb '%s'; skipping", item["section_breadcrumb"]
            )
            continue

        record = records[0]
        item["article_title"] = record.payload["article_title"]
        item["text"] = record.payload["raw_text"]
        item["source_url"] = record.payload["source_url"]
        enriched.append(item)

    return enriched