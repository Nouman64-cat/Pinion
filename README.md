# Pinion

Pinion is a tiny, pluggable job queue and worker for Python. It provides a simple `@task` registry, an in-memory queue for quick starts, and a durable SQLite backend for cross-process work, plus a retry policy with exponential backoff.

## Features

- In-memory queue with thread-safe `Condition` coordination
- Durable SQLite storage with atomic job claim (WAL) across processes
- Pluggable `Storage` protocol (SPI) for custom backends
- Task registry via `@task` decorator (case-insensitive names)
- Worker loop with polling, retries, and graceful stop
- Exponential backoff retries with optional jitter and cap
- Job lifecycle tracking: `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`

## Requirements

- Python 3.12+

## Installation

- From source (local dev): `pip install -e .`
- CLI entry point installs as `pinion`

## Quick Start

### CLI demo

Run the bundled demo (registers a simple `add` task and processes one job):

```bash
pinion
```

### Library usage (in-memory)

```python
import threading, time
from pinion import task, Job, InMemoryStorage, Worker, RetryPolicy

@task()
def add(a: int, b: int) -> int:
    return a + b

storage = InMemoryStorage()
worker = Worker(storage, retry=RetryPolicy(jitter=False))
thread = threading.Thread(target=worker.run_forever, daemon=True)
thread.start()

storage.enqueue(Job("add", (1, 2)))   # args tuple
storage.enqueue(Job("BOOM"))           # case-insensitive lookup (if registered)

time.sleep(2.5)
worker.stop()
thread.join()
```

### Library usage (SQLite)

```python
import threading, time
from pinion import task, Job, Worker, RetryPolicy
from pinion.queue import SqliteStorage  # durable backend

@task("boom")
def fail() -> None:
    raise ValueError("kaboom")

storage = SqliteStorage("pinion.db")
worker = Worker(storage, retry=RetryPolicy(jitter=False))
t = threading.Thread(target=worker.run_forever, daemon=True)
t.start()

storage.enqueue(Job("fail"))

time.sleep(4.5)
worker.stop()
t.join()
```

## Core Concepts

- Job: encapsulates function name, args/kwargs, id, status, attempts, timestamps
- Storage: SPI with `enqueue`, `dequeue`, `mark_done`, `mark_failed`, `size`
- Task registry: mapping of case-insensitive names to callables via `@task`
- Worker: pulls jobs, executes callables, applies retry policy
- Retry policy: `max_retries`, `base_delay`, `cap`, optional `jitter`

## Extending Storage

Implement the `Storage` protocol to plug in your own backend (e.g., Redis, DB, file-based):

```python
class MyStorage:
    def enqueue(self, job: Job) -> None: ...
    def dequeue(self, timeout: float | None = None) -> Job | None: ...
    def mark_done(self, job: Job) -> None: ...
    def mark_failed(self, job: Job, exc: Exception) -> None: ...
    def size(self) -> int: ...
```

`dequeue` should block until timeout or a job is available, mark the job `RUNNING`, and increment `attempts` before returning the job.

## Design Notes

- `InMemoryStorage` uses a `Condition` for coordinating producers/consumers.
- `SqliteStorage` uses WAL mode and an atomic claim (`BEGIN IMMEDIATE` + `UPDATE`) to safely select a `PENDING` job across processes.
- `Worker` uses a `JobExecution` context manager to mark success/failure.
- Retries are scheduled by re-enqueuing the same job after a computed delay.
- Registry keys are normalized to lowercase for case-insensitive task names.

## Limitations

- In-memory storage is ephemeral; jobs are not persisted across restarts.
- SQLite backend is local to a machine; horizontal scaling requires a different backend.
- No result storage/return channel; tasks handle their own outputs.
- Minimal inspection/metrics API.

## Project Layout

- `pinion/queue.py` — core queue, worker, storages, demo tasks
- `pinion/cli.py` — simple CLI demo (`pinion`)

---

Pinion aims to be a tiny, understandable foundation you can extend with a real storage backend and operational features as needed.

