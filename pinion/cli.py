def main() -> None:
    import logging, threading, time
    from .queue import InMemoryStorage, Worker, RetryPolicy, Job, task

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    @task()  # so users see it do something
    def add(a: int, b: int) -> int:
        out = a + b
        print(f"add -> {out}")
        return out

    s = InMemoryStorage()
    w = Worker(s, retry=RetryPolicy(jitter=False))
    t = threading.Thread(target=w.run_forever, daemon=True)
    t.start()
    s.enqueue(Job("add", (1, 2)))

    try:
        time.sleep(2.0)
    finally:
        w.stop()
        t.join()
