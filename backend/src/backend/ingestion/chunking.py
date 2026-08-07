import logging
from urllib.parse import quote

import tiktoken

logger = logging.getLogger(__name__)

encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(encoder.encode(text))


MIN_TOKENS = 50
MAX_TOKENS = 400


def build_chunks(sections, article_title):
    chunks = []
    buffer = None

    for section in sections:
        tokens = count_tokens(section["text"])

        if tokens < MIN_TOKENS:
            if buffer is None:
                buffer = section
            else:
                buffer["text"] += "\n\n" + section["text"]
            continue

        if buffer is not None:
            chunks.extend(split_if_needed(buffer, article_title))
            buffer = None
        chunks.extend(split_if_needed(section, article_title))

    if buffer is not None:
        chunks.extend(split_if_needed(buffer, article_title))

    logger.info("Built %d chunks from %d sections", len(chunks), len(sections))
    return chunks


def split_if_needed(section, article_title):
    text = section["text"]
    if count_tokens(text) <= MAX_TOKENS:
        return [
            format_chunk(article_title, section["title"], section["breadcrumb"], text)
        ]

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    sub_chunks, current, current_tokens = [], [], 0

    for para in paragraphs:
        para_tokens = count_tokens(para)
        if current and current_tokens + para_tokens > MAX_TOKENS:
            sub_chunks.append("\n\n".join(current))
            current = [current[-1], para]  # 1-paragraph overlap
            current_tokens = count_tokens(current[0]) + para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        sub_chunks.append("\n\n".join(current))

    return [
        format_chunk(article_title, section["title"], section["breadcrumb"], sc)
        for sc in sub_chunks
    ]


def get_section_url(article_title, section_title):
    base = f"https://en.wikipedia.org/wiki/{quote(article_title.replace(' ', '_'))}"
    if section_title == "Introduction":
        return base  # intro has no heading, so no anchor to link to
    anchor = quote(section_title.replace(" ", "_"))
    return f"{base}#{anchor}"


def format_chunk(article_title, section_title, breadcrumb, text):
    return {
        "text": f"Article: {article_title}\nSection: {breadcrumb}\n\n{text}",
        "article_title": article_title,
        "section_title": section_title,
        "section_breadcrumb": breadcrumb,
        "source_url": get_section_url(article_title, section_title),
        "raw_text": text,
    }
