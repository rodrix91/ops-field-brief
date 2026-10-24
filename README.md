# ops-field-brief

[![CI](https://github.com/rodrix91/ops-field-brief/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrix91/ops-field-brief/actions/workflows/ci.yml)


A small standard-library Python CLI that answers five practical questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `N/A`, `null`, `none`, `s/d`, `s.d.`, `N/D`, `N.D.`, and `-` count as missing.
- Does the business key repeat?
- Which groups account for the rows?
- Does one group dominate more of the extract than allowed?
- Does the extract contain at least the expected number of data rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness (fill rate, repeated keys, top groups).

Status: 0.3.0 with additional Unreleased work, verified by the tests in this repository. It is not a production pipeline. See [CHANGELOG.md](CHANGELOG.md).

Topics (set on the repository): `csv`, `data-quality`, `operations`, `cli`, `python`, `standard-library`.

For a concise checklist of operational gates, example commands, and safe CI integration, see the [operations playbook](docs/README.md).

## Why this exists

Operational extracts (shipments, orders, inventory movements) often need a fast check before they enter a process: are the required fields present, does the business key repeat, which counterparties dominate the file, and did the extract contain enough rows to be plausible? This tool answers those questions with one command and a clear exit code.

## Structural CSV validation (opt-in)

For critical operational extracts, add `--strict-csv` to reject malformed CSV
structure **before** any completeness, duplicate-key, or concentration metrics
are calculated. It reports an input error (exit code `2`) for:

- missing, blank, or duplicate header names (names are compared after trimming spaces);
- data rows with more fields than the header;
- data rows with fewer fields than the header.

For example:

```bash
python -m ops_field_brief shipments.csv --required shipment,buyer,eta --strict-csv
```

This check works with stdin, explicit delimiters, and `--delimiter auto`.
An **empty cell** in a correctly sized row is still valid CSV structure and is
handled by the existing fill-rate gate. For compatibility, the default remains
permissive, including the standard CSV reader's last-value-wins behavior for
duplicate header names. Enable strict mode when a silent column shift or lost
field would make the report misleading.

## Install and run

Python 3.10 or newer. No third-party packages. From a checkout:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

After `pip install .`, the same command is available as `ops-field-brief`. Use `ops-field-brief --version` to confirm the installed version.

Exit code `0` means every enabled quality gate passes. Exit code `1` means at least one required field is too empty, repeated keys exceed `--max-duplicates`, incomplete key rows exceed `--max-incomplete-keys`, the data-row count is below `--min-rows`, or the largest `--group` exceeds `--max-group-share`. Exit code `2` means the file or the arguments could not be used, including an unknown `--encoding`, a `--max-missing` or `--max-group-share` outside 0 to 1, a negative `--max-duplicates` or `--min-rows`, an empty `--required` list, an unknown `--key` or `--group`, using `--max-group-share` without `--group`, a negative `--top`, or an unknown `--delimiter`.

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

To flag an extract when one buyer, supplier, carrier, or other group dominates too much of the file, combine `--group` with `--max-group-share`:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --group buyer \
  --max-group-share 0.60
```

The threshold is a share from `0` to `1`. The gate is opt-in, so existing commands keep their current behavior.

## GitHub Action

The repository also exposes a composite GitHub Action for operational CSV gates. It runs the same standard-library CLI directly from the checked-out Action source, so no package installation or runtime dependency is added.

Until a future release includes the Action, `@main` follows Unreleased changes; pin a reviewed commit SHA instead when reproducibility matters.

The Action rejects informational CLI flags (`-h`, `--help`, `--version`, and accepted long-option abbreviations) with `exit-code=2` and `passed=false`. Without this protection, an informational command would exit successfully **without checking any CSV**, falsely satisfying a pipeline gate. To display help or a version, invoke the standalone CLI instead.

For safety, the Action `path` must name a CSV **inside the caller's `GITHUB_WORKSPACE`**. Absolute paths, `../` paths that leave the workspace, symlinks that resolve outside it, and stdin (`-`) are rejected before the CLI runs (exit code `2`, `passed=false`). Ordinary nested relative paths, including paths through symlinks that remain inside the workspace, are supported. This boundary protects against unintended reads outside the job checkout; it does not make untrusted CSV content safe to publish in logs or job summaries.

```yaml
steps:
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7

  - name: Check shipment extract
    id: brief
    uses: rodrix91/ops-field-brief@main
    with:
      path: data/shipments.csv
      args: --required shipment,buyer,eta --key shipment --max-duplicates 0 --strict-csv

  - name: Use the result
    run: echo "passed=${{ steps.brief.outputs.passed }}"
```

A CLI exit code other than `0` fails the Action step, so quality-gate failures naturally stop a workflow unless the caller uses `continue-on-error`. The Action still writes two outputs before returning:

| Output | Meaning |
|---|---|
| `exit-code` | The CLI exit code (`0` pass, `1` failed quality gate, `2` unusable input/arguments) |
| `passed` | `true` only when the CLI returned `0` |

Inputs:

| Input | Default | Meaning |
|---|---|---|
| `path` | required | CSV path relative to the caller workspace |
| `args` | `""` | Additional CLI arguments; quoted values are parsed as arguments, never evaluated as shell code |
| `python-version` | `3.12` | Python used by the Action |
| `summary` | `true` | Append the Markdown report to the job summary; JSON output is fenced as JSON |

The repository CI runs the Action end to end with one passing extract and one deliberate failed duplicate-key gate, and verifies both outputs.

## Verify release artifacts

Releases produced by the current release workflow include a `SHA256SUMS` file and GitHub artifact provenance attestations for the wheel and source distribution. After downloading the release files into one directory, verify the checksums:

```bash
sha256sum -c SHA256SUMS
```

Then verify provenance for each artifact with GitHub CLI:

```bash
gh attestation verify PATH/TO/ARTIFACT -R rodrix91/ops-field-brief
```

Historical releases created from older commits may predate checksums or provenance attestations; verify only the guarantees actually published with that release.

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

The suite covers fill counts, repeated keys, three identical keys, two repeated keys, blank keys, `--max-duplicates` allowing repeated keys within limits and failing when exceeded, a negative `--max-duplicates`, missing tokens including `N/D` and `s.d.`, unknown columns, an unknown key and an unknown group, a passing CLI run, semicolon, tab and pipe exports, an unknown delimiter, a cp1252 file, a UTF-8 BOM, a UTF-8 BOM on stdin, an unknown encoding, an empty required list, `--json`, blank groups, a five-group limit, `--top`, `--top 0`, a negative `--top`, a quoted field with a comma, an escaped quote, a multiline quoted field, a trailing comma, a whitespace-only field, a tab-only field, a duplicate header, a header-only file, an empty file, stdin, `--help`, `--max-missing` allowing a share of blanks, and `--max-missing` outside 0 to 1, `--min-rows` passing/failing row-count gates, JSON gate metadata, and a negative `--min-rows`. Strict CSV validation is covered for duplicate or blank headers and ragged rows. Eighty-five tests. It uses the standard library only. The installed package ships a PEP 561 `py.typed` marker so downstream type checkers can consume its inline annotations. CI runs the suite on Python 3.10 through 3.13 on Ubuntu, plus Python 3.10 and 3.13 on Windows and macOS.

## Maintenance

The tool is intentionally small and focused. Changes are kept additive. Existing behavior and history are preserved.

The scheduled weekly engineering audit is local-only and read-only. Even if `GEMINI_API_KEY` exists in the environment, the maintenance script will not make an external API call unless a manual run also passes `--allow-external-api`.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the setup, the test command, and the guidelines. Please keep changes small and additive. The project uses the standard library only and is intentionally focused. Bug and feature forms ask for the command or the problem, and the expected result. Blank issues are disabled. A pull request template asks for the summary and the local test check.

Report a security problem through [SECURITY.md](SECURITY.md), not in a public issue.

## Citation

If you use `ops-field-brief` in research, teaching, or a reproducible operational workflow, cite the software using [CITATION.cff](CITATION.cff). The citation metadata is included in the source distribution and linked from the package metadata.

## License

MIT. See the [LICENSE](LICENSE) file. Copyright (c) 2026 Rodrigo Pantoja Navajas.
