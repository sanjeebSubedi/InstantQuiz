import json
import sqlite3
import uuid
from datetime import datetime, timezone

from backend.core.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS quizzes (
    job_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    question_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    questions_json TEXT,
    error TEXT
);
"""


def _connect():
    conn = sqlite3.connect(config.QUIZ_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(SCHEMA)


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_job(topic, difficulty, question_count, status="queued"):
    job_id = uuid.uuid4().hex
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO quizzes (job_id, topic, difficulty, question_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, topic, difficulty, question_count, status, now, now),
        )
    return job_id


def get_job(job_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM quizzes WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _to_dict(row)


def update_status(job_id, status):
    with _connect() as conn:
        conn.execute(
            "UPDATE quizzes SET status = ?, updated_at = ? WHERE job_id = ?",
            (status, _now(), job_id),
        )


def append_questions(job_id, questions):
    existing = []
    with _connect() as conn:
        row = conn.execute(
            "SELECT questions_json FROM quizzes WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row and row["questions_json"]:
            existing = json.loads(row["questions_json"])
    existing.extend(questions)
    with _connect() as conn:
        conn.execute(
            "UPDATE quizzes SET questions_json = ?, updated_at = ? WHERE job_id = ?",
            (json.dumps(existing), _now(), job_id),
        )


def complete_job(job_id):
    with _connect() as conn:
        conn.execute(
            "UPDATE quizzes SET status = 'completed', updated_at = ? WHERE job_id = ?",
            (_now(), job_id),
        )


def fail_job(job_id, error):
    with _connect() as conn:
        conn.execute(
            "UPDATE quizzes SET status = 'failed', error = ?, updated_at = ? WHERE job_id = ?",
            (error, _now(), job_id),
        )


def _to_dict(row):
    if row is None:
        return None
    return {
        "job_id": row["job_id"],
        "topic": row["topic"],
        "difficulty": row["difficulty"],
        "question_count": row["question_count"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "questions": (
            json.loads(row["questions_json"]) if row["questions_json"] else None
        ),
        "error": row["error"],
    }