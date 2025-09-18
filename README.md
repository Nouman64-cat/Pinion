# Pinion

Pinion is a tiny, pluggable job queue and worker for Python. It provides a simple `@task` registry, an in-memory queue for quick starts, and a durable SQLite backend for cross-process work, plus a retry policy with exponential backoff.

## Features

- In-memory queue with thread-safe `Condition` coordination
- Durable SQLite storage with atomic job claim (WAL) across processes
- Pluggable `Storage` protocol (SPI) for custom backends
- Task registry via `@task` decorator (case-insensitive names)
- Worker loop with polling, retries, timeouts, and graceful stop/join
- Exponential backoff retries with optional jitter and cap
- Dead-letter queue (DLQ) after exhausted retries
- Basic worker metrics (processed/succeeded/failed/retried/dead_lettered/reaped)
- Job lifecycle tracking: `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`

## Requirements

- Python 3.12+

## Installation

- From source (local dev): `pip install -e .`
- CLI entry point installs as `pinion`

## Quick Start

### CLI

- `pinion` prints a concise quickstart, admin command cheatsheet, and exits.
- `pinion --demo` runs a tiny in-memory demo (adds 1+2).
- SQLite admin commands: `status`, `running`, `pending`, `dlq-list`, `dlq-replay`, `enqueue`, `worker`.

Examples:

```bash
# Show queue summary for a DB
pinion status --db pinion.db

# Run a worker for 5s and import your task module for registration
pinion worker --db pinion.db --max-retries 2 --task-timeout 5 \
  --import your_project.tasks --run-seconds 5

# Enqueue a job by name with JSON args/kwargs
pinion enqueue add --db pinion.db --args '[1,2]'
```

## Documentation

- Local preview with MkDocs:
  - `pip install -e .[docs]` (or install `mkdocs` and `mkdocs-material` manually)
  - From repo root: `mkdocs serve --config-file docs/mkdocs-material.yml`
  - Or `cd docs` then: `mkdocs serve -f mkdocs-material.yml`
  - Open the URL printed by MkDocs (e.g., `http://127.0.0.1:8000/`).

## Running Tests

- Install extras that include the testing tools: `pip install -e ".[tests]"` (or use `.[dev]` for docs + tests).
- From the project root, run the suite with `pytest` (append `-q` for quiet output, `--cov` for coverage).
- Tests expect a local SQLite database file for backend checks and create/delete temporary files automatically.

## Tested Guarantees

The automated test suite captures the core behaviours you rely on in production:

- Jobs begin life as `Status.PENDING` with `attempts == 0`, and in-memory queues report their length via `InMemoryStorage.size()`.
- Claiming a job through either storage backend moves it to `RUNNING`, increments `attempts`, and `mark_done` persists a `SUCCESS` state (SQLite verified at the schema level).
- Stale or failed work is recovered: `reap_stale` requeues timed-out jobs and both storages funnel exhausted retries into a dead-letter queue.
- Task registration is case-insensitive, so `@task()` without arguments registers handlers by their lowercase function name.
- `RetryPolicy.compute_delay()` delivers deterministic exponential backoff when jitter is disabled and uniform jitter when enabled.
- Worker metrics track successes, retries, dead-letter events, and respect optional per-task timeouts while continuing to poll for work.

### Library usage (in-memory)

```python
import threading, time
from pinion import task, Job, InMemoryStorage, Worker, RetryPolicy

@task()
def add(a: int, b: int) -> int:
    return a + b

storage = InMemoryStorage()
worker = Worker(storage, retry=RetryPolicy(jitter=False), task_timeout=2.0)
thread = threading.Thread(target=worker.run_forever, daemon=True)
thread.start()

storage.enqueue(Job("add", (1, 2)))   # args tuple
storage.enqueue(Job("BOOM"))           # case-insensitive lookup (if registered)

time.sleep(2.5)
worker.stop()
thread.join()
# Optional: access basic metrics
print(worker.metrics)
```

### Library usage (SQLite)

```python
import threading, time
from pinion import task, Job, Worker, RetryPolicy, SqliteStorage  # durable backend

@task("boom")
def fail() -> None:
    raise ValueError("kaboom")

storage = SqliteStorage("pinion.db")
worker = Worker(storage, retry=RetryPolicy(jitter=False), task_timeout=2.0)
t = threading.Thread(target=worker.run_forever, daemon=True)
t.start()

storage.enqueue(Job("fail"))

time.sleep(4.5)
worker.stop()
t.join()

# Inspect DLQ (SQLite backend) for permanently failed jobs
# rows: (id, func_name, args_json, kwargs_json, attempts, error, failed_at)
print(storage._conn.execute("SELECT * FROM dlq").fetchall())
```

## Core Concepts

- Job: encapsulates function name, args/kwargs, id, status, attempts, timestamps
- Storage: SPI with `enqueue`, `dequeue`, `mark_done`, `mark_failed`, `size`, `heartbeat`, `reap_stale`, `dead_letter`
- Task registry: mapping of case-insensitive names to callables via `@task`
- Worker: pulls jobs, executes callables, applies retry policy and optional per-task timeouts
- Retry policy: `max_retries`, `base_delay`, `cap`, optional `jitter`
- DLQ: jobs moved to durable dead-letter storage after retries are exhausted
- Metrics: basic counters available via `worker.metrics`

## Extending Storage

Implement the `Storage` protocol to plug in your own backend (e.g., Redis, DB, file-based):

```python
class MyStorage:
    def enqueue(self, job: Job) -> None: ...
    def dequeue(self, timeout: float | None = None) -> Job | None: ...
    def mark_done(self, job: Job) -> None: ...
    def mark_failed(self, job: Job, exc: Exception) -> None: ...
    def size(self) -> int: ...
    def heartbeat(self, job: Job) -> None: ...
    def reap_stale(self, visibility_timeout: float) -> int: ...
    def dead_letter(self, job: Job, exc: Exception) -> None: ...
```

`dequeue` should block until timeout or a job is available, mark the job `RUNNING`, and increment `attempts` before returning the job.

## Design Notes

- `InMemoryStorage` uses a `Condition` for coordinating producers/consumers.
- `SqliteStorage` uses WAL mode and an atomic claim (`BEGIN IMMEDIATE` + `UPDATE`) to safely select a `PENDING` job across processes. Access is serialized with a lock.
- `Worker` uses a `JobExecution` context manager to mark success/failure and provides a thread-based per-task timeout option.
- Retries are scheduled by re-enqueuing the same job after a computed delay.
- Registry keys are normalized to lowercase for case-insensitive task names.
- DLQ persists final failures (SQLite backend has a `dlq` table).

## Limitations

- In-memory storage is ephemeral; jobs are not persisted across restarts.
- SQLite backend is local to a machine; horizontal scaling requires a different backend.
- Thread-based timeouts cannot kill Python threads; long-running tasks should be cooperative or run in separate processes.
- No result storage/return channel; tasks handle their own outputs.
- Minimal inspection/metrics API.

## Breaking Changes (since 0.1.x)

- Storage SPI: added `dead_letter(job, exc)`; custom backends must implement it.

## Release and Publishing

Pinion targets Python 3.12+ and is published as `pinion-queue`.

Suggested versioning for this release: bump to `0.2.0`.

1) Update version

- Edit `pyproject.toml`: set `version = "0.2.0"`.
- Edit `pinion/__init__.py`: set `__version__ = "0.2.0"`.

2) Build distributions

```bash
python -m pip install --upgrade pip build twine
python -m build
twine check dist/*
```

3) Publish to PyPI

```bash
# Set PYPI token in environment (from your PyPI account)
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-***your-token***"

twine upload dist/*
```

4) Tag the release

```bash
git tag v0.2.0
git push --tags
```

If `pinion-queue` is not available on PyPI, choose an alternative name or organization namespace.

## Project Layout

- `pinion/queue.py` — core queue, worker, storages, demo tasks
- `pinion/cli.py` — simple CLI demo (`pinion`)

## Upgrading

- pip: `pip install -U pinion-queue`
- pipx: `pipx upgrade pinion-queue`
- Poetry: `poetry update pinion-queue`

The CLI performs a lightweight update check (with a short timeout) and prints a hint if a newer version is available. Disable via `PINION_NO_UPDATE_CHECK=1` or `pinion --no-update-check`.

See the Changelog for release notes: `CHANGELOG.md`.

---

Pinion aims to be a tiny, understandable foundation you can extend with a real storage backend and operational features as needed.
