from __future__ import annotations

# Facade module to preserve original public API while delegating
# to smaller, focused modules for maintainability.

from .types import Job, Status
from .storage import Storage
from .inmemory import InMemoryStorage
from .worker import Worker
from .retry import RetryPolicy
from .registry import task
from .sqlite_storage import SqliteStorage
from .errors import PinionError, TaskNotFound, TaskExecutionError

# ---------- Demo tasks (kept for backward-compat behavior) ----------
@task()
def add(a: int, b: int) -> int:
    out = a + b
    print(f"add -> {out}")
    return out


@task("boom")
def fail() -> None:
    raise ValueError("kaboom")

