# Operations playbook

Practical, reproducible checks for CSV extracts used in shipping, order processing, and other operations workflows.

**Start here:** [Project README](../README.md) · [Changelog](../CHANGELOG.md) · [Security policy](../SECURITY.md) · [Contributing](../CONTRIBUTING.md)

## 1. Choose the quality gate

| Operational question | CLI option | Interpretation |
|---|---|---|
| Are mandatory cells present? | `--required shipment,buyer,eta --max-missing 0` | Exit `1` when a named field has missing values; missing is evaluated per field |
| Does a business key repeat? | `--key shipment --max-duplicates 0` | Counts extra rows after the first occurrence of each complete key (no blank or missing-value token) |
| Are business keys incomplete? | `--key order_id,line_id --max-incomplete-keys 0` | Exit `1` when any row has a blank or known missing-value token in a key component; duplicate counting ignores incomplete keys |
| Are there enough usable business identifiers? | `--key order_id,line_id --min-complete-keys 100` | Exit `1` if fewer than 100 rows have **every** key component present; complete duplicates still count toward the minimum |
| Are there enough distinct business identifiers? | `--key order_id,line_id --min-distinct-keys 100` | Exit `1` if fewer than 100 **unique complete** key tuples exist, so repeats cannot inflate the count; missing components are excluded |
| Is the extract unexpectedly small? | `--min-rows 100` | Exit `1` when the data-row count is below the threshold |
| Is the data concentrated in one group? | `--group buyer --max-group-share 0.60` | Exit `1` if the largest group exceeds 60% of rows; blank, `NA`, `N/A`, `s/d` etc. share the `(blank)` bucket |
| Are columns structurally consistent? | `--strict-csv` | Exit `2` on duplicate or blank headers and rows with the wrong number of fields |
| Can column names collide across spreadsheets or Unicode casing? | `--strict-csv --casefold-headers` | Exit `2` when headings differ only by Unicode case folding (such as `id`/`ID` or `Straße`/`STRASSE`); original header names remain unchanged |
| Is a composite key unique? | `--key order_id,line_id --max-duplicates 0` | Repeats are checked on complete tuples, not on each column in isolation |

A comma-separated `--key` must specify every component: `--key order_id,,line_id` (or a leading/trailing comma) is invalid and returns exit `2` rather than silently changing the key. This is checked by the CLI and the reusable Action.

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

For an extract with a composite order-line identifier, separate missing-key risk from repeated-key risk:

```bash
PYTHONPATH=src python -m ops_field_brief examples/orders-incomplete-keys.csv \
  --required order_id --max-missing 1 \
  --key order_id,line_id --max-incomplete-keys 1 --json
```

The five-row synthetic fixture includes two rows with a blank key component and one extra duplicate complete key. The limit of one incomplete key fails independently of the duplicate count. Blank or missing includes empty/whitespace-only components and known placeholders such as `NA`, `N/A`, `null` and `s/d`. Incomplete keys are excluded from duplicate counting, and `--max-incomplete-keys` is the independent gate for them. Required-field checks share the same missing-value rules. Without `--max-incomplete-keys`, incomplete keys are reported but do not by themselves fail the command.

For an independent **minimum usable-identifier** gate on that same fixture, combine the two newer options:

```bash
PYTHONPATH=src python -m ops_field_brief examples/orders-incomplete-keys.csv \
  --key order_id,line_id \
  --min-complete-keys 4 \
  --max-duplicates 0 \
  --strict-csv --casefold-headers --json
```

The five-row fixture contains **three complete-key rows** (including one duplicated key) and **two incomplete-key rows**. The command therefore fails with exit `1` because the minimum is four and there is one extra duplicate row. These checks are independent: `--min-complete-keys 3` passes the complete-key threshold without making a repeated business key unique. Strict Unicode case-folding is enabled only alongside `--strict-csv` and does not rename columns, change the original CSV, or alter the default case-sensitive strict check. On duplicate case-equivalent headings, the structure check exits `2` before quality metrics are produced.

## 3. Interpret the outcome

| Exit code | Meaning | Recommended pipeline action |
|---|---|---|
| `0` | All enabled quality gates passed | Allow the next processing step |
| `1` | An enabled completeness, duplicate, row-count, or concentration gate failed | Quarantine or review the extract; do not silently ignore the alert |
| `2` | CSV structure, file access, encoding, field selection, or CLI arguments are invalid | Repair the input or configuration and rerun the check |

The number of extra duplicate rows is not the number of distinct repeated keys. Blank key components are excluded from duplicate counting. A zero-row extract passes the default gate unless `--min-rows` or a positive `--min-complete-keys` is set. Treat an empty or unexpectedly small extract as a separate operational risk.

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

`@main` follows new commits. For stable or regulated pipelines, replace it with an **actual reviewed commit SHA** from the repository. The reusable Action rejects `-h`, `--help`, `--version` and accepted abbreviations before running the CSV checker. These informational flags are valid in the standalone CLI but **must not produce a passing pipeline result without validating the extract**.

A reusable Action input `path` must be relative to the caller's `GITHUB_WORKSPACE`. Absolute paths, traversal outside the workspace, symlink escapes, and stdin (`-`) are rejected before the CLI starts. Quality failures and invalid inputs cause the Action to fail while still populating `exit-code` and `passed` outputs.

Set `summary: "false"` when group labels or other CSV values are confidential. Job logs may still contain report output; do not run sensitive exports on workflows whose logs can be viewed by unauthorized people. The Action does not upload files or call a paid model API.

## 5. Validate and cite the work

Run the repository test suite before making changes:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The repository additionally checks lint, formatting, type checking, packaging, the installed CLI, and Action behavior in GitHub CI. See [CITATION.cff](../CITATION.cff) for software citation metadata and [SECURITY.md](../SECURITY.md) for reporting vulnerabilities privately.

## 6. Scope and limitations

This is a **lightweight operational gate**, not a full ETL validator, entity-resolution engine, anomaly detector, or guarantee of business correctness. A `0` exit status means only that *the selected checks* passed. Data owners remain responsible for accurate thresholds, representative sample sizes, privacy and access controls, and operational review.
