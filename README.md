# ops-field-brief

A small standard-library Python CLI that answers three questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `null`, and `s/d` count as missing.
- Does the business key repeat?
- Which groups account for the rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness.

Status: 0.1.0, verified by the tests in this repository. It is not a production pipeline.

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
