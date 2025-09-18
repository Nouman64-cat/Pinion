import threading
import time

from pinion.inmemory import InMemoryStorage
from pinion.registry import task
from pinion.retry import RetryPolicy
from pinion.types import Job, Status
from pinion.worker import Worker


def wait_until(predicate, timeout=1.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_worker_executes_registered_task():
    storage = InMemoryStorage()
    results: list[int] = []

    @task("worker-success")
    def add(a: int, b: int) -> None:
        results.append(a + b)

    job = Job("worker-success", args=(2, 3))
    storage.enqueue(job)

    worker = Worker(
        storage,
        retry=RetryPolicy(jitter=False),
        poll_timeout=0.05,
        visibility_timeout=None,
    )
    thread = threading.Thread(target=worker.run_forever, daemon=True)
    thread.start()

    try:
        assert wait_until(lambda: job.status is Status.SUCCESS)
    finally:
        worker.stop()
        thread.join(timeout=1.0)
        worker.join(1.0)

    assert results == [5]
    assert worker.metrics["processed"] == 1
    assert worker.metrics["succeeded"] == 1


def test_worker_retries_and_dead_letters_after_failures():
    storage = InMemoryStorage()
    attempts: list[float] = []

    @task("always-fail")
    def boom() -> None:
        attempts.append(time.time())
        raise RuntimeError("fail")

    storage.enqueue(Job("always-fail"))

    worker = Worker(
        storage,
        retry=RetryPolicy(max_retries=1, base_delay=0.01, jitter=False),
        poll_timeout=0.02,
        visibility_timeout=None,
    )
    thread = threading.Thread(target=worker.run_forever, daemon=True)
    thread.start()

    try:
        assert wait_until(lambda: len(storage._dlq) == 1, timeout=2.0)
    finally:
        worker.stop()
        thread.join(timeout=1.0)
        worker.join(1.0)

    assert len(attempts) >= 2
    assert worker.metrics["retried"] == 1
    assert worker.metrics["dead_lettered"] == 1


def test_worker_marks_timeout_and_dead_letters():
    storage = InMemoryStorage()

    @task("too-slow")
    def slow_task() -> None:
        time.sleep(0.15)

    storage.enqueue(Job("too-slow"))

    worker = Worker(
        storage,
        retry=RetryPolicy(max_retries=0, base_delay=0.01, jitter=False),
        poll_timeout=0.02,
        visibility_timeout=None,
        task_timeout=0.05,
    )
    thread = threading.Thread(target=worker.run_forever, daemon=True)
    thread.start()

    try:
        assert wait_until(lambda: len(storage._dlq) == 1, timeout=2.0)
    finally:
        worker.stop()
        thread.join(timeout=1.0)
        worker.join(1.0)

    assert storage._dlq[0][0].status is Status.FAILED
    assert worker.metrics["dead_lettered"] == 1
