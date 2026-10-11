# Contributing

Project status: 0.1.0, maintained by rodrix91. Small, focused, additive changes with tests are welcome.

## Setup

Requires Python 3.10 or newer. No third-party packages. From the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

That is the same suite CI runs on Python 3.10 through 3.13.

## Checks

Before opening a pull request:

1. Run the test suite above. All tests must pass.
2. Keep the runtime standard-library only. Do not add dependencies.
3. Add or update a test in `tests/test_brief.py` for every behavior change.
4. Update `README.md` and `CHANGELOG.md` when the behavior or the test count changes.

## Guidelines

- Keep changes small and additive. Existing behavior and history are preserved.
- Prefer a new test that locks the new behavior over a large rewrite.
- Use small commits with honest messages.

## License

By contributing you agree that your contribution is licensed under the MIT License (see `LICENSE`).
