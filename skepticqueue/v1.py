from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable
from collections import deque
import threading, time, uuid


class Status(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()


@dataclass(slots=True)
class Job:
    func_name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: Status = Status.PENDING
    attempts: int = 0
    created_at: float = field(default_factory=time.time)


@runtime_checkable
class Storage(Protocol):
    def enqueue(self, job: Job) -> None: ...
    def dequeue(self, timeout: float | None = None) -> Job | None: ...
    def mark_done(self, job: Job) -> None: ...
    def mark_failed(self, job: Job, exc: Exception) -> None: ...
    def size(self) -> int: ...


class InMemoryStorage:
    def __init__(self) -> None:
        self._q: deque[Job] = deque()
        self._cv = threading.Condition()
        self._failures: dict[str, str] = {}
        self._done: set[str] = set()

    def enqueue(self, job: Job) -> None:
        with self._cv:
            self._q.append(job)
            self._cv.notify()

    def dequeue(self, timeout: float | None = None) -> Job | None:
        end = None if timeout is None else time.time() + timeout
        with self._cv:
            while not self._q:
                if timeout is None:
                    self._cv.wait()
                else:
                    remaining = end - time.time()
                    if remaining <= 0:
                        return None
                    self._cv.wait(remaining)
            job = self._q.popleft()
            job.status = Status.RUNNING
            job.attempts += 1
            return job

    def mark_done(self, job: Job) -> None:
        job.status = Status.SUCCESS
        with self._cv:
            self._done.add(job.id)

    def mark_failed(self, job: Job, exc: Exception) -> None:
        job.status = Status.FAILED
        with self._cv:
            self._failures[job.id] = repr(exc)

    def size(self) -> int:
        with self._cv:
            return len(self._q)


if __name__ == "__main__":
    s = InMemoryStorage()
    s.enqueue(Job("add", (1, 2)))
    j = s.dequeue(timeout=0.1)
    assert j and j.func_name == "add"
    try:
        1 / 0
    except Exception as e:
        s.mark_failed(j, e)
    print("smoke test ok")
