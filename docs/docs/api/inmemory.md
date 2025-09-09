## InMemoryStorage

Module: `pinion.inmemory`

Thread-safe, in-process queue built on `collections.deque` and a `Condition`.

Key behaviors:

- `enqueue`: append and notify waiting consumers.
- `dequeue`: block with optional timeout; marks job `RUNNING`, increments `attempts`.
- `mark_done` / `mark_failed`: finalize status and clear heartbeat/running maps.
- `heartbeat`: best-effort liveness update for current job.
- `reap_stale`: re-enqueue jobs whose heartbeat is older than the visibility window.
- `dead_letter`: append to an in-memory DLQ list for inspection in tests.

Best for local development and unit tests; not durable.

