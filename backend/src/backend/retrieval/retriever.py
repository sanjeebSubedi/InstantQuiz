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


def resolve_chunks_locally(chunks, blueprint):
    """Resolve planned breadcrumbs against the in-memory chunk list.

    Chunks sharing a breadcrumb (long sections split by the chunker) have
    their ``raw_text`` concatenated in build order with "\\n\\n" so the
    generator sees the whole section. Planned breadcrumbs with no local match
    are skipped with a warning; callers surface the resulting shortfall.
    """
    grouped = {}
    for chunk in chunks:
        grouped.setdefault(chunk["section_breadcrumb"], []).append(chunk)

    enriched = []
    for item in blueprint:
        matches = grouped.get(item["section_breadcrumb"])
        if not matches:
            logger.warning(
                "No chunk found for breadcrumb '%s'; skipping",
                item["section_breadcrumb"],
            )
            continue

        first = matches[0]
        item["article_title"] = first["article_title"]
        item["text"] = "\n\n".join(chunk["raw_text"] for chunk in matches)
        item["source_url"] = first["source_url"]
        enriched.append(item)

    return enriched