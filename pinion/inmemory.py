from __future__ import annotations

from collections import deque
import threading
import time
from typing import Any

from .types import Job, Status
from .storage import Storage


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

