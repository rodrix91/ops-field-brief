# Operations playbook

Practical, reproducible checks for CSV extracts used in shipping, order processing, and other operations workflows.

**Start here:** [Project README](../README.md) · [Changelog](../CHANGELOG.md) · [Security policy](../SECURITY.md) · [Contributing](../CONTRIBUTING.md)

## 1. Choose the quality gate

| Operational question | CLI option | Interpretation |
|---|---|---|
| Are mandatory cells present? | `--required shipment,buyer,eta --max-missing 0` | Exit `1` when a named field has missing values; missing is evaluated per field |
| Does a business key repeat? | `--key shipment --max-duplicates 0` | Counts extra rows after the first occurrence of each nonblank complete key |
| Is the extract unexpectedly small? | `--min-rows 100` | Exit `1` when the data-row count is below the threshold |
| Is the data concentrated in one group? | `--group buyer --max-group-share 0.60` | Exit `1` if the largest group accounts for more than 60% of data rows |
| Are columns structurally consistent? | `--strict-csv` | Exit `2` on duplicate or blank headers and rows with the wrong number of fields |
| Is a composite key unique? | `--key order_id,line_id --max-duplicates 0` | Repeats are checked on complete tuples, not on each column in isolation |

These controls are opt-in except `--required`. Gate thresholds are examples, not universal business rules. Agree on suitable limits with the data owner before using them to block a delivery.

## 2. Check an export locally

From a checkout, with Python 3.10 or newer:

```bash
PYTHONPATH=src python -m ops_field_brief examples/shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --max-duplicates 0 \
  --group buyer \
  --strict-csv
```

The included `examples/shipments.csv` intentionally contains a repeated shipment and incomplete fields; this check demonstrates a failed operational gate. Use `--json` when a downstream process needs machine-readable results, for example:

```bash
PYTHONPATH=src python -m ops_field_brief examples/shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --json
```

For semicolon-separated exports commonly produced by regional spreadsheet tools:

```bash
PYTHONPATH=src python -m ops_field_brief examples/shipments-semicolon.csv \
  --required envio,comprador,eta \
  --key envio \
  --delimiter semicolon \
  --strict-csv
```

Use `--delimiter auto` only when the separator varies, and specify `--encoding cp1252` or `latin-1` explicitly if the source file uses that encoding.

## 3. Interpret the outcome

| Exit code | Meaning | Recommended pipeline action |
|---|---|---|
| `0` | All enabled quality gates passed | Allow the next processing step |
| `1` | An enabled completeness, duplicate, row-count, or concentration gate failed | Quarantine or review the extract; do not silently ignore the alert |
| `2` | CSV structure, file access, encoding, field selection, or CLI arguments are invalid | Repair the input or configuration and rerun the check |

The number of extra duplicate rows is not the number of distinct repeated keys. Blank key components are excluded from duplicate counting. A zero-row extract passes the default gate unless `--min-rows` is set. Treat an empty or unexpectedly small extract as a separate operational risk.

## 4. Run a gate in GitHub Actions

A consumer workflow can call the reusable composite Action after checking out its own data:

```yaml
name: check-operational-extract
on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - name: Validate operational export
        id: brief
        uses: rodrix91/ops-field-brief@main
        with:
          path: data/shipments.csv
          args: --required shipment,buyer,eta --key shipment --max-duplicates 0 --strict-csv
          summary: "false"
```

`@main` follows new commits. For stable or regulated pipelines, replace it with an **actual reviewed commit SHA** from the repository. A reusable Action input `path` must be relative to the caller's `GITHUB_WORKSPACE`. Absolute paths, traversal outside the workspace, symlink escapes, and stdin (`-`) are rejected before the CLI starts. Quality failures and invalid inputs cause the Action to fail while still populating `exit-code` and `passed` outputs.

Set `summary: "false"` when group labels or other CSV values are confidential. Job logs may still contain report output; do not run sensitive exports on workflows whose logs can be viewed by unauthorized people. The Action does not upload files or call a paid model API.

## 5. Validate and cite the work

Run the repository test suite before making changes:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The repository additionally checks lint, formatting, type checking, packaging, the installed CLI, and Action behavior in GitHub CI. See [CITATION.cff](../CITATION.cff) for software citation metadata and [SECURITY.md](../SECURITY.md) for reporting vulnerabilities privately.

## 6. Scope and limitations

This is a **lightweight operational gate**, not a full ETL validator, entity-resolution engine, anomaly detector, or guarantee of business correctness. A `0` exit status means only that *the selected checks* passed. Data owners remain responsible for accurate thresholds, representative sample sizes, privacy and access controls, and operational review.
