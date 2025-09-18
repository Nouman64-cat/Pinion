from pinion.inmemory import InMemoryStorage
from pinion.types import Job, Status


def test_job_defaults_to_pending_status():
    job = Job("demo")

    assert job.status is Status.PENDING
    assert job.attempts == 0


def test_storage_size_matches_enqueued_jobs():
    storage = InMemoryStorage()

    storage.enqueue(Job("demo"))
    storage.enqueue(Job("other"))

    assert storage.size() == 2
