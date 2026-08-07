import logging

import tiktoken

logger = logging.getLogger(__name__)

encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(encoder.encode(text))


def build_outline(sections, article_title):
    outline = []
    for s in sections:
        preview = s["raw_text"][:150].rsplit(" ", 1)[0] + "..."
        outline.append(
            {
                "breadcrumb": s["section_breadcrumb"],
                "preview": preview,
                "token_count": count_tokens(s["raw_text"]),
            }
        )
    logger.info("Built outline for '%s' (%d sections)", article_title, len(outline))
    return {"article_title": article_title, "sections": outline}