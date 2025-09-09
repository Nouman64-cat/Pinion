## Worker

Module: `pinion.worker`

Runs a loop to fetch jobs from a `Storage`, execute tasks, and apply retries, heartbeats, and reaping.

Constructor (selected params):

- `storage: Storage`
- `poll_timeout: float = 0.5`
- `retry: RetryPolicy | None = None`
- `visibility_timeout: float | None = 10.0`
- `heartbeat_interval: float = 1.0`
- `reap_interval: float = 2.0`
- `task_timeout: float | None = None`

Attributes:

- `metrics`: dict with `processed`, `succeeded`, `failed`, `retried`, `dead_lettered`, `reaped`.

Methods:

- `run_forever()`: start processing until `stop()` is called.
- `stop()`: signal background loops to stop.
- `join(timeout=None)`: wait for helper threads.

Timeouts:

- If `task_timeout` > 0, tasks execute in a helper thread and are marked failed if they exceed the timeout (thread isn’t forcibly killed).

Retries:

- Failures are retried while attempts ≤ `max_retries` using `RetryPolicy.compute_delay`.

