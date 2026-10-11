# Changelog

## 0.1.0

- Operational brief: fill rate, repeated business keys, and top groups.
- `--delimiter` accepts `comma` (default), `semicolon`, `tab`, and `pipe`. Comma stays the default.
- `--encoding` accepts a Python codec. Default is `utf-8`. Use `cp1252` or `latin-1` for Windows Excel exports.
- An unknown encoding exits `2` and names the codec.
- `--max-missing` can allow a share of blanks. The default remains `0`. A value outside 0 to 1 exits `2`.
- An empty `--required` list exits `2`.
- An unknown `--key` or `--group` exits `2` and names the column.
- A blank group value is reported as `(blank)`.
- `--json` writes the same brief as JSON.
- Missing tokens include empty cells, `NA`, `null`, and `s/d`.
- Exit codes: `0` within the fill limit, `1` fill check failed, `2` file or arguments could not be used.
- CI uses `actions/checkout@v7` and `actions/setup-python@v7` on Python 3.10 through 3.13.
- `SECURITY.md` explains how to report a problem in the local CLI.
- `pyproject.toml` declares Homepage, Changelog, and Issues. `MANIFEST.in` includes the license, examples, and tests.
- Bug and feature request forms ask for the command or the problem, and the expected result. Blank issues are disabled.
- A pull request template asks for the summary and the local test check.
