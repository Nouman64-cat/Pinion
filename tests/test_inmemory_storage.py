import time

from pinion.inmemory import InMemoryStorage
from pinion.types import Job, Status


def test_enqueue_dequeue_updates_status_and_attempts():
    storage = InMemoryStorage()
    job = Job("demo")

    storage.enqueue(job)
    assert storage.size() == 1

    dequeued = storage.dequeue(timeout=0.05)

    assert dequeued is job
    assert job.status is Status.RUNNING
    assert job.attempts == 1
    assert storage.size() == 0


def test_mark_done_marks_success():
    storage = InMemoryStorage()
    job = Job("demo")
    storage.enqueue(job)
    job = storage.dequeue(timeout=0.05)

    storage.mark_done(job)

    assert job.status is Status.SUCCESS
    assert storage.size() == 0


def test_reap_stale_moves_job_back_to_queue():
    storage = InMemoryStorage()
    job = Job("demo")
    storage.enqueue(job)
    dequeued = storage.dequeue(timeout=0.05)
    assert dequeued is job
    # simulate stale heartbeat
    storage._heartbeats[job.id] = time.time() - 5

    reaped = storage.reap_stale(visibility_timeout=0.1)

    assert reaped == 1
    assert job.status is Status.PENDING
    assert storage.size() == 1


def test_dead_letter_records_entry():
    storage = InMemoryStorage()
    job = Job("demo")

    storage.dead_letter(job, RuntimeError("boom"))

    # Access internal DLQ list for verification in tests
    assert storage._dlq
    saved_job, error_repr, timestamp = storage._dlq[-1]
    assert saved_job is job
    assert "RuntimeError" in error_repr
    assert timestamp <= time.time()
