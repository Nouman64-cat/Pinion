## Contributing

- Use Python 3.12+.
- Install dev/test extras in editable mode: `pip install -e ".[dev]"` (or `.[tests]` if you only need the suite).
- Run tests from the project root: `pytest -q` (append `--cov` for coverage details).
- Keep changes focused; match code style and patterns.
- Update docs when introducing or changing public APIs.

Release checklist (maintainers):

1) Bump versions in `pyproject.toml` and `pinion/__init__.py`.
2) Build: `python -m build` and `twine check dist/*`.
3) Publish: `twine upload dist/*`.
4) Tag: `git tag vX.Y.Z && git push --tags`.

