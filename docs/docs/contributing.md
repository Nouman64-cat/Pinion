## Contributing

- Use Python 3.12+.
- Install dev deps and Pinion in editable mode: `pip install -e .`.
- Run tests: `pytest -q`.
- Keep changes focused; match code style and patterns.
- Update docs when introducing or changing public APIs.

Release checklist (maintainers):

1) Bump versions in `pyproject.toml` and `pinion/__init__.py`.
2) Build: `python -m build` and `twine check dist/*`.
3) Publish: `twine upload dist/*`.
4) Tag: `git tag vX.Y.Z && git push --tags`.

