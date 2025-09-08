def main() -> None:
    import argparse
    import logging, threading, time
    from . import __version__
    from .queue import InMemoryStorage, Worker, RetryPolicy, Job, task

    parser = argparse.ArgumentParser(prog="pinion", add_help=True)
    parser.add_argument(
        "-V", "--version", action="store_true", help="print version and exit"
    )
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

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
