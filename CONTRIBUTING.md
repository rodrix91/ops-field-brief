# Contributing

Project status: 0.3.0, maintained by rodrix91. Small, focused, additive changes with tests are welcome.

## Setup

Requires Python 3.10 or newer. Runtime remains standard-library only. Development tooling is pinned separately:

```bash
python -m pip install -r requirements-dev.txt
```

Run the compatibility suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## Checks

Before opening a pull request:

1. Run `coverage run -m unittest discover -s tests && coverage combine && coverage report`. Branch coverage must stay at or above 90%.
2. Run `ruff check .` and `ruff format --check .`.
3. Run `mypy`.
4. Keep the runtime standard-library only. Development-only tools belong in `requirements-dev.txt`.
5. Add or update a test in `tests/test_brief.py` for every behavior change.
6. Update `README.md` and `CHANGELOG.md` when behavior or the test count changes.


## Releases

Releases are tag-driven and must use a semantic version tag such as `v0.2.0`.

1. Update `ops_field_brief.__version__` and the changelog in a reviewed pull request.
2. Merge only after CI passes.
3. Create the matching `vX.Y.Z` tag on that validated commit.
4. The release workflow checks that the tag matches the package version, builds the wheel and source distribution, tests both artifacts, and creates the GitHub release.

Do not tag a commit whose runtime version does not match the tag. The workflow fails before publishing in that case.

## Guidelines

- Keep changes small and additive. Existing behavior and history are preserved.
- Prefer a new test that locks the new behavior over a large rewrite.
- Use small commits with honest messages.

## License

By contributing you agree that your contribution is licensed under the MIT License (see `LICENSE`).
