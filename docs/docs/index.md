# Pinion

> Tiny, pluggable Python job queue with retries and a durable SQLite backend.

Key features:

- In-memory queue with thread-safe `Condition` coordination
- Durable SQLite storage with atomic job claim (WAL) across processes
- Pluggable `Storage` protocol (SPI) for custom backends
- Worker loop with polling, retries, timeouts, and graceful stop/join
- Exponential backoff retries with optional jitter and cap
- Dead-letter queue (DLQ) after exhausted retries
- Basic worker metrics and job lifecycle tracking

!!! info "Requirements"
    Python 3.12+

Get started in minutes in the Quickstart, or dive into Concepts and the API reference.

!!! tip "Links"
    - Source: https://github.com/Nouman64-cat/Pinion  
    - PyPI: pinion-queue  
    - Changelog: see Changelog page
