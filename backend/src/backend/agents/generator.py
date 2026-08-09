import logging
from time import perf_counter

from backend.agents.models import QuestionsResponse
from backend.agents.prompts import (
    QUESTION_GENERATOR_SYSTEM_PROMPT,
    build_batch_prompt,
)

logger = logging.getLogger(__name__)


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


def generate_quiz(llm_client, blueprint, max_retries=2):
    batches = batch_questions(blueprint)
    total_batches = len(batches)

    for index, batch in enumerate(batches, start=1):
        required = sum(int(item["question_count"]) for item in batch)
        logger.info(
            "Generating questions for batch %d/%d (required %d)",
            index,
            total_batches,
            required,
        )

        response = []
        attempts = 0
        while len(response) < required and attempts <= max_retries:
            attempts += 1
            start = perf_counter()
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

        if len(response) < required:
            logger.warning(
                "Batch %d/%d shortfall: produced %d/%d questions after %d attempts",
                index,
                total_batches,
                len(response),
                required,
                attempts,
            )
        yield response