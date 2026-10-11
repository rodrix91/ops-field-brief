# ops-field-brief

A small standard-library Python CLI that answers three questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `null`, and `s/d` count as missing.
- Does the business key repeat?
- Which groups account for the rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness (fill rate, repeated keys, top groups).

Status: 0.1.0, verified by the tests in this repository. It is not a production pipeline.

Suggested topics: `csv`, `data-quality`, `operations`, `cli`, `python`, `standard-library`.

## Why this exists

Operational extracts (shipments, orders, inventory movements) often need a fast check before they enter a process: are the required fields present, does the business key repeat, and which counterparties dominate the file? This tool answers those three questions with one command and a clear exit code.

## Install and run

Python 3.10 or newer. No third-party packages.

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

Exit code `0` means every required field is within `--max-missing` (default `0`). Exit code `1` means at least one required field is too empty. Exit code `2` means the file or the arguments could not be used.

`--json` writes the same brief as JSON.

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

The suite covers fill counts, repeated keys, unknown columns, and a passing CLI run. It uses the standard library only.

## Maintenance

The tool is intentionally small and focused. Changes are kept additive. Existing behavior and history are preserved.

## Contributing

Issues and pull requests are welcome. Please keep changes small and additive. The project uses the standard library only and is intentionally focused.

## License

MIT. See the [LICENSE](LICENSE) file. Copyright (c) 2026 Rodrigo Pantoja Navajas.
