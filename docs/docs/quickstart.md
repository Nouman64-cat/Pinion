## Quickstart

Install for local development:

```bash
pip install -e .
```

CLI entry points: `pinion` and `pinion-queue`.

### Run the tests

```bash
pip install -e ".[tests]"
pytest -q
```

Use the `.[dev]` extra if you also want the MkDocs tooling installed alongside the test suite.

!!! tip "Pretty docs locally"
    To use the Material theme variant, install:

    ```bash
    pip install mkdocs-material
    ```
    Then serve from the `docs` folder:

    ```bash
    # default (Read the Docs theme)
    mkdocs -f docs/mkdocs.yml serve

    # Material (after install)
    mkdocs -f docs/mkdocs-material.yml serve
    ```

### Run the demo

```bash
pinion --demo
```

Shows a greeting and a transient failure that retries, then prints metrics.

### In-memory usage

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

storage.enqueue(Job("add", (1, 2)))

time.sleep(1.0)
worker.stop(); thread.join()
print(worker.metrics)
```

### Durable usage (SQLite)

```python
import threading, time
from pinion import task, Job, Worker, RetryPolicy, SqliteStorage

@task("boom")
def fail() -> None:
    raise ValueError("kaboom")

storage = SqliteStorage("pinion.db")
worker = Worker(storage, retry=RetryPolicy(jitter=False), task_timeout=2.0)
t = threading.Thread(target=worker.run_forever, daemon=True)
t.start()

storage.enqueue(Job("fail"))

time.sleep(3.0)
worker.stop(); t.join()

# Inspect DLQ entries via storage connection (optional)
print(storage._conn.execute("SELECT id, error FROM dlq").fetchall())
```

### CLI admin (SQLite)

```bash
# Show queue summary for a DB
pinion status --db pinion.db

# Run a worker for 5s and import your task module for registration
pinion worker --db pinion.db --max-retries 2 --task-timeout 5 \
  --import your_project.tasks --run-seconds 5

# Enqueue by name with JSON args/kwargs
pinion enqueue add --db pinion.db --args '[1,2]'
```
