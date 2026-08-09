import asyncio
import logging

from fastapi import APIRouter, HTTPException

from backend.api.models import QuizCreateRequest, QuizCreateResponse, QuizJobResponse
from backend.core.config import config
from backend.services.quiz_service import generate_quiz_for_topic
from backend.storage import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])

_jobs: dict[str, asyncio.Task] = {}


def _submit_job(job_id: str, topic: str):
    difficulty = config.DEFAULT_DIFFICULTY
    question_count = config.DEFAULT_QUESTION_COUNT

    async def _run():
        db.update_status(job_id, "running")
        try:
            await asyncio.to_thread(
                generate_quiz_for_topic,
                topic,
                lambda batch: db.append_questions(job_id, batch),
                difficulty,
                question_count,
            )
            db.complete_job(job_id)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            logger.exception("Job %s failed: %s", job_id, exc)
            db.fail_job(job_id, str(exc))

    _jobs[job_id] = asyncio.create_task(_run())


@router.post("", status_code=202, response_model=QuizCreateResponse)
async def create_quiz(payload: QuizCreateRequest):
    job_id = db.create_job(
        payload.topic,
        config.DEFAULT_DIFFICULTY,
        config.DEFAULT_QUESTION_COUNT,
    )
    _submit_job(job_id, payload.topic)

    return QuizCreateResponse(job_id=job_id, status="running")


@router.get("/{job_id}", response_model=QuizJobResponse)
async def get_quiz(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="quiz not found")
    return QuizJobResponse(
        job_id=job["job_id"],
        topic=job["topic"],
        status=job["status"],
        questions=job["questions"],
        error=job["error"],
    )