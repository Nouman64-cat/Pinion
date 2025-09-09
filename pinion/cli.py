def main() -> None:
    import argparse
    import logging, threading, time, os, json, urllib.request, urllib.error
    from pathlib import Path
    from . import __version__
    from .queue import InMemoryStorage, Worker, RetryPolicy, Job, task

    def _parse_version(v: str) -> tuple[int, ...] | None:
        try:
            parts = []
            for p in v.split("."):
                num = "".join(ch for ch in p if ch.isdigit())
                if num == "":
                    break
                parts.append(int(num))
            return tuple(parts) if parts else None
        except Exception:
            return None

    def _maybe_check_update(no_check: bool = False) -> None:
        if no_check or os.environ.get("PINION_NO_UPDATE_CHECK"):
            return
        try:
            # simple cache under ~/.cache/pinion/update.json
            home = Path.home()
            cache_dir = home / ".cache" / "pinion"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / "update.json"
            latest: str | None = None
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    ts = float(data.get("ts", 0))
                    if (time.time() - ts) < 24 * 3600:
                        latest = data.get("latest")
                except Exception:
                    pass
            if latest is None:
                url = "https://pypi.org/pypi/pinion-queue/json"
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    info = json.loads(resp.read().decode("utf-8"))
                    latest = info.get("info", {}).get("version")
                cache_file.write_text(json.dumps({"latest": latest, "ts": time.time()}))
            cur_t = _parse_version(__version__)
            lat_t = _parse_version(latest or "")
            if cur_t and lat_t and lat_t > cur_t:
                print(
                    f"A newer pinion-queue {latest} is available. Upgrade: pip install -U pinion-queue",
                    flush=True,
                )
        except Exception:
            # best-effort: never block or crash CLI
            pass

    parser = argparse.ArgumentParser(prog="pinion", add_help=True)
    parser.add_argument(
        "-V", "--version", action="store_true", help="print version and exit"
    )
    parser.add_argument(
        "--no-update-check", action="store_true", help="disable update check"
    )
    parser.add_argument(
        "--demo", action="store_true", help="run a tiny in-memory demo and exit"
    )
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    _maybe_check_update(no_check=args.no_update_check)

    # If --demo requested, run the tiny in-memory demonstration
    if args.demo:
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
        return

    # Otherwise, print a concise CLI guide and exit
    guide = f"""
Pinion {__version__}

Quickstart (library):
  In-memory:
    from pinion import task, Job, InMemoryStorage, Worker, RetryPolicy
    @task()\ndef add(a,b): return a+b
    s=InMemoryStorage(); w=Worker(s, retry=RetryPolicy(jitter=False))
    import threading; threading.Thread(target=w.run_forever, daemon=True).start()
    s.enqueue(Job("add", (1,2)))

  Durable (SQLite):
    from pinion import task, Job, Worker, RetryPolicy, SqliteStorage
    @task()\ndef hello(name): print("hi", name)
    s=SqliteStorage("pinion.db"); w=Worker(s, retry=RetryPolicy())
    # start worker thread/process then enqueue jobs; inspect dlq via s._conn

CLI tips:
  Show version:      pinion --version
  Run tiny demo:     pinion --demo
  Disable update chk: PINION_NO_UPDATE_CHECK=1 or pinion --no-update-check

Docs: README.md • Changelog: CHANGELOG.md • PyPI: pinion-queue
"""
    print(guide.strip())
    return
