# ops-field-brief

A small standard-library Python CLI that answers four questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `N/A`, `null`, `none`, `s/d`, `s.d.`, `N/D`, `N.D.`, and `-` count as missing.
- Does the business key repeat?
- Which groups account for the rows?
- Does the extract contain at least the expected number of data rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness (fill rate, repeated keys, top groups).

Status: 0.3.0, verified by the tests in this repository. It is not a production pipeline. See [CHANGELOG.md](CHANGELOG.md).

Topics (set on the repository): `csv`, `data-quality`, `operations`, `cli`, `python`, `standard-library`.

## Why this exists

Operational extracts (shipments, orders, inventory movements) often need a fast check before they enter a process: are the required fields present, does the business key repeat, which counterparties dominate the file, and did the extract contain enough rows to be plausible? This tool answers those questions with one command and a clear exit code.

## Install and run

Python 3.10 or newer. No third-party packages. From a checkout:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

After `pip install .`, the same command is available as `ops-field-brief`. Use `ops-field-brief --version` to confirm the installed version.

Exit code `0` means every enabled quality gate passes. Exit code `1` means at least one required field is too empty, repeated keys exceed `--max-duplicates`, or the data-row count is below `--min-rows`. Exit code `2` means the file or the arguments could not be used, including an unknown `--encoding`, a `--max-missing` outside 0 to 1, a negative `--max-duplicates` or `--min-rows`, an empty `--required` list, an unknown `--key` or `--group`, a negative `--top`, or an unknown `--delimiter`.

`--json` writes the same brief as JSON. `--key` accepts one field or a comma-separated composite business key such as `order_id,line_id`; duplicate rows are counted only when the complete key repeats, and rows with a blank key component are ignored for duplicate counting. `--delimiter` accepts `comma` (default), `semicolon`, `tab`, `pipe`, or `auto`. The default keeps the original comma behavior. `auto` detects those four common separators from the input and exits `2` with a clear message when detection is ambiguous. An unknown delimiter exits `2`.

`--encoding` defaults to `utf-8`. A UTF-8 BOM, common in Excel exports, is stripped so the first column name stays usable, including on stdin. For a Windows Excel export in Spanish, pass `--encoding cp1252` or `--encoding latin-1`.

A blank `--group` value is reported as `(blank)`. A blank `--key` is not counted as a repeat. Repeated keys are counted as extra rows: three identical keys count as two, and two different keys each repeated once also count as two. Composite keys use the complete tuple of fields, so `order_id=O1,line_id=1` and `order_id=O1,line_id=2` are distinct keys. Top groups are limited to five. `--top` can lower that limit. `--top 0` reports no groups. A negative `--top` exits `2`. `--max-duplicates` limits the allowable extra rows from a repeated business key; if exceeded, the command exits `1` with a failed duplicate check. A negative `--max-duplicates` exits `2`. A quoted field that contains a comma stays one field. An escaped quote stays in the field. A multiline quoted field stays one row. A trailing comma does not break the row. A field that is only whitespace counts as missing. A field that is only a tab also counts as missing. A duplicate column name in the header uses the last value. A header-only file and an empty file report `0` rows and exit `0` by default; use `--min-rows N` when zero or undersized extracts should fail the quality gate. A path of `-` reads the CSV from stdin. `--help` exits `0` and lists the arguments.

Semicolon exports, common in Spanish and Latin American spreadsheets:

```bash
python -m ops_field_brief examples/shipments-semicolon.csv \
  --required envio,comprador,eta \
  --delimiter semicolon \
  --key envio
```


When the separator is not known in advance, let the CLI detect comma, semicolon, tab, or pipe:

```bash
python -m ops_field_brief export.csv \
  --required shipment,buyer,eta \
  --delimiter auto
```


For a business key made from more than one column, separate the key fields with commas:

```bash
python -m ops_field_brief order-lines.csv \
  --required order_id,line_id,buyer \
  --key order_id,line_id \
  --max-duplicates 0
```

## Example

`examples/shipments.csv` has a repeated shipment id, a blank ETA, and an `s/d` buyer. This command is expected to exit `1`.

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The suite covers fill counts, repeated keys, three identical keys, two repeated keys, blank keys, `--max-duplicates` allowing repeated keys within limits and failing when exceeded, a negative `--max-duplicates`, missing tokens including `N/D` and `s.d.`, unknown columns, an unknown key and an unknown group, a passing CLI run, semicolon, tab and pipe exports, an unknown delimiter, a cp1252 file, a UTF-8 BOM, a UTF-8 BOM on stdin, an unknown encoding, an empty required list, `--json`, blank groups, a five-group limit, `--top`, `--top 0`, a negative `--top`, a quoted field with a comma, an escaped quote, a multiline quoted field, a trailing comma, a whitespace-only field, a tab-only field, a duplicate header, a header-only file, an empty file, stdin, `--help`, `--max-missing` allowing a share of blanks, and `--max-missing` outside 0 to 1, `--min-rows` passing/failing row-count gates, JSON gate metadata, and a negative `--min-rows`. Fifty-six tests. It uses the standard library only. CI runs the suite on Python 3.10 through 3.13 on Ubuntu, plus Python 3.10 and 3.13 on Windows and macOS. A dedicated quality job also enforces at least 90% branch coverage, Ruff lint/format checks, and mypy type checking.

## Maintenance

The tool is intentionally small and focused. Changes are kept additive. Existing behavior and history are preserved.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the setup, the test command, and the guidelines. Please keep changes small and additive. The project uses the standard library only and is intentionally focused. Bug and feature forms ask for the command or the problem, and the expected result. Blank issues are disabled. A pull request template asks for the summary and the local test check.

Report a security problem through [SECURITY.md](SECURITY.md), not in a public issue.

## License

MIT. See the [LICENSE](LICENSE) file. Copyright (c) 2026 Rodrigo Pantoja Navajas.
