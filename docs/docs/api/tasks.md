## Tasks & Registry

Module: `pinion.registry`

```python
REGISTRY: dict[str, Callable[..., Any]]

def task(name: str | None = None):
    def deco(fn):
        REGISTRY[(name or fn.__name__).lower()] = fn
        return fn
    return deco
```

Usage:

```python
from pinion import task

@task()
def add(a, b):
    return a + b

@task("boom")
def fail():
    raise ValueError("kaboom")
```

Notes:

- Names are case-insensitive; keys are normalized to lowercase.
- Import modules containing `@task` functions before enqueuing or running a worker so they are registered.

