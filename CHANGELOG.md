# Changelog

## Unreleased

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
