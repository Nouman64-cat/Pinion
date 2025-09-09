from __future__ import annotations

from typing import Any
import logging
import threading
import time

from .errors import TaskNotFound
from .registry import REGISTRY
from .retry import RetryPolicy
from .storage import Storage
from .types import Job, Status


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

    def __enter__(self) -> Any:
        fn = REGISTRY.get(self.job.func_name.lower())
        if not fn:
            raise TaskNotFound(
                f"no task registered: {self.job.func_name!r} (known: {list(REGISTRY)})"
            )
        return fn


def _requeue_later(storage: Storage, job: Job, delay: float) -> None:
    def _t():
        time.sleep(delay)
        job.status = Status.PENDING
        storage.enqueue(job)

    threading.Thread(target=_t, daemon=True).start()


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

