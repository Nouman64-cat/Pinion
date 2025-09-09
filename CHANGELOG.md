# Changelog

All notable changes to this project will be documented in this file.

## 0.2.7 — Typing marker

- Add PEP 561 marker file `pinion/py.typed` and include it in wheels/sdists so type checkers (e.g., mypy, pyright) recognize Pinion as typed.

## 0.2.6 — CLI quickstart fix + improved demo

- Fix: crash when running `pinion` due to unescaped braces in the quickstart guide string. Switched to safe formatting and escaped examples.
- Demo: `pinion --demo` now shows a professional, deterministic demo (greet + transient retry) and prints metrics.
- Quickstart: includes author credit (Nouman Ejaz).
- No API changes. Recommended update for anyone using the CLI.

## 0.2.5 — CLI admin tools + worker

- CLI: added useful SQLite admin subcommands:
  - `status`, `running`, `pending`, `dlq-list`, `dlq-replay`, `enqueue`.
- CLI: added `worker` subcommand to run a worker against a SQLite DB with flags for retries/timeouts and optional module imports for task registration.
- CLI: quickstart updated to include admin cheat sheet.
- Docs: README updated with CLI usage examples.

## 0.2.4 — CLI quickstart by default

- CLI: default execution now prints a concise quickstart guide instead of running a demo.
- CLI: retained `--demo` for a minimal example; `--version` and update check remain.

## 0.2.3 — Update notice + docs

- CLI: optional update check against PyPI (disabled via `--no-update-check` or `PINION_NO_UPDATE_CHECK=1`).
- Docs: added Changelog; README upgrade instructions and links.

## 0.2.2 — Export SqliteStorage

- Public API: exported `SqliteStorage` at top-level (`from pinion import SqliteStorage`).

## 0.2.1 — CLI polish

- Added `pinion-queue` console alias.
- Added `--version` flag.

## 0.2.0 — Reliability upgrades

- SQLite thread-safety via connection lock.
- Failure marking for missing tasks.
- Dead-letter queue (DLQ) for exhausted retries (SQLite table `dlq`).
- Per-task timeout (thread-based).
- Basic worker metrics and join/shutdown polish.
- Tests + CI.
