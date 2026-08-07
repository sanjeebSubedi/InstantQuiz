import logging
from time import perf_counter

from backend.agents.models import QuizOutline
from backend.agents.prompts import PLANNER_SYSTEM_PROMPT, build_planner_prompt

logger = logging.getLogger(__name__)


def plan_quiz(llm_client, outline, topic, difficulty, question_count):
    logger.info("Planning quiz: topic='%s', difficulty='%s', %d questions", topic, difficulty, question_count)
    start = perf_counter()

    planner_prompt = build_planner_prompt(
        outline, topic, difficulty, question_count
    )

    response = llm_client.create(
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": planner_prompt},
        ],
        response_model=list[QuizOutline],
        extra_body={"provider": {"require_parameters": True}},
    )

    blueprint = [
        item.model_dump(exclude={"reason"})
        for item in response
    ]
    planned = sum(item["question_count"] for item in blueprint)
    logger.info(
        "Planner produced blueprint for %d sections (%d questions) in %.2fs",
        len(blueprint),
        planned,
        perf_counter() - start,
    )
    return blueprint