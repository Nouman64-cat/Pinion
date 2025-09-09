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
    # Admin subcommands (SQLite only)
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("status", help="show queue and DLQ summary (SQLite)")
    p.add_argument("--db", default="pinion.db")
    p = sub.add_parser("running", help="list RUNNING jobs (SQLite)")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("pending", help="list PENDING jobs (SQLite)")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("dlq-list", help="list DLQ entries (SQLite)")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("dlq-replay", help="re-enqueue items from DLQ (SQLite)")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("enqueue", help="enqueue a task by name (SQLite)")
    p.add_argument("task", help="task name")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--args", help="JSON list of positional args")
    p.add_argument("--kwargs", help="JSON dict of keyword args")
    p = sub.add_parser("worker", help="run a worker for a SQLite DB")
    p.add_argument("--db", default="pinion.db")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--base-delay", type=float, default=0.5)
    p.add_argument("--no-jitter", action="store_true")
    p.add_argument("--task-timeout", type=float, default=0.0)
    p.add_argument("--visibility-timeout", type=float, default=10.0)
    p.add_argument("--run-seconds", type=float, default=0.0)
    p.add_argument(
        "--import",
        dest="imports",
        action="append",
        help="Python module(s) to import for task registration (repeatable)",
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

    # SQLite admin subcommands
    # These require no task registration and work against an existing DB.
    if args.cmd in {"status", "running", "pending", "dlq-list", "dlq-replay", "enqueue", "worker"}:
        import json as _json
        from . import SqliteStorage, Job as _Job, RetryPolicy as _RetryPolicy, Worker as _Worker
        import importlib as _importlib
        import logging as _logging
        import threading as _threading
        import time as _time

        db = getattr(args, "db", "pinion.db")
        s = SqliteStorage(db)
        if args.cmd == "status":
            qsize = s.size()
            counts = s._conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status;").fetchall()
            dlq = s._conn.execute("SELECT COUNT(*) FROM dlq;").fetchone()[0]
            print("queue size:", qsize)
            print("jobs by status:", dict(counts))
            print("dlq count:", dlq)
            return
        if args.cmd == "running":
            rows = s._conn.execute(
                "SELECT id, func_name, attempts, heartbeat_at, created_at FROM jobs WHERE status='RUNNING' ORDER BY heartbeat_at DESC NULLS LAST, created_at DESC LIMIT ?;",
                (args.limit,),
            ).fetchall()
            for r in rows:
                print(r)
            if not rows:
                print("(none)")
            return
        if args.cmd == "pending":
            rows = s._conn.execute(
                "SELECT id, func_name, attempts, created_at FROM jobs WHERE status='PENDING' ORDER BY created_at ASC LIMIT ?;",
                (args.limit,),
            ).fetchall()
            for r in rows:
                print(r)
            if not rows:
                print("(none)")
            return
        if args.cmd == "dlq-list":
            rows = s._conn.execute(
                "SELECT id, func_name, attempts, error, failed_at FROM dlq ORDER BY failed_at DESC LIMIT ?;",
                (args.limit,),
            ).fetchall()
            for r in rows:
                print(r)
            if not rows:
                print("(empty)")
            return
        if args.cmd == "dlq-replay":
            rows = s._conn.execute(
                "SELECT id, func_name, args, kwargs FROM dlq ORDER BY failed_at ASC LIMIT ?;",
                (args.limit,),
            ).fetchall()
            count = 0
            for _id, func_name, ajson, kjson in rows:
                args_tuple = tuple(_json.loads(ajson))
                kwargs_dict = _json.loads(kjson)
                s.enqueue(_Job(func_name, args_tuple, kwargs_dict))
                s._conn.execute("DELETE FROM dlq WHERE id=?;", (_id,))
                count += 1
            print(f"replayed {count} job(s)")
            return
        if args.cmd == "enqueue":
            pos_args = tuple(_json.loads(args.args) if getattr(args, "args", None) else [])
            kw_args = _json.loads(args.kwargs) if getattr(args, "kwargs", None) else {}
            s.enqueue(_Job(args.task, pos_args, kw_args))
            print(f"enqueued {args.task} -> args={pos_args} kwargs={kw_args}")
            return
        if args.cmd == "worker":
            # Optional imports to register tasks in this process
            if getattr(args, "imports", None):
                for mod in args.imports:
                    try:
                        _importlib.import_module(mod)
                    except Exception as e:
                        print(f"failed to import {mod!r}: {e}")
            _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
            retry = _RetryPolicy(max_retries=args.max_retries, base_delay=args.base_delay, jitter=not args.no_jitter)
            w = _Worker(s, retry=retry, poll_timeout=0.1, task_timeout=args.task_timeout, visibility_timeout=args.visibility_timeout)
            if args.run_seconds and args.run_seconds > 0:
                t = _threading.Thread(target=w.run_forever, daemon=True)
                t.start()
                try:
                    _time.sleep(args.run_seconds)
                except KeyboardInterrupt:
                    pass
                finally:
                    w.stop(); t.join(); w.join(1.0)
                    print("metrics:", w.metrics)
            else:
                try:
                    w.run_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    w.stop(); w.join(1.0)
                    print("metrics:", w.metrics)
            return

    # Otherwise, print a concise CLI guide and exit
    guide = """
Pinion {version}

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

Admin (SQLite):
  pinion status --db pinion.db
  pinion running --db pinion.db --limit 10
  pinion pending --db pinion.db --limit 10
  pinion dlq-list --db pinion.db --limit 10
  pinion dlq-replay --db pinion.db --limit 10
  pinion enqueue TASK --db pinion.db --args '[]' --kwargs '{{}}'
  pinion worker --db pinion.db --max-retries 2 --task-timeout 5 \
    --import your_project.tasks  # import modules to register tasks

CLI tips:
  Show version:      pinion --version
  Run tiny demo:     pinion --demo
  Disable update chk: PINION_NO_UPDATE_CHECK=1 or pinion --no-update-check

Docs: README.md • Changelog: CHANGELOG.md • PyPI: pinion-queue
""".format(version=__version__)
    print(guide.strip())
    return
