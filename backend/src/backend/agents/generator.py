import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from backend.agents.models import QuestionsResponse
from backend.agents.prompts import (
    QUESTION_GENERATOR_SYSTEM_PROMPT,
    build_batch_prompt,
)

logger = logging.getLogger(__name__)

# Per-job tail concurrency: 1 eager sync call + 2 concurrent tail calls.
TAIL_MAX_WORKERS = 2
# Process-wide cap on in-flight generator LLM calls (~2 jobs x 3 batches)
# so simultaneous quizzes queue instead of hammering OpenRouter/Gemini.
MAX_CONCURRENT_PROVIDER_CALLS = 6
_provider_call_slots = threading.BoundedSemaphore(MAX_CONCURRENT_PROVIDER_CALLS)


def batch_questions(blueprint, first_batch_max=3, batch_max=4):
    """Split blueprint into batches capped by batch count.

    The first batch is kept small (first_batch_max) so the first results reach
    the user quickly; subsequent batches are capped at batch_max. A single
    section may be split across batches by reducing its per-batch count.
    """
    batches = []
    current = []
    remaining = first_batch_max

    counter = 0
    for item in blueprint:
        counter += 1
        count = int(item["question_count"])
        while count > 0:
            if remaining == 0:
                batches.append(current)
                current = []
                remaining = batch_max
            take = min(count, remaining)
            current.append({**item, "question_count": take, "section_index": counter})
            count -= take
            remaining -= take

    if current:
        batches.append(current)
    return batches


def _generate_batch(llm_client, batch, index, total_batches, max_retries):
    """Generate one batch, retrying short responses and provider errors.

    After the final attempt a non-empty partial result is returned so callers
    surface the shortfall; a batch left with nothing re-raises the last error
    so its position decides the outcome (an eager first-batch failure fails
    the job, a tail failure forfeits only that batch).
    """
    required = sum(int(item["question_count"]) for item in batch)
    logger.info(
        "Generating questions for batch %d/%d (required %d)",
        index,
        total_batches,
        required,
    )

    response = []
    last_error = None
    attempts = 0
    while len(response) < required and attempts <= max_retries:
        attempts += 1
        try:
            start = perf_counter()
            with _provider_call_slots:
                candidate = llm_client.create(
                    messages=[
                        {"role": "system", "content": QUESTION_GENERATOR_SYSTEM_PROMPT},
                        {"role": "user", "content": build_batch_prompt(batch)},
                    ],
                    response_model=list[QuestionsResponse],
                    extra_body={"provider": {"require_parameters": True}},
                )
            logger.info(
                "Batch %d/%d attempt %d produced %d/%d questions in %.2fs",
                index,
                total_batches,
                attempts,
                len(candidate),
                required,
                perf_counter() - start,
            )
            response = candidate[:required]
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Batch %d/%d attempt %d failed: %s: %s",
                index,
                total_batches,
                attempts,
                type(exc).__name__,
                exc,
            )

    if len(response) < required:
        logger.warning(
            "Batch %d/%d shortfall: produced %d/%d questions after %d attempts",
            index,
            total_batches,
            len(response),
            required,
            attempts,
        )
    if not response and last_error is not None:
        raise last_error
    return response


def generate_quiz(llm_client, blueprint, max_retries=2):
    """Yield question batches: first eagerly, then tail batches concurrently.

    Batches are independent, so all but the first run in a thread pool (the
    pipeline itself already runs off the event loop). Results are yielded in
    original batch order regardless of completion order, keeping streamed
    output and ``section_index`` references stable. Each batch retries
    internally; batches neither cancel nor block each other.
    """
    batches = batch_questions(blueprint)
    total_batches = len(batches)
    if not batches:
        return

    # The first batch is awaited here so time-to-first-question is unchanged.
    yield _generate_batch(llm_client, batches[0], 1, total_batches, max_retries)

    if total_batches == 1:
        return

    with ThreadPoolExecutor(max_workers=TAIL_MAX_WORKERS) as executor:
        # Each future owns its retry loop; siblings are never cancelled or
        # blocked, so one batch failing hard only forfeits its own questions.
        futures = [
            executor.submit(
                _generate_batch,
                llm_client,
                batch,
                position,
                total_batches,
                max_retries,
            )
            for position, batch in enumerate(batches[1:], start=2)
        ]
        for position, future in enumerate(futures, start=2):
            try:
                yield future.result()
            except Exception:
                logger.exception(
                    "Batch %d/%d failed; skipping its questions",
                    position,
                    total_batches,
                )