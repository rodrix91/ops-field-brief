# Changelog

## Unreleased

- Add a checked-in synthetic `sep=;` Excel operations fixture with a runnable, documented auto-delimiter and quality-gate command. Guard its exact header, required-field accounting and JSON CLI behavior with cross-platform regressions. Preserve all existing CSV examples and parsing semantics.

- Display CSV-sourced soft hyphens (U+00AD), zero-width spaces (U+200B), word joiners (U+2060), and byte-order marks embedded in labels (U+FEFF) as visible, inert `[U+XXXX]` markers in Markdown and GitHub Action summaries. Prevent visually identical but distinct group/key labels from being hidden in presentation while preserving original Unicode JSON values, ordinary letters, and joiners used by writing systems. Add API and real CLI regression tests.

- With `--delimiter auto`, recognize an exact Excel `sep=;`, `sep=,`, `sep=|`, or tab separator directive on the first text line and skip it before interpreting the actual CSV header. Support local and gzip exports, stdin, BOM and CRLF; preserve explicitly selected delimiter behavior, reject ambiguous lookalikes, and keep strict CSV and JSON gate semantics. Add reader and CLI regressions.

- Render Unicode line and paragraph separators (U+2028/U+2029) in untrusted CSV fields and group labels as inert ASCII markers in Markdown and Action summaries, preventing invisible visual line breaks while keeping JSON values unchanged. Add library and CLI regressions.

- Render Unicode bidirectional formatting controls from untrusted CSV labels and group values as visible ASCII [U+XXXX] markers in Markdown and GitHub job summaries. Unlike HTML numeric references, these cannot be decoded back into direction-changing characters by a Markdown renderer. Keep original JSON values, ordinary multilingual text and existing C0/C1 escaping unchanged; add direct and CLI regression tests.

- Read `.gz` operational CSV exports directly using Python's standard-library streaming gzip reader, preserving delimiter autodetection, strict CSV checks, BOM stripping, explicit encodings and existing gate semantics. Invalid/truncated gzip data fails with input exit `2` rather than a traceback; stdin remains plain text. Add gzip, malformed archive and CLI regression coverage without changing uncompressed reports or adding runtime dependencies.

- Harden reusable GitHub Action JSON report validation against forged or missing base quality-gate flags and contradictory duplicate/incomplete business-key counters. Only documented failed_* outcomes count toward the CI status; optional genuine gates remain supported. Add negative and multi-gate regression tests without changing the CLI JSON schema.

- Reconcile every Markdown required-field missing percentage against the measured missing/total rows to the rendered one-decimal precision in the reusable Action. Reject inconsistent ratios, duplicate/blank field labels, malformed numeric cells and false-green reports without affecting the original CLI report or JSON schema. Add regression tests including zero-row and escaped-label examples.

- Validate the reusable GitHub Action's Markdown output structurally, not merely for nonempty text: require an operational heading, row count, measured required-field table, and failure sections consistent with the CLI exit code. This blocks reportless false successes while preserving genuine Markdown/JSON reports and the standalone CLI. Extend regression tests to normal, failing, empty-data and truncated reports.

- Strengthen the reusable Action JSON integrity gate by reconciling each field's missing-rate display against its actual missing count and total rows, rejecting NaN/Infinity, duplicate field identities and unknown or repeated failure labels. Preserve the standalone CLI's schema and exit codes; add negative and empty-export regressions.

- Validate the reusable GitHub Action's JSON output against the operational report contract: nonnegative row counts, populated field metrics with reconciled filled/missing totals, and reported quality-gate flags that agree with exit `0` or `1`. Malformed, incomplete or contradictory reports now fail closed with exit `3` and `passed=false` rather than exposing misleading summaries; the standalone CLI, JSON schema and existing functionality remain unchanged. Add focused negative and compatibility regressions.

- Add opt-in `--max-distinct-keys N`, a maximum-cardinality quality gate on **unique complete** single/composite business keys, independent of row-count, completeness, and duplicate gates. Exclude known missing-value tokens, respect optional Unicode `--casefold-key`, validate nonnegative bounds and `--key`, and reject conflicting minimum/maximum ranges. Preserve the default JSON/Markdown layouts and prior gates; include API, CLI, Unicode, empty-export, configuration, and reusable Action regressions.

- Fail closed in the reusable GitHub Action if the analyzer returns exit `0` or `1` without a nonempty report, or returns malformed/non-object JSON when `--json` (including argparse abbreviations) is requested. Reportless false successes now produce error exit `3`, `passed=false` and no new job summary; genuine analysis/configuration failure exit codes remain unchanged. Add direct and runner-level regressions for missing output, invalid JSON and valid Markdown/JSON including failed quality gates. The standalone CLI and output schema are unchanged.

- Add opt-in `--min-distinct-keys N` as an independent minimum-cardinality gate for **unique complete** single or composite business keys. Unlike `--min-complete-keys`, repeated valid IDs count once; incomplete keys are excluded, and `--casefold-key` controls Unicode case-insensitive matching when selected. Enforce nonnegative bounds and `--key` configuration (exit `2`), quality failures (exit `1`), JSON/Markdown output only when enabled, and preserve the historical default report and all existing gates. Include API, CLI, Unicode, empty-data and combined-gate regressions.

- Ensure the reusable Action recognizes argparse's accepted `--json` abbreviations (`--j`, `--js`, `--jso`) when deciding how to fence GitHub job summaries. Previously, abbreviated JSON mode bypassed the defensive Markdown code fence even though the CLI accepted and emitted JSON. Keep ordinary Markdown summaries, the original CLI flags, payload bytes and prior output behavior unchanged; add direct and end-to-end regression tests covering untrusted backtick-bearing labels.

- Reject every Unicode C1 terminal control (U+0080–U+009F) in the reusable GitHub Action `path` and `args` and reject literal tabs in `path`, which is passed as one filename rather than as shell tokens. Keep tabs valid as separators in `args`, retain ordinary Unicode filenames and prior CR/LF/NUL error semantics, and fail with exit `2` / `passed=false` before spawning the CLI. Add direct full-C1-range and end-to-end Action regression coverage. Standalone CLI and source CSV content remain unchanged.

- Add optional `--casefold-headers` alongside `--strict-csv` to reject ambiguous Unicode case-equivalent CSV headers (e.g., `id`/`ID`, `Straße`/`STRASSE`, or Greek sigma forms), while keeping original names and existing case-sensitive validation unchanged unless selected. Reject the option without strict mode before input access (exit 2); add direct API, Unicode, CLI and default-compatibility regressions. No changes to reports, other gates or dependencies.

- Add opt-in `--min-complete-keys N` for the minimum number of usable business-key rows, including composite identifiers. Missing tokens exclude a row, duplicates remain countable, and this gate is independent of total-row and duplicate gates. Reject negative limits and missing `--key` as configuration errors, preserve existing output when disabled, and report failing thresholds in Markdown/JSON with dedicated regression coverage.

- Escape all untrusted CSV C0, DEL and C1 control characters as numeric references in Markdown reports and GitHub job-summary source, preventing invisible ANSI/terminal controls or tabs from altering text presentation. Preserve the original CSV/JSON bytes, ordinary Unicode labels and previous Markdown escaping; cover every control code, field names, business keys, group labels and a real CLI CSV fixture.

- Reject additional terminal control characters (ANSI ESC, bell, backspace, DEL and other ASCII controls) in untrusted GitHub Action `path` / `args` inputs to prevent deceptive log rendering. Keep the existing LF/CR/NUL error contract, horizontal-tab argument separators, Unicode paths and fail-closed exit `2` / `passed=false` behavior. Add direct guard and end-to-end no-subprocess regressions.

- Harden the composite Action's JSON job summary against backtick sequences in untrusted CSV fields by choosing a Markdown code fence longer than any sequence in the payload. Preserve the raw JSON output, ordinary triple-fence summaries, Markdown reports and Action outputs; add summary-rendering regression tests.

- Reject impossible combined `--min-distinct-groups` and `--max-distinct-groups` settings when the minimum exceeds the maximum; return configuration error `2` without a misleading report. Keep each independent gate, equal bounds, zero-count exports and default reports unchanged. Add direct API, CLI and regression tests.

- Harden reusable GitHub Action inputs: reject newline, carriage-return and NUL characters in the CSV path or additional args before any CLI subprocess starts, recording exit code `2` and `passed=false`. Preserve valid relative paths, regular flags, existing workspace traversal/symlink checks and standalone CLI behavior. Add direct and workflow-runner regression tests.

- Add opt-in `--max-rows N` quality gate for unexpectedly oversized CSV exports, complementing `--min-rows` and preserving all existing count, key, group, and field checks. Reject negative and inconsistent row-count limits as configuration errors, report failure via exit `1`, preserve JSON/Markdown schemas unless enabled, and add API/CLI boundary and empty-file regressions.

- Add optional `--max-incomplete-key-share SHARE` to cap the fraction of CSV rows with missing single/composite business-key components, independently of absolute incomplete-key and duplicate gates. Preserve historical JSON/Markdown unless enabled, accept inclusive 0–1 finite limits, reject missing keys or invalid thresholds with exit 2, and cover library, CLI, empty-file, all-incomplete and integration scenarios.

- Add opt-in `--max-duplicate-share SHARE` to cap extra repeated business-key rows as a fraction of complete-key rows, rather than only by an absolute count. Exclude missing key components from both numerator and denominator, fail closed on nonempty exports with no complete keys, support composite keys and Unicode casefold, and retain independent duplicate-count/incomplete-key gates. Only append JSON/Markdown metadata when enabled; cover CLI, library, valid/invalid shares and zero-row regressions.

- Add opt-in `--max-distinct-groups N` with `--group` to reject unexpectedly high numbers of distinct real customers or suppliers. Exclude missing-label placeholders, support Unicode group casefold and `--top 0`, and preserve independent minimum-diversity checks. Report failure via exit `1`, reject invalid configurations with exit `2`, and keep JSON/Markdown unchanged unless enabled. Add library and CLI regressions alongside explicit tests preserving legacy headerless-input behavior.

- Add opt-in `--max-assigned-group-share SHARE` (requires `--group`) to detect concentration among identified customers/suppliers even when missing counterparty labels dilute overall shares. Exclude only recognized missing-group rows from this new denominator, fail closed when nonempty extracts have no assigned groups, retain empty-extract `--min-rows` semantics, support Unicode casefold and `--top 0`, and preserve all previous concentration/JSON defaults. Validate thresholds and cover API/CLI/Markdown/JSON regressions.

- Add opt-in `--casefold-group` (requires `--group`) to normalize real customer/supplier group labels using Unicode casefold before counting, ranking and applying concentration/diversity gates. This prevents capitalization variants from artificially inflating distinct groups or hiding top-group share, while keeping missing placeholders and legitimate `(blank)` labels separate. Default behavior and JSON stay unchanged; add API/CLI/Unicode/composition regression tests.

- Add opt-in `--casefold-key` (requires `--key`) for Unicode case-insensitive duplicate detection in single/composite business identifiers. Normalize only valid, non-missing values after whitespace trimming, preserve the default case-sensitive behavior and old JSON when disabled, and test missing-key handling, CLI failures, and Unicode equivalence.

- Add opt-in `--max-missing-group-share SHARE` (requires `--group`) to fail operational extracts with too many missing or placeholder group assignments, independent of `--top` and distinct-group/concentration gates. Exclude legitimate literal `(blank)` labels from missing counts; reject non-finite/out-of-range thresholds, preserve legacy output unless enabled, and cover direct/CLI/JSON/Markdown regressions.

- Add opt-in `--min-distinct-groups N` with `--group` for operational customer/supplier diversity checks. Count only non-missing distinct group labels, independent of `--top`; reject negative limits and missing `--group`. Preserve legacy JSON unless enabled and cover CLI, library, empty extracts, and missing-token cases with regressions.

- Parse `--max-missing-column NAME=SHARE` at the **last** `=` to support exact required-field names containing an equals sign (e.g. `SLA=met=0.5`), without relaxing invalid-share or unknown-field checks. Add an end-to-end quality-gate and JSON regression.

- Add repeatable `--max-missing-column NAME=SHARE` to override required-field completeness thresholds without relaxing the global `--max-missing` gate. Reject malformed, duplicate, unknown, non-finite, and out-of-range overrides with usage exit 2; include override metadata only when requested to preserve existing JSON contracts. Add API, CLI, Markdown and JSON regression tests.

- Require an explicit `--key` whenever `--max-duplicates` is set. Previously a duplicate quality gate without a key silently returned success, even when the CSV contained duplicate orders. Fail with usage exit 2 and no misleading report; retain valid single/composite-key behavior. Add library and CLI regressions.

- Retry `--delimiter auto` detection with the complete CSV if the first 8,192-character sample cannot be classified, including long quoted single-column or multi-column fields crossing the sample boundary. Preserve strict CSV errors for truly unterminated quotes. Add stdin, local-file and CLI regressions.

- Preserve `--delimiter auto` for one-column exports containing blank physical lines: ignore CSV reader's empty records during delimiter fallback without relaxing validation of malformed quoting, missing headers or mixed-width rows. New strict-CSV CLI and library regressions ensure only actual data rows are counted.

- Allow valid single-column CSV exports with `--delimiter auto` even though no separator is detectable. Verify all sampled records have one field under all four candidate delimiters, respecting quoted embedded commas and pipes; continue rejecting ambiguous, ragged and malformed quoted input. Cover local-file, standard-input and strict-mode regressions.

- Keep a real CSV group value named `(blank)` separate from missing-value buckets when computing `--max-group-share`, preventing false concentration failures. Preserve existing `(blank)` output for ordinary missing groups and disambiguate its display name only when a real group uses that label. Add direct/CLI regressions, including collision-safe labeling.

- Reject repeated field names in composite `--key` settings, rather than reporting the same source column as multiple key components. Library and CLI regressions cover duplicate names, valid composite keys and unaffected duplicate-row counting.

- Reject empty field positions in comma-separated `--required` arguments (including leading/trailing commas and whitespace-only components) instead of silently dropping the corresponding quality checks. Valid whitespace-trimmed field names remain supported, with CLI regression coverage.

- Reject blank segments in comma-separated `--key` CLI arguments (e.g. `order_id,,line_id` or a trailing comma) with exit `2`, rather than silently dropping a requested component and evaluating a different business key. Preserve valid single/composite key behavior and the all-blank argument error; added regressions and reusable Action end-to-end checks.

- Normalize blank and missing-token (`NA`, `N/A`, `null`, `s/d`, etc.) group labels into one `(blank)` bucket before ranking groups or evaluating `--max-group-share`. This closes a false-green concentration-gate scenario when one missing group is split across placeholder spellings. Added direct and CLI regressions and synchronized the operations documentation with the existing missing business-key behavior.

- Business-key completeness now applies the same missing-value token rules as required-field checks: `NA`, `N/A`, `null`, `s/d` and similar placeholders count as incomplete key cells, rather than being counted as valid identifiers or duplicate business keys. Added single-key, composite-key and CLI regression tests.

- Escaped CSV-derived field names, business keys and group values in Markdown output and GitHub Action summaries. Pipes and Markdown syntax no longer distort tables or create misleading links/headings; embedded CR/LF cannot add Markdown source lines. JSON values and quality-gate calculations remain unchanged, with regression tests covering single-line and multiline CSV content.

- Corrected a fail-open validation edge case: `--max-missing NaN` previously passed the 0-to-1 range checks and could suppress required-field completeness failures. Non-finite thresholds now exit 2 with a clear error, consistent with existing `--max-group-share` validation. Added library, CLI and regression coverage.

- The regression suite now has 90 tests with 100% line and branch coverage.

- Added optional `--max-incomplete-keys N` with `--key` to count and gate CSV rows with an empty component in a single or composite business key. Reports expose `incomplete_key_rows`, the configured limit, and the failed-gate flag; duplicate counting remains unchanged. Added a reproducible sample, CLI tests, and GitHub Action end-to-end checks.

- Prevented false-green reusable Action runs when `args` contains `-h`, `--help`, `--version` or argparse-accepted abbreviated spellings: the Action now fails closed with `exit-code=2` and `passed=false`, before running the CLI. Added regression and Action end-to-end checks; standalone CLI help/version remain unchanged.

- Added an operations playbook under `docs/README.md` covering quality gates, CI integration, outcomes and privacy safeguards; the repository Documentation URL now resolves to a real page, and CI verifies the page is included in source distributions. README now reflects 83 tests.

- The reusable GitHub Action now validates the input CSV path against `GITHUB_WORKSPACE` before launching the CLI: absolute paths, parent traversal, symlink escapes, and stdin (`-`) are rejected with the existing exit-code/passed outputs. Added unit and end-to-end CI regression checks; normal relative paths remain supported.

- Added a reusable composite GitHub Action with safe argument handling, optional job-summary output, `exit-code`/`passed` outputs, and end-to-end CI coverage for passing and failed operational quality gates.

- Added focused edge-case regression tests for stdin, BOM handling, API validation, Markdown group-concentration output, and strict header metadata; the suite now has 76 tests and CI enforces 100% line and branch coverage.

- The installed package now ships a PEP 561 `py.typed` marker; CI verifies the marker in both the source distribution and a clean wheel installation.

- Added `CITATION.cff`; the source distribution now includes it, CI verifies its presence, and package metadata links directly to citation guidance.

- Added opt-in `--strict-csv` structural validation: reject blank/duplicate header names and ragged data rows before calculating operational quality metrics. The default CSV behavior remains backward compatible; file and stdin regression tests cover both modes.

- Source distributions now explicitly include `CONTRIBUTING.md`, and CI builds the sdist to verify both `SECURITY.md` and `CONTRIBUTING.md` are present.

- README now documents how to verify release SHA-256 checksums and GitHub provenance attestations, while noting that historical releases may predate those guarantees.

- Release builds now generate GitHub artifact provenance attestations for the wheel and source distribution, signed through GitHub OIDC/Sigstore and pinned to `actions/attest` v4.2.2 by commit SHA.

- GitHub Actions checkouts now disable persisted Git credentials because CI, release, and scheduled audit jobs do not push repository changes.

- Release checksum entries now use artifact basenames rather than `dist/`-prefixed paths, so `sha256sum -c SHA256SUMS` works directly in a download directory.

- Release artifacts now include a `SHA256SUMS` file so downloaded wheels and source distributions can be independently verified.

- The release job now has an explicit timeout so a stuck build, install, or release test cannot occupy a runner indefinitely.

- CI jobs now have explicit conservative timeouts so a hung test or platform runner cannot consume GitHub Actions indefinitely.

- The scheduled engineering audit now runs weekly on Mondays instead of daily, reducing redundant CI usage while preserving manual `workflow_dispatch`; naming was updated to describe the read-only audit accurately.

- The distribution metadata now links directly to the project documentation alongside the changelog, issues, contribution guide, and security page.

- Security documentation now distinguishes the local-only runtime CLI from the optional maintenance script, whose external Gemini assessment requires both `--allow-external-api` and `GEMINI_API_KEY`; the agent docstring now states the same safe-default behavior.

- Package metadata now describes the current operational checks more accurately and exposes project status, intended audience, and the repository security page in built distributions.

- The release workflow now installs the explicitly pinned `build==1.6.1`, matching the declared development dependency so release builds do not depend on whatever `build` version happens to be latest at publish time.

- `--max-group-share SHARE` adds an opt-in concentration gate for `--group`: the command exits `1` when the largest group exceeds the allowed share of rows. Markdown and JSON report the observed share when enabled, while existing commands and default JSON remain unchanged.

- The autonomous maintenance script now requires both `--allow-external-api` and `GEMINI_API_KEY` before any external API call; an API key alone stays local-only. Three regression tests enforce both safe-default paths and the explicitly enabled mocked path.

- CI now has a dedicated quality gate with branch coverage (minimum 90%), Ruff lint/format checks, and mypy type checking. Development tools are pinned separately and do not become runtime dependencies.

- The build backend is pinned to `setuptools==84.2.1` for reproducible isolated builds, and Dependabot now tracks Python build dependencies weekly in addition to GitHub Actions.

- GitHub Actions are pinned to the verified commit SHAs behind `actions/checkout@v7` and `actions/setup-python@v7`, while version comments keep Dependabot updates readable.

- `--min-rows N` adds an opt-in row-count quality gate: the command exits `1` when the CSV contains fewer than N data rows. Markdown reports the minimum and failure; JSON adds `min_rows` and `failed_rows` only when the gate is requested, preserving default JSON output.

- `--key` now accepts comma-separated composite business keys such as `order_id,line_id`; duplicate counting uses the complete key and ignores rows with a blank key component. JSON output adds `key_fields` while preserving the existing `key` field.

- Header-only CSV files now retain their parsed column names for `--key` and `--group` validation, so valid fields do not become false `unknown columns` errors when there are zero data rows.

- CI now runs PR validation once through the `pull_request` event, limits push validation to `main`, cancels superseded runs, and declares read-only repository permissions.

- Stdin is now decoded with the explicit `--encoding` instead of the host locale, fixing UTF-8 BOM and cp1252 input on Windows.

- CI now runs the full unit-test suite on Windows and macOS at the oldest and newest supported Python versions, in addition to the existing Ubuntu matrix.

## 0.3.0 - 2026-10-23

- `--version` prints the installed `ops-field-brief` version and exits successfully.
- Package metadata now reads the version from `ops_field_brief.__version__`, removing duplicated version declarations.
- CI now smoke-tests the built wheel in a clean environment and validates installed metadata against the runtime package version.
- A tag-driven release workflow validates version tags, builds and tests wheel and source distributions, and publishes only GitHub release artifacts. It does not publish to PyPI.
- The version CLI regression test derives its expected value from the package version, so future release bumps do not require a hard-coded test edit.

## 0.2.0

- `--delimiter auto` detects comma, semicolon, tab, or pipe for files and stdin; ambiguous input exits `2` with guidance to choose a delimiter explicitly.

## 0.1.0

- Operational brief: fill rate, repeated business keys, and top groups.
- `--delimiter` accepts `comma` (default), `semicolon`, `tab`, and `pipe`. Comma stays the default. An unknown delimiter exits `2`.
- `--encoding` accepts a Python codec. Default is `utf-8`. Use `cp1252` or `latin-1` for Windows Excel exports.
- A UTF-8 BOM, common in Excel exports, is stripped so the first column name stays usable, including on stdin.
- An unknown encoding exits `2` and names the codec.
- `--max-missing` can allow a share of blanks. The default remains `0`. A value outside 0 to 1 exits `2`.
- `--max-duplicates` sets a quality gate on repeated business keys: fails with exit code `1` if extra rows from a repeated key exceed the threshold. A negative value exits `2`.
- An empty `--required` list exits `2`.
- An unknown `--key` or `--group` exits `2` and names the column.
- A blank group value is reported as `(blank)`. A blank key is not counted as a repeat.
- A header-only file and an empty file report `0` rows and exit `0`.
- `--json` writes the same brief as JSON.
- Missing tokens include empty cells, `NA`, `N/A`, `null`, `none`, `s/d`, `s.d.`, `N/D`, `N.D.`, and `-`.
- Top groups are limited to five. `--top` can lower that limit. `--top 0` reports no groups. A negative `--top` exits `2`.
- A path of `-` reads the CSV from stdin.
- Repeated keys are counted as extra rows. Three identical keys count as two extra rows. Two different keys, each repeated once, also count as two.
- A quoted field that contains a comma stays one field. An escaped quote stays in the field. A multiline quoted field stays one row.
- A trailing comma does not break the row.
- A field that is only whitespace counts as missing. A field that is only a tab also counts as missing.
- A duplicate column name in the header uses the last value, following the standard library CSV reader.
- `--help` exits `0` and lists the arguments.
- Exit codes: `0` within the fill and duplicate limits, `1` fill check or duplicate check failed, `2` file or arguments could not be used.
- CI uses `actions/checkout@v7` and `actions/setup-python@v7` on Python 3.10 through 3.13.
- Autonomous daily engineering cycle workflow in GitHub Actions (`.github/workflows/autonomous-daily.yml`) running daily at 09:00 (13:00 UTC) with `scripts/autonomous_agent.py`.
- `SECURITY.md` explains how to report a problem in the local CLI.
- `CONTRIBUTING.md` explains the setup, the test command, and the guidelines.
- `pyproject.toml` declares Homepage, Changelog, Issues, and Contributing. `MANIFEST.in` includes the license, examples, tests, and scripts.
- Bug and feature request forms ask for the command or the problem, and the expected result. Blank issues are disabled.
- A pull request template asks for the summary and the local test check.
