"""In-process deterministic fakes for the quiz generation pipeline.

These stand in for the three external systems the orchestration service
touches: Wikipedia (HTTP), Qdrant + Gemini embeddings, and the OpenRouter
LLM (instructor client). Everything runs locally with no network access.
"""

import re

from backend.agents.models import QuestionsResponse, QuizOutline
from backend.sources.wikipedia.client import WikipediaClient

TOPIC = "everest"
ARTICLE_TITLE = "Mount Everest"

# Shape of a streamed API question, asserted at both the service and API seams.
QUESTION_KEYS = {"section_index", "question", "options", "correct_answer", "source_url"}

# Canned wikitext; every section is long enough to survive the >=50 token
# minimum in chunking.build_chunks, so each becomes its own chunk with a
# predictable breadcrumb.
WIKITEXT = """\
Mount Everest is Earth's highest mountain above sea level, located in the \
Mahalangur Himal sub-range of the Himalayas. The China–Nepal border runs \
across its summit point. Its elevation of 8,848.86 m was most recently \
established in 2020 by Chinese and Nepali authorities. Mount Everest \
attracts many climbers, some of them highly experienced. There are two main \
climbing routes, one approaching the summit from the southeast in Nepal and \
the other from the north in Tibet. While not posing substantial technical \
climbing challenges on the standard route, Everest presents dangers such as \
altitude sickness, weather and wind, as well as significant hazards from \
avalanches and the Khumbu Icefall.

== Etymology ==
The Tibetan name for Everest is Qomolangma, spelled Jo-mo-glang-ma in \
official romanizations. The Nepali name is Sagarmatha. In 1865, the Great \
Trigonometrical Survey of India established the first published height of \
Everest, then known as Peak XV, at 29,002 ft. The Royal Geographical Society \
named it Mount Everest in honour of Sir George Everest, a former Surveyor \
General of India. The name was objected to by many people at the time, but \
the Royal Geographical Society prevailed and the name has been used ever \
since in the English-speaking world.

== History ==
The Great Trigonometrical Survey of India began in 1802 and took decades to \
complete. In 1856 Andrew Waugh announced that Peak XV was the highest \
mountain yet surveyed. In 1921 the first British reconnaissance expedition \
reached the northern side of the mountain. Early expeditions climbed from \
the north Tibetan side because Nepal did not allow foreigners to enter the \
country. In 1953, the ninth British expedition led by John Hunt returned to \
Nepal, and Edmund Hillary and Tenzing Norgay reached the summit on 29 May \
1953 via the south col route.

== Climbing routes ==
Mount Everest has two main climbing routes: the south-east ridge from Nepal \
and the north ridge from Tibet, as well as many other less frequently \
climbed routes. Of the two main routes, the south-east ridge is technically \
easier and more frequently used. It was the route used by Hillary and \
Tenzing in 1953 and the first recognized of 15 routes to the top by 1996. \
Most attempts are made during May, before the summer monsoon season, when \
the jet stream migrates north and wind speeds at the summit drop \
dramatically.
"""

# Planner blueprint referencing breadcrumbs that exist among the chunks above.
# 3 + 4 + 3 = 10 questions.
BLUEPRINT = [
    {
        "section_breadcrumb": "Introduction",
        "question_count": 3,
        "difficulty": "medium",
        "reason": "core facts",
    },
    {
        "section_breadcrumb": "History",
        "question_count": 4,
        "difficulty": "medium",
        "reason": "survey history",
    },
    {
        "section_breadcrumb": "Climbing routes",
        "question_count": 3,
        "difficulty": "medium",
        "reason": "routes detail",
    },
]


class FakeWikipediaClient(WikipediaClient):
    """Real section parsing over a canned article; no HTTP."""

    def resolve_topic_to_article(self, topic):
        return {"title": ARTICLE_TITLE, "content": WIKITEXT}


# One prompt block per section: header line through its question count.
SECTION_BLOCK_RE = re.compile(
    r"Section (\d+):\n"
    r"Article: .+\n"
    r"Breadcrumb: (.+)\n"
    r"Difficulty: .+\n"
    r"Number of questions required: (\d+)"
)


class FakeLlmClient:
    """Stands in for the instructor-wrapped OpenRouter client.

    The planner call returns BLUEPRINT; each generator call answers exactly
    the sections requested in its user prompt, so shortfalls or retries never
    trigger and question counts line up deterministically. Batches are read
    from the prompt rather than a call counter so responses stay correct even
    when generator batches execute concurrently.
    """

    def __init__(self):
        self.blueprint = BLUEPRINT
        self.planner_calls = 0
        self.generator_calls = 0
        # User prompts of generator calls, for asserting resolved section text.
        self.generator_prompts = []

    def set_blueprint(self, blueprint):
        self.blueprint = blueprint

    def _questions_for_prompt(self, prompt):
        questions = []
        for index, breadcrumb, count in SECTION_BLOCK_RE.findall(prompt):
            for _ in range(int(count)):
                questions.append(
                    QuestionsResponse(
                        section_index=int(index),
                        question=f"Question about {breadcrumb}?",
                        options=["A", "B", "C", "D"],
                        correct_answer="A",
                        explanation="deterministic fixture",
                    )
                )
        return questions

    def create(self, messages=None, response_model=None, extra_body=None, **kwargs):
        if response_model == list[QuizOutline]:
            self.planner_calls += 1
            return [QuizOutline(**item) for item in self.blueprint]

        assert response_model == list[QuestionsResponse]
        self.generator_calls += 1
        self.generator_prompts.append(
            next(m["content"] for m in messages if m["role"] == "user")
        )
        return self._questions_for_prompt(self.generator_prompts[-1])


def fake_get_embedding(client, text, emb_model="gemini-embedding-2"):
    # Deterministic per-text vectors; retrieval scrolls by payload filter, so
    # only determinism matters, not similarity quality.
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in (digest * 96)[:1536]]
