# ops-field-brief

A small standard-library Python CLI that answers three questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `N/A`, `null`, `none`, `s/d`, `s.d.`, `N/D`, `N.D.`, and `-` count as missing.
- Does the business key repeat?
- Which groups account for the rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness (fill rate, repeated keys, top groups).

Status: 0.1.0, verified by the tests in this repository. It is not a production pipeline. See [CHANGELOG.md](CHANGELOG.md).

Suggested topics: `csv`, `data-quality`, `operations`, `cli`, `python`, `standard-library`.

## Why this exists

Operational extracts (shipments, orders, inventory movements) often need a fast check before they enter a process: are the required fields present, does the business key repeat, and which counterparties dominate the file? This tool answers those three questions with one command and a clear exit code.

## Install and run

Python 3.10 or newer. No third-party packages. From a checkout:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

After `pip install .`, the same command is available as `ops-field-brief`.

Exit code `0` means every required field is within `--max-missing` (default `0`). Exit code `1` means at least one required field is too empty. Exit code `2` means the file or the arguments could not be used, including an unknown `--encoding`, a `--max-missing` outside 0 to 1, an empty `--required` list, or an unknown `--key` or `--group`.

`--json` writes the same brief as JSON. `--delimiter` accepts `comma` (default), `semicolon`, `tab`, or `pipe`. The default keeps the original comma behavior.

`--encoding` defaults to `utf-8`. A UTF-8 BOM, common in Excel exports, is stripped so the first column name stays usable. For a Windows Excel export in Spanish, pass `--encoding cp1252` or `--encoding latin-1`.

A blank `--group` value is reported as `(blank)`. A blank `--key` is not counted as a repeat. A header-only file and an empty file report `0` rows and exit `0`.

Semicolon exports, common in Spanish and Latin American spreadsheets:

```bash
python -m ops_field_brief examples/shipments-semicolon.csv \
  --required envio,comprador,eta \
  --delimiter semicolon \
  --key envio
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

The suite covers fill counts, repeated keys, blank keys, missing tokens including `N/D` and `s.d.`, unknown columns, an unknown key and an unknown group, a passing CLI run, semicolon, tab and pipe exports, a cp1252 file, a UTF-8 BOM, an unknown encoding, an empty required list, `--json`, blank groups, a header-only file, an empty file, `--max-missing` allowing a share of blanks, and `--max-missing` outside 0 to 1. It uses the standard library only. CI runs the same suite on Python 3.10 through 3.13.

## Maintenance

The tool is intentionally small and focused. Changes are kept additive. Existing behavior and history are preserved.

## Contributing

Issues and pull requests are welcome. Please keep changes small and additive. The project uses the standard library only and is intentionally focused. Bug and feature forms ask for the command or the problem, and the expected result. Blank issues are disabled. A pull request template asks for the summary and the local test check.

Report a security problem through [SECURITY.md](SECURITY.md), not in a public issue.

## License

MIT. See the [LICENSE](LICENSE) file. Copyright (c) 2026 Rodrigo Pantoja Navajas.
