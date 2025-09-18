import time

from pinion.sqlite_storage import SqliteStorage
from pinion.types import Job, Status


def test_sqlite_enqueue_dequeue_and_mark_done(tmp_path):
    storage = SqliteStorage(str(tmp_path / "queue.db"))
    job = Job("demo", args=(1,), kwargs={"x": 2})

    storage.enqueue(job)
    assert storage.size() == 1

    dequeued = storage.dequeue(timeout=0.1)
    assert dequeued is not None
    assert dequeued.id == job.id
    assert dequeued.status is Status.RUNNING
    assert dequeued.attempts == 1

    storage.mark_done(dequeued)
    row = storage._conn.execute("SELECT status FROM jobs WHERE id=?;", (job.id,)).fetchone()
    assert row[0] == "SUCCESS"


def test_sqlite_reap_stale_requeues_job(tmp_path):
    storage = SqliteStorage(str(tmp_path / "queue.db"))
    job = Job("demo")

    storage.enqueue(job)
    first = storage.dequeue(timeout=0.1)
    assert first is not None

    # age the heartbeat to force a reap
    storage._conn.execute(
        "UPDATE jobs SET heartbeat_at=? WHERE id=?;", (time.time() - 5, job.id)
    )

    reaped = storage.reap_stale(visibility_timeout=0.1)
    assert reaped == 1

    second = storage.dequeue(timeout=0.1)
    assert second is not None
    assert second.id == job.id
    assert second.attempts == first.attempts + 1


def test_sqlite_dead_letter_persists_entry(tmp_path):
    storage = SqliteStorage(str(tmp_path / "queue.db"))
    job = Job("demo")

    storage.enqueue(job)
    claimed = storage.dequeue(timeout=0.1)
    assert claimed is not None

    storage.dead_letter(claimed, RuntimeError("boom"))

    row = storage._conn.execute(
        "SELECT id, func_name, attempts, error FROM dlq WHERE id=?;", (job.id,)
    ).fetchone()
    assert row is not None
    assert row[0] == job.id
    assert row[1] == job.func_name
    assert row[2] == claimed.attempts
    assert "RuntimeError" in row[3]
