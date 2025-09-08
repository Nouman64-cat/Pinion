from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable, Callable
from collections import deque
import threading, time, uuid
import logging, random
import sqlite3, json


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
    # Heartbeat and reaping
    def heartbeat(self, job: Job) -> None: ...
    def reap_stale(self, visibility_timeout: float) -> int: ...
    # Dead letter queue
    def dead_letter(self, job: Job, exc: Exception) -> None: ...


# ---------- In-memory storage ----------
class InMemoryStorage:
    def __init__(self) -> None:
        self._q: deque[Job] = deque()
        self._cv = threading.Condition()
        self._failures: dict[str, str] = {}
        self._done: set[str] = set()
        self._heartbeats: dict[str, float] = {}
        self._running: dict[str, Job] = {}
        self._dlq: list[tuple[Job, str, float]] = []

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
            self._heartbeats[job.id] = time.time()
            self._running[job.id] = job
            return job

    def mark_done(self, job: Job) -> None:
        job.status = Status.SUCCESS
        with self._cv:
            self._done.add(job.id)
            self._heartbeats.pop(job.id, None)
            self._running.pop(job.id, None)

    def mark_failed(self, job: Job, exc: Exception) -> None:
        job.status = Status.FAILED
        with self._cv:
            self._failures[job.id] = repr(exc)
            self._heartbeats.pop(job.id, None)
            self._running.pop(job.id, None)

    def size(self) -> int:
        with self._cv:
            return len(self._q)

    def heartbeat(self, job: Job) -> None:
        with self._cv:
            if job.status is Status.RUNNING:
                self._heartbeats[job.id] = time.time()

    def reap_stale(self, visibility_timeout: float) -> int:
        now = time.time()
        reaped = 0
        with self._cv:
            stale_ids = [
                jid
                for jid, hb in list(self._heartbeats.items())
                if hb + visibility_timeout < now
            ]
            for jid in stale_ids:
                self._heartbeats.pop(jid, None)
                job = self._running.pop(jid, None)
                if job is not None and job.status is Status.RUNNING:
                    job.status = Status.PENDING
                    self._q.append(job)
                    reaped += 1
            if reaped:
                self._cv.notify_all()
        return reaped

    def dead_letter(self, job: Job, exc: Exception) -> None:
        with self._cv:
            self._dlq.append((job, repr(exc), time.time()))
            self._cv.notify_all()


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

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.storage.mark_done(self.job)
        else:
            self.storage.mark_failed(self.job, exc)
        return False  # don't suppress exceptions

    def __enter__(self) -> Callable[..., Any]:
        fn = REGISTRY.get(self.job.func_name.lower())
        if not fn:
            raise TaskNotFound(
                f"no task registered: {self.job.func_name!r} (known: {list(REGISTRY)})"
            )
        return fn


# ---------- Retry policy ----------
@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5  # seconds
    cap: float = 10.0
    jitter: bool = True

    def compute_delay(self, attempt: int) -> float:
        raw = min(self.cap, self.base_delay * (2 ** (attempt - 1)))
        return random.uniform(0, raw) if self.jitter else raw


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
        logger: logging.Logger | None = None,
        visibility_timeout: float | None = 10.0,
        heartbeat_interval: float = 1.0,
        reap_interval: float = 2.0,
        task_timeout: float | None = None,
    ):
        self.storage = storage
        self.poll_timeout = poll_timeout
        self.retry = retry or RetryPolicy()
        self.stop_event = threading.Event()
        self.log = logger or logging.getLogger("pinion.worker")
        self.visibility_timeout = visibility_timeout
        self.heartbeat_interval = heartbeat_interval
        self.reap_interval = reap_interval
        self._current_job: Job | None = None
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._reaper_thread = threading.Thread(target=self._reaper_loop, daemon=True)
        self.task_timeout = task_timeout
        self.metrics = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "retried": 0,
            "dead_lettered": 0,
            "reaped": 0,
        }

    def stop(self) -> None:
        self.stop_event.set()
        # Give background threads a chance to exit
        # They are daemons, so joining is optional; keep it light

    def run_forever(self) -> None:
        # start background helpers on first run
        if not self._hb_thread.is_alive():
            self._hb_thread.start()
        if self.visibility_timeout is not None and not self._reaper_thread.is_alive():
            self._reaper_thread.start()
        while not self.stop_event.is_set():
            job = self.storage.dequeue(timeout=self.poll_timeout)
            if job is None:
                continue
            self.log.info(
                "job.start id=%s name=%s attempt=%d",
                job.id,
                job.func_name,
                job.attempts,
            )
            try:
                self._current_job = job
                # Resolve the task early so TaskNotFound gets marked as failed
                fn = REGISTRY.get(job.func_name.lower())
                if not fn:
                    raise TaskNotFound(
                        f"no task registered: {job.func_name!r} (known: {list(REGISTRY)})"
                    )
                # Execute with optional timeout
                if self.task_timeout is None or self.task_timeout <= 0:
                    with JobExecution(self.storage, job) as _:
                        fn(*job.args, **job.kwargs)
                else:
                    # Run in a helper thread and wait up to task_timeout
                    result: dict[str, Any] = {}

                    def _call():
                        try:
                            fn(*job.args, **job.kwargs)
                            result["ok"] = True
                        except Exception as ex:  # propagate later
                            result["exc"] = ex

                    t = threading.Thread(target=_call)
                    t.daemon = True
                    t.start()
                    t.join(self.task_timeout)
                    if t.is_alive():
                        # Timed out; mark failed and proceed (cannot kill the thread)
                        raise TimeoutError(f"task timed out after {self.task_timeout}s")
                    # If thread finished, check for exception
                    if "exc" in result:
                        raise result["exc"]
                    with JobExecution(self.storage, job):
                        # Success already happened, just finalize
                        pass
                self.metrics["processed"] += 1
                self.metrics["succeeded"] += 1
            except Exception as e:
                self.log.exception(
                    "job.fail id=%s name=%s attempt=%d err=%r",
                    job.id,
                    job.func_name,
                    job.attempts,
                    e,
                )
                # If failure happened before entering context (e.g., missing task),
                # it hasn't been marked yet — record failure now.
                if job.status is not Status.FAILED and job.status is not Status.SUCCESS:
                    try:
                        self.storage.mark_failed(job, e)
                    except Exception:
                        pass
                # attempts incremented in dequeue(); attempt 1 just ran
                if job.attempts <= self.retry.max_retries:
                    delay = self.retry.compute_delay(job.attempts)
                    self.log.info(
                        "job.retry id=%s delay=%.3f next_attempt=%d",
                        job.id,
                        delay,
                        job.attempts + 1,
                    )
                    _requeue_later(self.storage, job, delay)
                    self.metrics["failed"] += 1
                    self.metrics["retried"] += 1
                else:
                    self.log.error(
                        "job.giveup id=%s name=%s attempt=%d",
                        job.id,
                        job.func_name,
                        job.attempts,
                    )
                    try:
                        self.storage.dead_letter(job, e)
                        self.metrics["dead_lettered"] += 1
                    except Exception:
                        pass
            finally:
                self._current_job = None

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            job = self._current_job
            if job is not None:
                try:
                    self.storage.heartbeat(job)
                except Exception:
                    # best-effort heartbeat
                    pass
            self.stop_event.wait(self.heartbeat_interval)

    def _reaper_loop(self) -> None:
        if self.visibility_timeout is None:
            return
        while not self.stop_event.is_set():
            try:
                count = self.storage.reap_stale(self.visibility_timeout)
                if count:
                    self.log.info("reaper.requeued count=%d", count)
                    self.metrics["reaped"] += int(count)
            except Exception:
                # best-effort reaping
                pass
            self.stop_event.wait(self.reap_interval)

    def join(self, timeout: float | None = None) -> None:
        # Give helper threads a chance to exit
        self._hb_thread.join(timeout=timeout)
        if self.visibility_timeout is not None:
            self._reaper_thread.join(timeout=timeout)


class PinionError(Exception):
    pass


class TaskNotFound(PinionError):
    pass


class TaskExecutionError(PinionError):
    pass


class SqliteStorage:
    def __init__(self, path: str = "pinion.db") -> None:
        self._cv = threading.Condition()  # local process wakeups
        self._lock = threading.RLock()    # serialize access to sqlite connection
        self._conn = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False
        )
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA busy_timeout=3000;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id         TEXT PRIMARY KEY,
                    func_name  TEXT NOT NULL,
                    args       TEXT NOT NULL,   -- json
                    kwargs     TEXT NOT NULL,   -- json
                    status     TEXT NOT NULL,   -- PENDING/RUNNING/SUCCESS/FAILED
                    attempts   INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    error      TEXT,
                    heartbeat_at REAL
                );
            """
            )
            # Best-effort schema upgrade for older DBs without heartbeat_at
            try:
                self._conn.execute("ALTER TABLE jobs ADD COLUMN heartbeat_at REAL;")
            except sqlite3.OperationalError:
                pass
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_hb ON jobs(status, heartbeat_at);"
            )
            # Dead letter table
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dlq (
                    id           TEXT PRIMARY KEY,
                    func_name    TEXT NOT NULL,
                    args         TEXT NOT NULL,
                    kwargs       TEXT NOT NULL,
                    attempts     INTEGER NOT NULL,
                    error        TEXT NOT NULL,
                    failed_at    REAL NOT NULL
                );
                """
            )

    # --- helpers ---
    @staticmethod
    def _row_to_job(row: tuple[Any, ...]) -> Job:
        id, func_name, args, kwargs, status, attempts, created_at, _ = row
        return Job(
            func_name=func_name,
            args=tuple(json.loads(args)),
            kwargs=json.loads(kwargs),
            id=id,
            status=Status[status],
            attempts=attempts,
            created_at=created_at,
        )

    # --- API ---
    def enqueue(self, job: Job) -> None:
        with self._lock:
            with self._cv:
                self._conn.execute(
                    "INSERT OR REPLACE INTO jobs (id, func_name, args, kwargs, status, attempts, created_at, error, heartbeat_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                    (
                        job.id,
                        job.func_name,
                        json.dumps(list(job.args)),
                        json.dumps(job.kwargs),
                        job.status.name,
                        job.attempts,
                        job.created_at,
                    ),
                )
                self._cv.notify_all()

    def dequeue(self, timeout: float | None = None) -> Job | None:
        deadline = None if timeout is None else time.time() + timeout
        while True:
            # try to claim a pending job atomically
            try:
                with self._lock:
                    cur = self._conn.cursor()
                    cur.execute("BEGIN IMMEDIATE;")  # take write lock for atomic claim
                    row = cur.execute(
                        "SELECT id FROM jobs WHERE status='PENDING' ORDER BY created_at LIMIT 1;"
                    ).fetchone()
                    if row is None:
                        self._conn.execute("COMMIT;")
                    else:
                        job_id = row[0]
                        updated = cur.execute(
                            "UPDATE jobs SET status='RUNNING', attempts=attempts+1, heartbeat_at=? "
                            "WHERE id=? AND status='PENDING';",
                            (time.time(), job_id),
                        ).rowcount
                        if updated == 1:
                            job_row = cur.execute(
                                "SELECT id, func_name, args, kwargs, status, attempts, created_at, error "
                                "FROM jobs WHERE id=?;",
                                (job_id,),
                            ).fetchone()
                            self._conn.execute("COMMIT;")
                            return self._row_to_job(job_row)
                        else:
                            self._conn.execute("ROLLBACK;")
                            continue
            except sqlite3.OperationalError:
                # busy; brief backoff
                time.sleep(0.01)

            # none available: optionally block
            if timeout is None:
                with self._cv:
                    self._cv.wait(0.25)
            else:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                with self._cv:
                    self._cv.wait(min(0.25, remaining))

    def mark_done(self, job: Job) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status='SUCCESS', error=NULL WHERE id=?;",
                (job.id,),
            )
            with self._cv:
                self._cv.notify_all()

    def mark_failed(self, job: Job, exc: Exception) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status='FAILED', error=? WHERE id=?;",
                (repr(exc), job.id),
            )
            with self._cv:
                self._cv.notify_all()

    def size(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status='PENDING';"
            ).fetchone()
            return int(row[0])

    def heartbeat(self, job: Job) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET heartbeat_at=? WHERE id=? AND status='RUNNING';",
                (time.time(), job.id),
            )

    def reap_stale(self, visibility_timeout: float) -> int:
        cutoff = time.time() - visibility_timeout
        with self._lock:
            with self._cv:
                cur = self._conn.cursor()
                cur.execute("BEGIN IMMEDIATE;")
                cur.execute(
                    "UPDATE jobs SET status='PENDING' WHERE status='RUNNING' AND (heartbeat_at IS NULL OR heartbeat_at < ?);",
                    (cutoff,),
                )
                count = cur.rowcount
                self._conn.execute("COMMIT;")
                if count:
                    self._cv.notify_all()
                return int(count)

    def dead_letter(self, job: Job, exc: Exception) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO dlq (id, func_name, args, kwargs, attempts, error, failed_at) VALUES (?, ?, ?, ?, ?, ?, ?);",
                (
                    job.id,
                    job.func_name,
                    json.dumps(list(job.args)),
                    json.dumps(job.kwargs),
                    job.attempts,
                    repr(exc),
                    time.time(),
                ),
            )



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
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    s = SqliteStorage("pinion.db")
    w = Worker(s, retry=RetryPolicy(jitter=False))
    t = threading.Thread(target=w.run_forever, daemon=True)
    t.start()

    s.enqueue(Job("add", (1, 2)))
    s.enqueue(Job("BOOM"))  # proves case-insensitive lookup

    time.sleep(4.5)  # give retries a moment to show
    w.stop()
    t.join()
    print("done; q size:", s.size())
