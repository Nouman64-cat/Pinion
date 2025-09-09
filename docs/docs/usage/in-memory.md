## In-Memory Queue

Best for quick starts and tests. Jobs are kept in process memory and lost on restart.

```python
import threading, time
from pinion import task, Job, InMemoryStorage, Worker, RetryPolicy

@task()
def add(a: int, b: int) -> int:
    return a + b

s = InMemoryStorage()
w = Worker(s, retry=RetryPolicy(jitter=False), task_timeout=1.0)
t = threading.Thread(target=w.run_forever, daemon=True)
t.start()

s.enqueue(Job("add", (1, 2)))
time.sleep(0.5)
w.stop(); t.join()
print(w.metrics)
```

Notes:

- Single-process only; thread-safe producer/consumer via a `Condition`.
- `size()` returns pending job count.
- DLQ entries are stored in-process for inspection during tests.

