# Pinion

Pinion is a minimal, in‑memory job queue and worker for Python, built around a pluggable storage interface, a simple task registry, and a retry policy with exponential backoff. The current implementation lives in `skepticqueue/v1.py`.

## Features

- In‑memory queue with thread-safe condition variable coordination
- Pluggable `Storage` protocol (SPI) for custom backends
- Task registry via `@task` decorator (case‑insensitive names)
- Worker loop with polling and graceful stop
- Exponential backoff retries (configurable attempts and base delay)
- Basic job lifecycle tracking (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`)

## Requirements

- Python 3.10+ (uses dataclass `slots=True` and modern typing)

## Quick Start

Run the demo script:

```bash
python skepticqueue/v1.py
```

It will:
- Start a worker thread
- Enqueue a success task (`add(1, 2)`) and a failing task (`boom`)
- Show retries for the failing task and then stop

## Core Concepts

- Job: encapsulates a function name, args/kwargs, id, status, attempts, timestamps
- Storage: SPI with `enqueue`, `dequeue`, `mark_done`, `mark_failed`, `size`
- Task registry: map of function name → callable, registered via `@task`
- Worker: pulls jobs, executes task callables, applies retry policy
- Retry policy: `max_retries` and `base_delay` (exponential backoff)

## Usage

Register tasks (case‑insensitive lookup):

```python
from skepticqueue.v1 import task

@task()  # name defaults to function name
def add(a: int, b: int) -> int:
    return a + b

@task("boom")  # explicit name
def fail() -> None:
    raise ValueError("kaboom")
```

Enqueue and run a worker:

```python
from skepticqueue.v1 import InMemoryStorage, Worker, Job
import threading, time

storage = InMemoryStorage()
worker = Worker(storage)
thread = threading.Thread(target=worker.run_forever, daemon=True)
thread.start()

storage.enqueue(Job("add", (1, 2)))   # args tuple
storage.enqueue(Job("BOOM"))           # proves case-insensitive lookup

time.sleep(2.5)
worker.stop()
thread.join()
```

## Extending Storage

Implement the `Storage` protocol to plug in your own backend (e.g., Redis, database, file‑based):

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
- `Worker` uses `JobExecution` context manager to handle marking success/failure.
- Retries are scheduled by re‑enqueuing the same job after a computed delay.
- Registry keys are normalized to lowercase for case‑insensitive task names.

## Limitations

- In‑memory only: jobs are not persisted across process restarts.
- No result storage/return channel; tasks print or handle their own outputs.
- Basic visibility: failures recorded internally; no metrics/inspection API.
- Single-process focus; you can run multiple workers against one storage, but distribution/locking depends on the storage backend.

## Project Layout

- `skepticqueue/v1.py` — the Pinion implementation and demo

---

Pinion aims to be a tiny, understandable foundation that you can extend with a real storage backend and operational features as needed.
