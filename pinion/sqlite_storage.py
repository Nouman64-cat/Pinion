from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from .types import Job, Status


class SqliteStorage:
    def __init__(self, path: str = "pinion.db") -> None:
        self._cv = threading.Condition()  # local process wakeups
        self._lock = threading.RLock()  # serialize access to sqlite connection
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
