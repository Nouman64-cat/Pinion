# Changelog

All notable changes to this project will be documented in this file.

## 0.2.5 — CLI quickstart fix

- Fix: crash when running `pinion` due to unescaped braces in the quickstart guide string. Switched to safe formatting and escaped examples.
- No API changes. Recommended update for anyone using the CLI.

## 0.2.4 — CLI quickstart + admin tools

- CLI: default execution now prints a concise quickstart guide instead of running a demo.
- CLI: added useful SQLite admin subcommands:
  - `status`, `running`, `pending`, `dlq-list`, `dlq-replay`, `enqueue`.
- CLI: added `worker` subcommand to run a worker against a SQLite DB with flags for retries/timeouts and optional module imports for task registration.
- CLI: retained `--demo` for the tiny in-memory example; `--version` and update check remain.
- Docs: README updated with CLI usage examples.

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
