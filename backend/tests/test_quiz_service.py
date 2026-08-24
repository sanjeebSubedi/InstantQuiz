from tests.fakes import ARTICLE_TITLE, QUESTION_KEYS, TOPIC


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


def test_collection_is_indexed_and_reusable_marker_free(harness):
    """Pipeline behavior is unchanged: indexing stays on the critical path."""
    harness.run_service()

    collection_name = next(
        c.name for c in harness.qdrant_client.get_collections().collections
    )
    points, _ = harness.qdrant_client.scroll(collection_name=collection_name)
    assert len(points) >= 3
