## SQLite Backend

Durable storage suitable for multiple processes on the same machine.

### Setup

```python
from pinion import SqliteStorage
s = SqliteStorage("pinion.db")
```

Uses WAL mode with an atomic claim pattern:

- `BEGIN IMMEDIATE` then `UPDATE ... WHERE status='PENDING'` to claim a single job
- Sets `RUNNING`, increments `attempts`, and records `heartbeat_at`

### Worker example

```python
import threading, time
from pinion import task, Job, Worker, RetryPolicy, SqliteStorage

@task("boom")
def fail():
    raise RuntimeError("always fails")

s = SqliteStorage("pinion.db")
w = Worker(s, retry=RetryPolicy(max_retries=1, jitter=False, base_delay=0.1))
t = threading.Thread(target=w.run_forever, daemon=True)
t.start()

s.enqueue(Job("BOOM"))
time.sleep(0.6)
w.stop(); t.join()
```

### Admin with CLI

```bash
pinion status --db pinion.db
pinion dlq-list --db pinion.db --limit 10
pinion dlq-replay --db pinion.db --limit 5
```

### Visibility and reaping

Configure `visibility_timeout`, `heartbeat_interval`, and `reap_interval` on the `Worker` to re-enqueue stale `RUNNING` jobs that stop heartbeating.

