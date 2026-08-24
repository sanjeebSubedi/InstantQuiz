"""Bounds on generator concurrency: per-job tail workers and a process-wide
cap on in-flight LLM calls, asserted at the service seam."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.agents import generator as generator_module
from backend.agents.models import QuestionsResponse
from backend.services import quiz_service as quiz_service_module
from tests.fakes import FakeLlmClient


def test_tail_executor_is_bounded_to_two_workers(harness, monkeypatch):
    """Tail batches share a ThreadPoolExecutor(max_workers=2): 1 eager sync +
    2 concurrent calls per job."""
    captured = {}

    def recording_executor(*args, **kwargs):
        captured.update(kwargs)
        return ThreadPoolExecutor(*args, **kwargs)

    monkeypatch.setattr(generator_module, "ThreadPoolExecutor", recording_executor)

    result, batches = harness.run_service()

    assert captured == {"max_workers": 2}
    assert result["question_count"] == 10
    assert [len(batch) for batch in batches] == [3, 4, 3]


class GlobalBoundProbe(FakeLlmClient):
    """Tracks peak concurrent generator calls across all jobs."""

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._in_flight = 0
        self.peak = 0

    def create(self, messages=None, response_model=None, extra_body=None, **kwargs):
        if response_model == list[QuestionsResponse]:
            with self._lock:
                self._in_flight += 1
                self.peak = max(self.peak, self._in_flight)
            try:
                time.sleep(0.05)
                return super().create(
                    messages=messages,
                    response_model=response_model,
                    extra_body=extra_body,
                    **kwargs,
                )
            finally:
                with self._lock:
                    self._in_flight -= 1
        return super().create(
            messages=messages,
            response_model=response_model,
            extra_body=extra_body,
            **kwargs,
        )


def test_global_semaphore_caps_concurrent_calls_across_jobs(harness, monkeypatch):
    """Five simultaneous quizzes must never exceed six in-flight LLM calls;
    they queue on the process-wide BoundedSemaphore instead."""
    llm = GlobalBoundProbe()
    monkeypatch.setattr(quiz_service_module, "get_llm_client", lambda *a, **k: llm)

    outcomes = [None] * 5

    def run(position):
        outcomes[position] = harness.run_service()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)

    # 5 jobs x 3 batches = 15 generator calls, all questions delivered.
    assert llm.generator_calls == 15
    for result, batches in outcomes:
        assert result["question_count"] == 10
        assert len(batches) == 3
    # BoundedSemaphore(6) caps in-flight calls well below the 10 an unbounded
    # 5-job run could reach (each job may hold two calls at once).
    assert llm.peak <= 6
