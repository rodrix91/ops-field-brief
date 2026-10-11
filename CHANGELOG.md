# Changelog

## 0.1.0

- Operational brief: fill rate, repeated business keys, and top groups.
- `--delimiter` accepts `comma` (default), `semicolon`, `tab`, and `pipe`. Comma stays the default.
- `--encoding` accepts a Python codec. Default is `utf-8`. Use `cp1252` or `latin-1` for Windows Excel exports.
- Missing tokens include empty cells, `NA`, `null`, and `s/d`.
- Exit codes: `0` within the fill limit, `1` fill check failed, `2` file or arguments could not be used.
