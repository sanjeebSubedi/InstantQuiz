import time

from tests.fakes import QUESTION_KEYS, TOPIC


def poll_job(client, job_id, timeout=15.0):
    """Poll the job endpoint until it leaves `running` (or time runs out)."""
    deadline = time.monotonic() + timeout
    snapshots = []
    while time.monotonic() < deadline:
        response = client.get(f"/api/quizzes/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if not snapshots or len(body["questions"] or []) > len(
            snapshots[-1]["questions"] or []
        ):
            snapshots.append(body)
        if body["status"] in {"completed", "failed"}:
            return body, snapshots
        time.sleep(0.05)
    raise AssertionError("job did not finish before timeout")


def test_unknown_job_returns_404(harness):
    with harness.api_client() as client:
        response = client.get("/api/quizzes/does-not-exist")

    assert response.status_code == 404


def test_full_polling_contract(harness):
    with harness.api_client() as client:
        create_response = client.post("/api/quizzes", json={"topic": TOPIC})
        assert create_response.status_code == 202
        created = create_response.json()
        assert set(created) == {"job_id", "status"}
        assert created["status"] == "running"

        final, snapshots = poll_job(client, created["job_id"])

    assert final["status"] == "completed"
    assert final["job_id"] == created["job_id"]
    assert final["error"] is None

    # Questions stream: partial snapshots grow monotonically to the total.
    sizes = [len(s["questions"] or []) for s in snapshots]
    assert sizes[-1] == 10
    assert all(a <= b for a, b in zip(sizes, sizes[1:]))

    for question in final["questions"]:
        assert set(question) == QUESTION_KEYS


def test_failed_job_surfaces_error(harness, monkeypatch):
    from backend.services import quiz_service as quiz_service_module

    def boom(*args, **kwargs):
        raise RuntimeError("planner exploded")

    monkeypatch.setattr(quiz_service_module, "plan_quiz", boom)
    with harness.api_client() as client:
        create_response = client.post("/api/quizzes", json={"topic": TOPIC})
        assert create_response.status_code == 202

        final, _ = poll_job(client, create_response.json()["job_id"])

    assert final["status"] == "failed"
    assert "planner exploded" in final["error"]
