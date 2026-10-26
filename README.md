# ops-field-brief

[![CI](https://github.com/rodrix91/ops-field-brief/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrix91/ops-field-brief/actions/workflows/ci.yml)


A small standard-library Python CLI that answers eight practical questions about one operational CSV:

- Are the required fields filled? Empty cells and tokens such as `NA`, `N/A`, `null`, `none`, `s/d`, `s.d.`, `N/D`, `N.D.`, and `-` count as missing.
- Does the business key repeat? Blank keys and configured missing-value tokens (such as `NA`, `N/A`, `null` or `s/d`) are excluded from duplicate-key comparisons and counted as incomplete business-key rows when a key is selected.
- Which groups account for the rows? Empty labels and missing-value tokens such as `NA`, `N/A`, and `s/d` are grouped together as `(blank)`.
- Does one group dominate more of the extract than allowed?
- Are too many records missing a real customer, supplier, or group assignment?
- Are there enough distinct non-missing customer or supplier groups?
- Are there unexpectedly many distinct customers or suppliers, suggesting an inconsistent group field?
- Does the extract contain at least the expected number of data rows?

It is a complement to [csv-quality-report](https://github.com/rodrix91/csv-quality-report), not a replacement. Use that project to profile types, locales, and ranges. Use this one when the question is operational completeness (fill rate, repeated keys, top groups).

Status: 0.3.0 with additional Unreleased work, verified by the tests in this repository. It is not a production pipeline. See [CHANGELOG.md](CHANGELOG.md).

Topics (set on the repository): `csv`, `data-quality`, `operations`, `cli`, `python`, `standard-library`.

For a concise checklist of operational gates, example commands, and safe CI integration, see the [operations playbook](docs/README.md).

## Why this exists

Operational extracts (shipments, orders, inventory movements) often need a fast check before they enter a process: are the required fields present, does the business key repeat, which counterparties dominate the file, and did the extract contain enough rows to be plausible? This tool answers those questions with one command and a clear exit code.

## Case-insensitive group matching (opt-in)

The same counterparty may appear in an operational export as `ACME`,
`Acme` and `acme`, or in Unicode forms such as `Straße` and `STRASSE`.
Counting these as separate groups can **understate customer/supplier concentration**
and **overstate the number of distinct counterparties**. Enable
`--casefold-group` alongside `--group` to normalize non-missing group labels
using Python's Unicode `str.casefold()`:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --group buyer --casefold-group \
  --max-group-share 0.50 --min-distinct-groups 2 --json
```

The option affects all group-derived metrics: displayed top groups (their labels
are shown in normalized lowercase/casefold form), top-group concentration,
minimum distinct non-missing groups and missing-group share (the last is
unchanged for a given dataset). Trimming, missing placeholders (`NA`, `N/A`,
`s/d`, etc.) and the safe distinction between missing values and a real
`(blank)` group remain intact. All records are counted even with `--top 0`.
Original CSV content, field names, business-key matching and required-field
completion are unaffected. If counterparty capitalization is meaningful in
your source system, leave this option off.

Without `--group`, the option returns configuration exit `2`. JSON
includes `"casefold_group": true` and Markdown notes the comparison mode
**only when enabled**. The default output and existing exit codes remain
unchanged. `--casefold-key` and `--casefold-group` may be selected
independently.

## Case-insensitive business-key matching (opt-in)

Operational identifiers sometimes arrive with inconsistent capitalization (for
example, `ORD-51` and `ord-51`) even though the upstream system treats them as
the same order. Enable `--casefold-key` with `--key` to compare all business-key
components without case differences:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --key shipment --max-duplicates 0 \
  --casefold-key --json
```

The option uses Python's Unicode `str.casefold()` for each **non-missing**
key component after trimming surrounding whitespace. Thus `Straße` and
`STRASSE` match, including in composite keys, while fields with missing
tokens such as `NA` remain excluded from duplicate counting and continue to
contribute to incomplete-key counts. The original CSV and displayed key-field
names are never rewritten. Case-sensitive matching remains the default,
because some real systems intentionally distinguish identifier case.

Without `--key`, the option fails with configuration exit `2` and produces
no report. With `--max-duplicates N`, detected duplicates trigger the same
existing quality-gate exit `1`. JSON adds `"casefold_key": true` only when
enabled; previous JSON output is unchanged otherwise. The Markdown summary
records when normalized matching was selected.

## Relative duplicate-key quality gate (opt-in)

The absolute `--max-duplicates N` limit catches a fixed number of repeated
business identifiers. For exports whose row counts change every day,
`--max-duplicate-share SHARE` additionally limits the fraction of **complete
business-key rows** that repeat an earlier key:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --key shipment \
  --max-duplicate-share 0.01 --json
```

The numerator is the existing **extra duplicate row** count (one occurrence
of each complete key is not a duplicate), and the denominator is the count of
rows with all key components present. Rows with missing key components such as
`NA`, `N/A` or blank are excluded from both. For example, if an extract has
five rows, three complete keys, one repeated complete key and two incomplete
keys, the duplicate share is **1/3 = 33.33%**, not 1/5. Combine this gate
with `--max-incomplete-keys` to also limit missing identifiers.

A share between **0 and 1**, inclusive, is allowed. Exceeding the limit
returns exit `1`; invalid or missing `--key` settings return exit `2`.
A **nonempty export with no complete keys fails closed** when this gate is
enabled: a zero duplicate count in that situation would be misleading. An
empty export has no duplicate failure; use `--min-rows` to require records.

The check is independent of `--max-duplicates`, supports composite keys and
`--casefold-key`, and runs even if other report displays are restricted.
JSON reports include `max_duplicate_share`, `duplicate_share`,
`complete_key_rows` and `failed_duplicate_share` **only when selected**.
Previous JSON fields, report defaults and existing thresholds are unchanged.

## Incomplete business keys (opt-in)

Duplicate-key checks exclude rows where any key component is blank or matches a missing-value token, so a file can pass `--max-duplicates 0` while containing orders that cannot be joined to their line items. Add `--max-incomplete-keys N` with `--key` to set a separate limit for those rows:

```bash
PYTHONPATH=src python -m ops_field_brief examples/orders-incomplete-keys.csv \
  --required order_id \
  --max-missing 1 \
  --key order_id,line_id \
  --max-incomplete-keys 1 \
  --json
```

The synthetic file has **five rows**, **two incomplete composite keys** and **one extra duplicate row**. This command exits `1` because the incomplete-key count exceeds `1`, even though no duplicate gate was enabled. `--max-incomplete-keys 2` passes (exit `0`) with the same other options; a negative limit or using the limit without `--key` exits `2`.

An incomplete key is a blank/whitespace-only key component or one matching a recognized missing-value token (such as `NA`, `N/A`, `null` or `s/d`). The same missing-value rules apply to required-field checks and single or composite business keys, which are excluded from duplicate counting when incomplete. The JSON includes `incomplete_key_rows`, `max_incomplete_keys` and `failed_incomplete_keys`. The count is informational unless the new limit is provided; existing duplicate-key calculations and quality-gate defaults remain unchanged.

## Relative incomplete-key quality gate (opt-in)

For daily exports of different sizes, a fixed `--max-incomplete-keys N` threshold
may be too strict for large files or too permissive for small ones. Use
`--max-incomplete-key-share SHARE` alongside `--key` to limit the **fraction of
all data rows** with any missing business-key component:

```bash
python -m ops_field_brief examples/orders-incomplete-keys.csv \
  --required order_id --max-missing 1 --key order_id,line_id \
  --max-incomplete-key-share 0.30 --json
```

The example has five rows and two incomplete composite business keys. Its
incomplete-key share is **2/5 = 40%**, so the 30% limit fails (exit `1`);
`--max-incomplete-key-share 0.40` passes. A row is incomplete when **any**
key component is blank or a recognized missing-value token (e.g. `NA`,
`null`, `s/d`). Unlike `--max-duplicate-share`, which uses only complete
business-key rows as its denominator, this gate uses **all CSV data rows**.

Accepted limits range from `0` through `1`, inclusive. Negative, non-finite
or greater-than-one values, and use without `--key`, exit `2`. An empty
CSV has a zero incomplete-key share and can be separately rejected with
`--min-rows`; a nonempty extract with no complete keys has a share of
100%. The percentage gate is independent of the absolute incomplete-key,
duplicate-key and missing-field gates. It supports single and composite keys,
and `--casefold-key` does not change which key components are missing.

The default JSON and Markdown outputs are unchanged. When enabled, JSON
adds `max_incomplete_key_share`, `incomplete_key_share` (rounded to four
decimal places), and `failed_incomplete_key_share`; Markdown shows the
observed percentage and a failure explanation when applicable.

## Minimum distinct complete business keys (opt-in)

A file may meet `--min-complete-keys` while containing many repeated
identifiers: three copies of one order still count as three complete-key rows.
Use `--min-distinct-keys N` with `--key` to demand at least **N unique,
fully identified business keys**. Only the first occurrence of each complete
key counts, including for composite order-line identifiers. Missing key
components (blank, `NA`, `N/A`, `s/d`, etc.) are excluded. This is
independent of `--max-duplicates` and the existing complete-row threshold.

```bash
PYTHONPATH=src python -m ops_field_brief examples/orders-incomplete-keys.csv \
  --required order_id --max-missing 1 --key order_id,line_id \
  --min-complete-keys 3 --min-distinct-keys 3 --json
```

The included five-row sample has **three complete-key rows** but only
**two distinct complete composite keys** (one complete key repeats). The
complete-row minimum passes while the distinct-key minimum fails, so the
command exits `1`; `--min-distinct-keys 2` passes. The option uses
the existing `--casefold-key` setting when explicitly enabled, so key
values such as `Straße` and `STRASSE` count as one identifier only in
casefold mode. An empty extract has zero distinct complete keys: a minimum
of zero passes and a positive minimum fails.

A negative minimum or use without `--key` returns configuration exit
`2`. When selected, JSON adds `min_distinct_keys`, `distinct_keys`
and `failed_distinct_keys`; Markdown shows the observed count and any
failure. The default JSON/Markdown layouts and underlying CSV are unchanged.

## Minimum complete business-key rows (opt-in)

Use `--min-complete-keys N` with `--key` to require a minimum number of
records whose business identifiers are fully usable. Missing tokens such as
`NA`, `N/A` and `s/d` in **any** component of a composite key exclude that
row from the count. Duplicate but complete keys still count as complete rows;
use `--max-duplicates` or `--max-duplicate-share` separately to check uniqueness.

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer --key shipment --min-complete-keys 100 --json
```

The count is independent of total rows: an export can pass `--min-rows` yet
fail this gate if its identifiers are largely missing. The threshold is inclusive
(`N` complete rows pass), `0` is allowed, and empty exports fail only for a
positive minimum. A failing gate exits `1`; negative limits or the absence of
`--key` exit `2`. When enabled, JSON includes `min_complete_keys`,
`complete_key_rows`, and `failed_complete_keys`; Markdown includes the count
and the failure reason. Omitting the option preserves the previous output.

## Structural CSV validation (opt-in)

For critical operational extracts, add `--strict-csv` to reject malformed CSV
structure **before** any completeness, duplicate-key, or concentration metrics
are calculated. It reports an input error (exit code `2`) for:

- missing, blank, or duplicate header names (names are compared after trimming spaces);
- data rows with more fields than the header;
- data rows with fewer fields than the header;
- unterminated quoted fields or invalid text after a closing CSV quote.

For example:

```bash
python -m ops_field_brief shipments.csv --required shipment,buyer,eta --strict-csv
```

This check works with stdin, explicit delimiters, and `--delimiter auto`.
For extra protection against ambiguous Excel or cross-system column names,
combine `--strict-csv --casefold-headers`. This also rejects headers that
differ only by Unicode case folding—for example `id` versus `ID`,
`Straße` versus `STRASSE`, or `Σ` versus `ς`.
It operates **only in strict mode**; using it without `--strict-csv`
returns configuration exit code `2` before opening the input.
The default strict check stays case-sensitive, and the option never
renames or normalizes actual CSV headers, so `--required`, `--key`,
and `--group` continue to use their exact original column names.

An **empty cell** in a correctly sized row is still valid CSV structure and is
handled by the existing fill-rate gate. For compatibility, the default remains
permissive, including the standard CSV reader's last-value-wins behavior for
duplicate header names. Enable strict mode when a silent column shift or lost
field would make the report misleading.

## Per-field missing limits (opt-in)

Operational exports often need different completeness targets: an order ID must
always be present, while an estimated delivery date may be missing in a small
fraction of rows. Use repeatable `--max-missing-column NAME=SHARE` to override
the global `--max-missing` threshold for individual `--required` fields:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment,buyer,eta \
  --max-missing 0 \
  --max-missing-column eta=0.5 --json
```

Each share is a number from 0 to 1 (inclusive). A named field must appear in
`--required`, and a field can be specified only once. The **last** `=` separates
the field name and its share, so a valid CSV header such as `SLA=met` can use
`--max-missing-column SLA=met=0.5` without losing part of the name. Invalid, duplicate,
unknown, negative, greater-than-one, and non-finite limits fail with exit code
`2`; exceeding an allowed missing rate fails the quality gate with exit
code `1`. Limits not explicitly overridden continue to use `--max-missing`.
JSON includes `max_missing_columns` only when overrides are supplied, so
existing output without the new option is unchanged. Markdown reports the
effective overrides in the summary.

## Concentration among assigned customers and suppliers (opt-in)

When an extract includes many missing customer or supplier labels,
`--max-group-share` uses **all rows** in its denominator and includes the
missing-value bucket among the possible top groups. This remains unchanged.
To evaluate how dependent the *identified* business is on one counterparty,
use `--max-assigned-group-share SHARE` with `--group COLUMN`:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment --max-missing 1 --group buyer \
  --max-assigned-group-share 0.60 --json
```

Only real, non-missing labels contribute to this new numerator and denominator:
for example, with 6 rows assigned to ACME, 2 to another buyer, and 12 missing,
the largest **assigned-group** share is 6/8 = **75%**, whereas
`--max-group-share` observes the missing bucket at 12/20 = **60%**.
The new limit fails the extract at 60% and reports exit `1`, even when the
existing top-group gate passes with the same threshold. If the extract contains
rows but every group is missing, this check **fails closed**; an entirely empty
extract reports 0% and can be rejected separately via `--min-rows 1`.

The gate uses the existing missing placeholders (including `NA`, `N/A`,
`null`, `s/d`), treats a real `(blank)` customer as assigned, respects
`--casefold-group`, and is calculated independently of `--top` (including
`--top 0`). The JSON adds `max_assigned_group_share`,
`top_assigned_group_share`, `assigned_group_rows`, and
`failed_assigned_group_share` **only if the option is enabled**. Markdown
shows the rate and a clear failure reason. Invalid, non-finite, or out-of-range
shares and using the option without `--group` produce configuration exit `2`.
The default outputs, ranking, concentration and missingness gates remain
unchanged; the original CSV is never rewritten.

## Maximum missing-group share (opt-in)

An extract can have many customers or suppliers while still leaving an unsafe
fraction of its records unassigned. Combine `--group COLUMN` with
`--max-missing-group-share SHARE` (from `0` to `1`) to reject extracts whose
missing, whitespace-only or recognized placeholder (`NA`, `N/A`, `null`, `s/d`,
etc.) group labels exceed the specified share of **all data rows**:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --group buyer \
  --max-missing-group-share 0.05 --top 0 --json
```

The gate evaluates every row even when `--top 0` hides the top-group list; a
literal valid group label `(blank)` does not count as missing. Equality with
the threshold passes; exceeding it exits `1`. A negative, greater-than-one or
non-finite limit (including `NaN`) or missing `--group` exits `2`. When enabled,
JSON adds `max_missing_group_share`, `missing_group_rows`, `missing_group_share`
and `failed_missing_group_share`; ordinary JSON output is unchanged.
An extract with zero data rows has a missing-group share of 0; use
`--min-rows N` when an empty extract should also fail. This check works
independently of `--max-group-share` and `--min-distinct-groups`.

## Minimum business-group diversity (opt-in)

A file with 10,000 rows can still contain only one real customer or supplier.
Use `--min-distinct-groups N` together with `--group COLUMN` to require at
least N **distinct, non-missing** group labels, independently of which groups
are displayed with `--top`. Missing-value tokens such as `NA`, `N/A`, `null`,
`s/d`, blanks and whitespace do **not** count as customers or suppliers. A
literal customer named `(blank)` is a real, non-missing label and does count.

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment,buyer --group buyer \
  --min-distinct-groups 2 --top 0 --json
```

The new option exits `1` when fewer distinct valid groups are present, or `2`
when its value is negative or `--group` is missing. Zero is allowed. JSON adds
`min_distinct_groups`, `distinct_groups`, and `failed_distinct_groups` **only**
when this gate is enabled; existing reports without the option are unchanged.
The concentration limit `--max-group-share` still counts the missing-value
bucket in its numerator where appropriate, so both rules can be used together.

## Maximum business-group cardinality (opt-in)

An export can unexpectedly introduce thousands of distinct supplier or
customer identifiers because of an incorrect join, a transaction ID accidentally
used as the group field, or unstable naming conventions. Pair
`--max-distinct-groups N` with `--group COLUMN` to reject an extract
that contains **more than N distinct, non-missing labels**:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --group buyer \
  --max-distinct-groups 100 --json
```

Missing values (`NA`, `N/A`, blank, `null`, `s/d`, etc.) do not
contribute to the count; a real group literally named `(blank)` does count.
The same normalization as `--min-distinct-groups` is used, including
optional Unicode `--casefold-group`. The count is independent of `--top`,
including `--top 0`, and can be checked alongside the minimum-diversity gate.

Equality with the limit passes; exceeding it returns quality-gate exit `1`.
Negative limits or omitting `--group` yield configuration exit `2`.
When both diversity bounds are enabled, `--min-distinct-groups` must be
less than or equal to `--max-distinct-groups`. An impossible pair, such as
`--min-distinct-groups 5 --max-distinct-groups 2`, is a configuration error
(exit `2`, without a JSON/Markdown report) rather than a failed CSV quality
check. Equal bounds and zero are valid. The rule is enforced by the Python API
and CLI before any row-count results are reported.
Zero is allowed, so a header-only export passes this upper-bound check
unless another gate (such as `--min-rows 1`) rejects it. JSON only adds
`max_distinct_groups`, `distinct_groups`, and
`failed_max_distinct_groups` when enabled, leaving the old output intact.
Markdown includes the configured maximum and the failure reason.

## Maximum data-row count (opt-in)

A nightly order, shipment, or inventory export can accidentally include a full
history instead of the requested day because of a missing date filter or a bad
join. Use `--max-rows N` to reject extracts with **more than N data rows**,
independently of completeness, repeated-key, and group-concentration checks:

```bash
python -m ops_field_brief examples/shipments.csv \
  --required shipment --min-rows 1 --max-rows 1000 --json
```

The upper bound is inclusive: exactly 1,000 rows passes; 1,001 fails with
quality-gate exit `1`. `--max-rows 0` accepts header-only exports and rejects
any data rows. A blank physical CSV line is not a data row. As with the existing
`--min-rows` gate, this checks the total number of rows independently of the
`--top` display limit and any group/key selection.

Negative maximums or mutually inconsistent bounds such as `--min-rows 10
--max-rows 5` are invalid configuration (exit `2`) and **do not produce a
misleading report**. JSON adds `max_rows` and `failed_max_rows` only when
enabled; Markdown includes the maximum and an explicit failure section when
it is exceeded. Previous JSON/Markdown output stays unchanged by default.

## Install and run

Python 3.10 or newer. No third-party packages. From a checkout:

```bash
python -m ops_field_brief shipments.csv \
  --required shipment,buyer,eta \
  --key shipment \
  --group buyer
```

After `pip install .`, the same command is available as `ops-field-brief`. Use `ops-field-brief --version` to confirm the installed version.

Exit code `0` means every enabled quality gate passes. Exit code `1` means at least one required field is too empty, repeated keys exceed `--max-duplicates`, incomplete key rows exceed `--max-incomplete-keys`, the data-row count is below `--min-rows` or above `--max-rows`, or the largest `--group` exceeds `--max-group-share`, or the count of real distinct groups falls below `--min-distinct-groups` or exceeds `--max-distinct-groups`, or missing group assignments exceed `--max-missing-group-share`. Exit code `2` means the file or the arguments could not be used, including an unknown `--encoding`, a `--max-missing` or `--max-group-share` outside 0 to 1 (including non-finite values such as `NaN`), a negative `--max-duplicates`, `--min-rows` or `--max-rows`, or a `--min-rows` greater than `--max-rows`, an empty, incomplete or repeated `--required` field list, an unknown `--key` or `--group`, using `--max-group-share`, `--max-missing-group-share`, `--min-distinct-groups` or `--max-distinct-groups` without `--group`, a negative `--min-distinct-groups` or `--max-distinct-groups`, a negative `--top`, or an unknown `--delimiter`.

`--required` trims surrounding spaces but rejects missing field positions such as `shipment,,eta`, leading/trailing commas or whitespace-only segments (exit `2`), rather than silently skipping a quality check. Duplicate field names also produce a configuration error.

Duplicate columns in a composite `--key` (for example `order_id,order_id`) are rejected with exit `2`, instead of presenting repeated copies as separate components of the business key. Valid multi-column identifiers remain unchanged.

`--json` writes the same brief as JSON. `--key` accepts one field or a comma-separated composite business key such as `order_id,line_id`; empty slots such as `order_id,,line_id`, leading commas or trailing commas are invalid configuration (exit `2`) rather than silently omitting a column; duplicate rows are counted only when the complete key repeats, and rows with a blank key component are ignored for duplicate counting. `--delimiter` accepts `comma` (default), `semicolon`, `tab`, `pipe`, or `auto`. The default keeps the original comma behavior. `auto` detects those four common separators from the input; a valid single-column CSV is accepted when every nonempty sampled CSV record has exactly one field for all four candidate separators; physically blank lines are ignored, just as the Python CSV reader ignores them. The fallback uses comma because no separator is needed. If the first 8,192-character detection sample is incomplete (for example, a long quoted CSV field), auto detection retries with the complete input before giving up; malformed quoting remains rejected. Truly ambiguous or inconsistent samples still exit `2` with a clear message. An unknown delimiter exits `2`.

`--encoding` defaults to `utf-8`. A UTF-8 BOM, common in Excel exports, is stripped so the first column name stays usable, including on stdin. For a Windows Excel export in Spanish, pass `--encoding cp1252` or `--encoding latin-1`.

CSV-derived labels in Markdown reports (field names, business keys and group values) are escaped so embedded pipes, Markdown links, line breaks and invisible terminal-control characters cannot create fake table columns, headings or deceptive job-summary source. ASCII C0 controls (including NUL, tabs, CR, LF, ANSI ESC and backspace), DEL and C1 controls are represented as numeric character references such as `&#27;`. JSON output and the original CSV retain every value unchanged; regular Unicode labels and report formatting are preserved.

To see the protection, run `PYTHONPATH=src python -m ops_field_brief examples/markdown-safety.csv --required shipment --group buyer`. The synthetic example includes a Markdown-style link, a quoted line break and a pipe in one group label.

Blank `--group` values and missing-value tokens (`NA`, `N/A`, `null`, `s/d`, etc.) share the `(blank)` bucket. A literal group value equal to `(blank)` stays separate from missing entries; only when both appear, the missing bucket is labeled `(blank) [missing]` (or numbered if that name also exists in the input). This bucket counts toward `--max-group-share`, including with `--top 0`; the original input CSV is not modified. A blank `--key` is not counted as a repeat. Repeated keys are counted as extra rows: three identical keys count as two, and two different keys each repeated once also count as two. Composite keys use the complete tuple of fields, so `order_id=O1,line_id=1` and `order_id=O1,line_id=2` are distinct keys. Top groups are limited to five. `--top` can lower that limit. `--top 0` reports no groups. A negative `--top` exits `2`. `--max-duplicates` limits the allowable extra rows from a repeated business key; if exceeded, the command exits `1` with a failed duplicate check. A negative `--max-duplicates` exits `2`. Supplying `--max-duplicates` without `--key` also exits `2`, rather than claiming that an unevaluated duplicate-key check passed. A quoted field that contains a comma stays one field. An escaped quote stays in the field. A multiline quoted field stays one row. A trailing comma does not break the row. A field that is only whitespace counts as missing. A field that is only a tab also counts as missing. A duplicate column name in the header uses the last value. A header-only file and an empty file report `0` rows and exit `0` by default; use `--min-rows N` when zero or undersized extracts should fail the quality gate. A path of `-` reads the CSV from stdin. `--help` exits `0` and lists the arguments.

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

When `--json` is used, including argparse's accepted unique abbreviations (`--j`, `--js`, `--jso`), the Action encloses JSON in a GitHub job-summary Markdown code fence whose length is longer than any backtick run in the JSON. This prevents untrusted CSV labels containing backticks from being interpreted as Markdown fence delimiters; JSON bytes and the normal three-backtick layout for ordinary reports remain unchanged.

The Action rejects informational CLI flags (`-h`, `--help`, `--version`, and accepted long-option abbreviations) with `exit-code=2` and `passed=false`. Without this protection, an informational command would exit successfully **without checking any CSV**, falsely satisfying a pipeline gate. To display help or a version, invoke the standalone CLI instead.

For safety, the Action `path` must name a CSV **inside the caller's `GITHUB_WORKSPACE`**. Absolute paths, `../` paths that leave the workspace, symlinks that resolve outside it, and stdin (`-`) are rejected before the CLI runs (exit code `2`, `passed=false`). Ordinary nested relative paths, including paths through symlinks that remain inside the workspace, are supported. This boundary protects against unintended reads outside the job checkout; it does not make untrusted CSV content safe to publish in logs or job summaries.

The reusable Action rejects **actual newline, carriage-return, NUL and terminal-control characters** (including ANSI ESC, bell, backspace, DEL and Unicode C1 controls) in its `path` and `args` inputs before invoking Python's CSV analyzer. Tabs are rejected in `path` filenames but remain supported as normal argument separators in `args`. This avoids malformed multiline inputs, forged log lines and control sequences that could manipulate job-log rendering. It returns exit `2` with `passed=false` without launching the analyzer. Normal relative Unicode paths, space- or tab-separated arguments and standalone CLI behavior remain unchanged.

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

The suite covers fill counts, repeated keys, three identical keys, two repeated keys, blank keys, `--max-duplicates` allowing repeated keys within limits and failing when exceeded, a negative `--max-duplicates`, missing tokens including `N/D` and `s.d.`, unknown columns, an unknown key and an unknown group, a passing CLI run, semicolon, tab and pipe exports, an unknown delimiter, a cp1252 file, a UTF-8 BOM, a UTF-8 BOM on stdin, an unknown encoding, an empty required list, `--json`, blank groups, a five-group limit, `--top`, `--top 0`, a negative `--top`, a quoted field with a comma, an escaped quote, a multiline quoted field, a trailing comma, a whitespace-only field, a tab-only field, a duplicate header, a header-only file, an empty file, stdin, `--help`, `--max-missing` allowing a share of blanks, and `--max-missing` outside 0 to 1, `--min-rows` passing/failing row-count gates, JSON gate metadata, and a negative `--min-rows`. Strict CSV validation is covered for duplicate or blank headers and ragged rows. 106 tests. It uses the standard library only. The installed package ships a PEP 561 `py.typed` marker so downstream type checkers can consume its inline annotations. CI runs the suite on Python 3.10 through 3.13 on Ubuntu, plus Python 3.10 and 3.13 on Windows and macOS.

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
