import json
import re
import sqlite3
from datetime import datetime, timezone

import tiktoken

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
    return {"article_title": article_title, "sections": outline}


def slugify_title(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def get_connection(db_path="../quiz_outlines.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_outline_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS outlines (
            article_id    TEXT PRIMARY KEY,
            article_title TEXT UNIQUE NOT NULL,
            outline_json  TEXT NOT NULL,
            fetched_at    TEXT NOT NULL
        )
    """)
    conn.commit()


def save_outline(conn, article_title, outline_dict):
    article_id = slugify_title(article_title)
    conn.execute(
        """
        INSERT INTO outlines (article_id, article_title, outline_json, fetched_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(article_id) DO UPDATE SET
            outline_json = excluded.outline_json,
            fetched_at   = excluded.fetched_at
    """,
        (
            article_id,
            article_title,
            json.dumps(outline_dict),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return article_id


def get_outline(conn, article_title):
    row = conn.execute(
        "SELECT article_id, outline_json, fetched_at FROM outlines WHERE article_title = ?",
        (article_title,),
    ).fetchone()
    if row is None:
        return None
    return {
        "article_id": row["article_id"],
        "outline": json.loads(row["outline_json"]),
        "fetched_at": row["fetched_at"],
    }
