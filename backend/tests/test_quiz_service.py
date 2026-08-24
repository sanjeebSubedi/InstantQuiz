import logging
import threading

from backend.agents.models import QuestionsResponse

from tests.fakes import (
    ARTICLE_TITLE,
    QUESTION_KEYS,
    TOPIC,
    FakeLlmClient,
    FakeWikipediaClient,
)


def test_service_generates_all_questions_in_order(harness):
    result, batches = harness.run_service()

    assert result == {
        "topic": TOPIC,
        "article_title": ARTICLE_TITLE,
        "difficulty": "medium",
        "question_count": 10,
    }
    assert len(batches) == 3
    assert [len(batch) for batch in batches] == [3, 4, 3]

    flattened = [q for batch in batches for q in batch]
    assert len(flattened) == 10
    for question in flattened:
        assert set(question) == QUESTION_KEYS
        assert isinstance(question["section_index"], int)
        assert 1 <= question["section_index"] <= 3
        assert len(question["options"]) == 4
        assert question["correct_answer"] in question["options"]


def test_section_index_is_stable_across_batches(harness):
    _, batches = harness.run_service()

    # Blueprint: Introduction=1 (3q), History=2 (4q), Climbing routes=3 (3q).
    assert {q["section_index"] for q in batches[0]} == {1}
    assert {q["section_index"] for q in batches[1]} == {2}
    assert {q["section_index"] for q in batches[2]} == {3}


def test_source_urls_map_to_wikipedia_sections(harness):
    _, batches = harness.run_service()

    expected = {
        1: f"https://en.wikipedia.org/wiki/{ARTICLE_TITLE.replace(' ', '_')}",
        2: f"https://en.wikipedia.org/wiki/{ARTICLE_TITLE.replace(' ', '_')}#History",
        3: f"https://en.wikipedia.org/wiki/{ARTICLE_TITLE.replace(' ', '_')}#Climbing_routes",
    }
    for batch in batches:
        for question in batch:
            assert question["source_url"] == expected[question["section_index"]]


# Two ~equal paragraphs whose combined size forces chunking to split them;
# both sub-chunks keep the "Geology" breadcrumb.
def _paragraph(seed, sentences=12):
    return " ".join(
        f"Sample {seed}-{i} contains quartz, feldspar, and biotite grains arranged "
        "in a coarse crystalline matrix formed under high pressure."
        for i in range(sentences)
    )


GEOLOGY_P1 = _paragraph("a")
GEOLOGY_P2 = _paragraph("b")


class SplitSectionWikipediaClient(FakeWikipediaClient):
    """Serves a Geology section long enough to split into two chunks."""

    def resolve_topic_to_article(self, topic):
        return {"title": ARTICLE_TITLE, "content": ""}

    def parse_sections(self, content):
        return [
            {
                "title": "Geology",
                "level": 2,
                "breadcrumb": "Geology",
                "text": f"{GEOLOGY_P1}\n\n{GEOLOGY_P2}",
            }
        ]


def test_split_section_chunks_are_concatenated_for_generation(harness, monkeypatch):
    from backend.services import quiz_service as quiz_service_module

    monkeypatch.setattr(
        quiz_service_module, "WikipediaClient", SplitSectionWikipediaClient
    )
    harness.llm.set_blueprint(
        [
            {
                "section_breadcrumb": "Geology",
                "question_count": 10,
                "difficulty": "medium",
                "reason": "split section",
            }
        ]
    )

    result, batches = harness.run_service()

    assert result["question_count"] == 10
    # Both sub-chunks share the breadcrumb, so their raw_text is concatenated
    # in build order with "\\n\\n" (the second sub-chunk repeats P1 via overlap).
    expected_text = f"{GEOLOGY_P1}\n\n{GEOLOGY_P1}\n\n{GEOLOGY_P2}"
    assert len(harness.llm.generator_prompts) == 3
    for prompt in harness.llm.generator_prompts:
        assert expected_text in prompt
    assert all(
        question["source_url"]
        == f"https://en.wikipedia.org/wiki/{ARTICLE_TITLE.replace(' ', '_')}#Geology"
        for batch in batches
        for question in batch
    )


class OutOfOrderLlmClient(FakeLlmClient):
    """Holds the History batch open until the Climbing routes batch starts.

    Forces tail batches to finish out of order (Climbing routes first) so the
    service's on_batch delivery order can be checked independently of LLM
    completion order.
    """

    def __init__(self):
        super().__init__()
        self.climbing_batch_started = threading.Event()
        # Section completion order, appended when each generator call returns.
        self.completion_order = []

    def create(self, messages=None, response_model=None, extra_body=None, **kwargs):
        if response_model == list[QuestionsResponse]:
            prompt = next(m["content"] for m in messages if m["role"] == "user")
            if "Breadcrumb: History" in prompt:
                assert self.climbing_batch_started.wait(timeout=5), (
                    "History batch ran alone; tail batches are not concurrent"
                )
                self.completion_order.append("history")
            elif "Breadcrumb: Climbing routes" in prompt:
                self.climbing_batch_started.set()
                self.completion_order.append("climbing routes")
        return super().create(
            messages=messages,
            response_model=response_model,
            extra_body=extra_body,
            **kwargs,
        )


def test_tail_batches_run_concurrently_but_persist_in_batch_order(
    harness, monkeypatch
):
    from backend.services import quiz_service as quiz_service_module

    llm = OutOfOrderLlmClient()
    monkeypatch.setattr(quiz_service_module, "get_llm_client", lambda *a, **k: llm)

    result, batches = harness.run_service()

    # Climbing routes finished before History, yet batches were persisted 1,2,3.
    assert llm.completion_order == ["climbing routes", "history"]
    assert [len(batch) for batch in batches] == [3, 4, 3]
    assert [{q["section_index"] for q in batch} for batch in batches] == [
        {1},
        {2},
        {3},
    ]
    assert result["question_count"] == 10


def test_tail_batch_failure_yields_partial_quiz(harness, monkeypatch, caplog):
    """A hard failure in one tail batch must not fail the whole job."""
    import logging

    from backend.services import quiz_service as quiz_service_module

    class FailingTailLlmClient(FakeLlmClient):
        def create(self, messages=None, response_model=None, extra_body=None, **kwargs):
            if response_model == list[QuestionsResponse]:
                prompt = next(
                    m["content"] for m in messages if m["role"] == "user"
                )
                if "Breadcrumb: History" in prompt:
                    raise RuntimeError("provider outage")
            return super().create(
                messages=messages,
                response_model=response_model,
                extra_body=extra_body,
                **kwargs,
            )

    monkeypatch.setattr(
        quiz_service_module, "get_llm_client", lambda *a, **k: FailingTailLlmClient()
    )

    with caplog.at_level(logging.WARNING):
        result, batches = harness.run_service()

    # History (batch 2, 4q) is lost; eager batch 1 and tail batch 3 still stream.
    assert result["question_count"] == 6
    assert [len(batch) for batch in batches] == [3, 3]
    assert [{q["section_index"] for q in batch} for batch in batches] == [{1}, {3}]
    assert any("Batch 2/3" in message for message in caplog.messages)
    assert any("Planned 10 questions but generated 6" in message for message in caplog.messages)


def test_missing_breadcrumb_is_skipped_with_shortfall_warning(harness, caplog):
    harness.llm.set_blueprint(
        [
            {
                "section_breadcrumb": "Introduction",
                "question_count": 5,
                "difficulty": "medium",
                "reason": "core facts",
            },
            {
                "section_breadcrumb": "Nonexistent Section",
                "question_count": 3,
                "difficulty": "medium",
                "reason": "stale outline",
            },
        ]
    )

    with caplog.at_level(logging.WARNING):
        result, batches = harness.run_service()

    # The unmatched planned section is skipped, not fatal.
    assert result["question_count"] == 5
    assert [len(batch) for batch in batches] == [3, 2]
    assert all(
        question["section_index"] == 1 for batch in batches for question in batch
    )
    warnings = [record.getMessage() for record in caplog.records]
    assert any("Nonexistent Section" in message for message in warnings)
    assert any("Planned 10 questions but generated 5" in message for message in warnings)
