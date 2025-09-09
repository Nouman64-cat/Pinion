## SqliteStorage

Module: `pinion.sqlite_storage`

Durable backend using SQLite with WAL and atomic claims for cross-process safety.

Schema:

- `jobs(id, func_name, args, kwargs, status, attempts, created_at, error, heartbeat_at)`
- `dlq(id, func_name, args, kwargs, attempts, error, failed_at)`

Highlights:

- WAL mode and `busy_timeout` are enabled.
- Claiming a job uses `BEGIN IMMEDIATE` and `UPDATE ... WHERE status='PENDING'`.
- Heartbeats record `heartbeat_at`; reaping moves stale `RUNNING` jobs back to `PENDING`.
- Final failures are inserted into `dlq`.

Use this backend when you need persistence on a single machine or simple multi-process workers.

