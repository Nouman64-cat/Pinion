Contributing to Pinion

Thanks for your interest in improving Pinion! This guide covers how to set up a dev environment, coding standards, and how to propose changes.

Quick Start

- Requirements: Python 3.12+, git, pip/venv
- Setup:
  1) Clone: `git clone https://github.com/Nouman64-cat/Pinion && cd Pinion`
  2) Create venv: `python -m venv .venv && . .venv/bin/activate` (Windows: `.venv\\Scripts\\activate`)
  3) Install package in editable mode: `pip install -e .`
  4) (Optional) Docs tooling: `pip install mkdocs`

Running Locally

- Run the tiny demo: `pinion --demo` (or `python -m pinion.cli --demo`)
- Try SQLite admin commands (will create `pinion.db` locally):
  - `pinion status --db pinion.db`
  - `pinion dlq-list --db pinion.db --limit 5`
  - `pinion worker --db pinion.db --run-seconds 5`

Development Workflow

- Use feature branches: `git checkout -b feat/my-change`
- Keep PRs small, focused, and well‑scoped
- Write clear commit messages using Conventional Commits where possible, e.g.:
  - `feat(worker): add pause/resume`
  - `fix(sqlite): prevent busy timeout on claim`
  - `docs(cli): clarify dlq-replay usage`
- Add or update documentation in `docs/docs/` when behavior or public API changes
- Update `CHANGELOG.md` and `docs/docs/changelog.md` for noteworthy changes

Coding Guidelines

- Favor clarity and minimalism; avoid unnecessary complexity or external deps
- Use type hints consistently; prefer `dataclass(slots=True)` where appropriate
- Keep public API stability (see exports in `pinion/__init__.py`)
- Match existing style patterns:
  - Logging via `logging` with concise, structured messages
  - Storage backends implement `pinion.storage.Storage` protocol
  - Tasks are registered via `@pinion.task()` and resolved case‑insensitively
- Keep changes tightly scoped to the task at hand

Docs

- Docs live under `docs/` and are built with MkDocs
- Preview locally: `mkdocs serve -f docs/mkdocs.yml`
- Keep API pages aligned with code (modules: `pinion.types`, `pinion.worker`, etc.)

Reporting Issues

- Include steps to reproduce, expected vs actual behavior, and environment info
- If relevant, share minimal code snippets and error logs

Releases (maintainers)

- Bump version in `pyproject.toml` and `pinion/__init__.py`
- Update changelogs
- Build and publish using the configured tooling (hatchling)

Code of Conduct

- Be respectful and constructive. We welcome all contributions that improve the project.

