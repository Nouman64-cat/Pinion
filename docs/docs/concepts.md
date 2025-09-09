## Core Concepts

- Job: encapsulates function name, args/kwargs, id, status, attempts, timestamps.
- Tasks & Registry: `@task` decorator registers callables under case-insensitive names.
- Storage: SPI with `enqueue`, `dequeue`, `mark_done`, `mark_failed`, `size`, `heartbeat`, `reap_stale`, `dead_letter`.
- Worker: pulls jobs, executes callables, applies retry policy, optional per-task timeout, and reaps stale RUNNING jobs.
- RetryPolicy: exponential backoff with jitter and cap; controls requeue delays.
- DLQ: jobs moved to durable dead-letter storage after retries are exhausted.
- Metrics: basic counters available via `worker.metrics`.

### Lifecycle and states

`PENDING` -> `RUNNING` -> `SUCCESS` or `FAILED`.

On failure: retry while attempts ≤ `max_retries`, otherwise move to DLQ and remain `FAILED`.

### Visibility timeout and reaping (durable backends)

- Workers periodically `heartbeat` for the currently running job.
- If a job is `RUNNING` but hasn’t been heartbeated within `visibility_timeout`, another worker can re-enqueue it (`reap_stale`).

### Timeouts

`Worker(task_timeout=...)` runs each task in a helper thread and marks it failed if it doesn’t finish in time (the original thread cannot be killed; long-running tasks should be cooperative).

