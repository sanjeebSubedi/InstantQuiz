import logging

from backend.services.quiz_service import generate_quiz_for_topic


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    topic = input("Enter a topic: ")

    result = {"questions": []}

    def on_batch(batch):
        result["questions"].extend(batch)

    generate_quiz_for_topic(topic, on_batch)

    for index, question in enumerate(result["questions"], start=1):
        print(f"\nQ{index}: {question['question']}")
        for i, option in enumerate(question["options"], start=1):
            print(f"   {i}. {option}")
        print(f"   Correct: {question['correct_answer']}")

    logger = logging.getLogger(__name__)
    logger.info("Pipeline finished: %d questions", len(result["questions"]))


if __name__ == "__main__":
    main()