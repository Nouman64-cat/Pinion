# Changelog

All notable changes to this project will be documented in this file.

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

