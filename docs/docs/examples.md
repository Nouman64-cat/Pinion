## Examples

### Retry and DLQ (SQLite)

```python
from pinion import task, Job, Worker, RetryPolicy, SqliteStorage
import threading, time

@task("boom")
def _boom():
    raise RuntimeError("always fails")

s = SqliteStorage("pinion.db")
w = Worker(s, retry=RetryPolicy(max_retries=1, jitter=False, base_delay=0.05), poll_timeout=0.02)
t = threading.Thread(target=w.run_forever, daemon=True); t.start()
s.enqueue(Job("BOOM"))
time.sleep(0.4)
w.stop(); t.join()
```

Check DLQ entries:

```sql
SELECT id, func_name, attempts, error FROM dlq ORDER BY failed_at DESC;
```

### Task timeout

```python
from pinion import task, Job, Worker, RetryPolicy, SqliteStorage
import threading, time

@task("slow")
def _slow():
    time.sleep(0.3)

s = SqliteStorage("pinion.db")
w = Worker(s, retry=RetryPolicy(max_retries=0, jitter=False), poll_timeout=0.02, task_timeout=0.05)
t = threading.Thread(target=w.run_forever, daemon=True); t.start()
s.enqueue(Job("SLOW"))
time.sleep(0.3)
w.stop(); t.join()
```

Job ends `FAILED` with a `TimeoutError` recorded in `jobs.error`.

### Reaping stale RUNNING jobs

Configure two workers: one with infrequent heartbeats, one with default settings. The reaper moves stale jobs back to `PENDING` so another worker can pick them up. See `tests/test_sqlite.py::test_reaper_requeues_stale_running` for a concrete pattern.

