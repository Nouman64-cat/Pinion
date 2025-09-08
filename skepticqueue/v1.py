from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable, Callable
from collections import deque
import threading, time, uuid


# ---------- Domain ----------
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


# ---------- Storage SPI ----------
@runtime_checkable
class Storage(Protocol):
    def enqueue(self, job: Job) -> None: ...
    def dequeue(self, timeout: float | None = None) -> Job | None: ...
    def mark_done(self, job: Job) -> None: ...
    def mark_failed(self, job: Job, exc: Exception) -> None: ...
    def size(self) -> int: ...


# ---------- In-memory storage ----------
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


# ---------- Task registry (case-insensitive) ----------
REGISTRY: dict[str, Callable[..., Any]] = {}


def task(name: str | None = None):
    def deco(fn: Callable[..., Any]):
        REGISTRY[(name or fn.__name__).lower()] = fn
        return fn

    return deco


# ---------- Execution context ----------
class JobExecution:
    def __init__(self, storage: Storage, job: Job):
        self.storage = storage
        self.job = job

    def __enter__(self) -> Callable[..., Any]:
        fn = REGISTRY.get(self.job.func_name.lower())
        if not fn:
            raise KeyError(
                f"no task registered: {self.job.func_name!r} (known: {list(REGISTRY)})"
            )
        return fn

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.storage.mark_done(self.job)
        else:
            self.storage.mark_failed(self.job, exc)
        return False  # don't suppress exceptions


# ---------- Retry policy ----------
@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5  # seconds


def _requeue_later(storage: Storage, job: Job, delay: float) -> None:
    def _t():
        time.sleep(delay)
        job.status = Status.PENDING
        storage.enqueue(job)

    threading.Thread(target=_t, daemon=True).start()


# ---------- Worker ----------
class Worker:
    def __init__(
        self,
        storage: Storage,
        poll_timeout: float = 0.5,
        retry: RetryPolicy | None = None,
    ):
        self.storage = storage
        self.poll_timeout = poll_timeout
        self.retry = retry or RetryPolicy()
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            job = self.storage.dequeue(timeout=self.poll_timeout)
            if job is None:
                continue
            try:
                with JobExecution(self.storage, job) as fn:
                    fn(*job.args, **job.kwargs)
            except Exception as e:
                print(f"[worker] job {job.id} failed: {e!r}")
                # attempts incremented in dequeue(); attempt 1 just ran
                if job.attempts <= self.retry.max_retries:
                    delay = self.retry.base_delay * (2 ** (job.attempts - 1))
                    print(
                        f"[worker] retrying {job.id} in {delay}s (attempt {job.attempts}/{self.retry.max_retries})"
                    )
                    _requeue_later(self.storage, job, delay)


# ---------- Demo tasks ----------
@task()
def add(a: int, b: int) -> int:
    out = a + b
    print(f"add -> {out}")
    return out


@task("boom")
def fail() -> None:
    raise ValueError("kaboom")


if __name__ == "__main__":
    s = InMemoryStorage()
    w = Worker(s)
    t = threading.Thread(target=w.run_forever, daemon=True)
    t.start()

    s.enqueue(Job("add", (1, 2)))
    s.enqueue(Job("BOOM"))  # proves case-insensitive lookup

    time.sleep(2.2)  # give retries a moment to show
    w.stop()
    t.join()
    print("done; q size:", s.size())
