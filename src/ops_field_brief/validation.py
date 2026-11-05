"""Opt-in CSV structure checks before operational metrics are calculated."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from unicodedata import normalize


def _diagnostic_header(name: str) -> str:
    """Bound untrusted duplicate-header labels without changing comparisons."""
    fragment = name[:80]
    # Embedded newlines, terminal escapes and bidi controls must not format
    # themselves as active characters inside CLI or GitHub Actions logs.
    displayed = fragment if fragment.isprintable() else repr(fragment)
    truncated = len(name) > 80
    # Escape sequences can expand substantially under repr().
    if len(displayed) > 120:
        displayed = displayed[:117] + "..."
        truncated = True
    return displayed + (" [truncated]" if truncated else "")


def validate_csv_structure(rows: list[dict[str, str]], *, casefold_headers: bool = False) -> None:
    """Reject ambiguous headers and ragged rows without changing default parsing.

    The normal reader preserves header names on CsvRows, including header-only
    files. Set casefold_headers to also reject Unicode case-equivalent labels,
    without renaming input columns or changing the default strict behavior.
    DictReader maps surplus fields under a None key and missing fields
    to None values. Caller-constructed records may also contain arbitrary
    undeclared keys, which strict validation must reject explicitly.
    """
    # Direct library calls must not treat "false", 1 or other truthy values
    # as an opt-in for case-insensitive header checks.
    if not isinstance(casefold_headers, bool):
        raise ValueError("casefold_headers must be a boolean")
    header = getattr(rows, "fieldnames", None)
    if header is None:
        raise ValueError("strict CSV validation requires a parsed header")
    if not header:
        raise ValueError("CSV has no header row")

    for position, name in enumerate(header, 1):
        # The public validator also accepts caller-constructed CsvRows. Fail
        # with a configuration error instead of an AttributeError when their
        # header metadata contains a non-string value.
        if not isinstance(name, str):
            raise ValueError(f"CSV header at column {position} must be a string")
        if not name or not name.strip():
            raise ValueError(f"blank CSV header at column {position}")

    names = [name.strip() for name in header]
    # With the opt-in flag, compare both case-insensitively and under Unicode
    # canonical equivalence (NFC). Keep original column names untouched so
    # --required, --key and --group continue to match exactly.
    compared = [normalize("NFC", name.casefold()) if casefold_headers else name for name in names]
    repeated = [name for name, count in Counter(compared).items() if count > 1]
    if repeated:
        # Report a bounded number of bounded labels. A CSV may contain many
        # distinct duplicated columns or very large/control-bearing names.
        displayed = ", ".join(_diagnostic_header(name) for name in repeated[:3])
        rest = f" (+{len(repeated) - 3} more)" if len(repeated) > 3 else ""
        raise ValueError("duplicate CSV header columns: " + displayed + rest)
    # Use the exact source header spelling, not its normalized comparison
    # form: strict parsing must not silently rewrite column identifiers.
    declared_fields = set(header)

    source_lines = getattr(rows, "source_lines", ())
    # CsvRows carries an optional physical line for *every* parsed record.
    # Caller-built instances may be mutated after construction. Reject
    # inconsistent metadata before indexing so a strict validation failure
    # never crashes with IndexError or reports a fabricated source line.
    if (
        not isinstance(source_lines, (tuple, list))
        or (source_lines and len(source_lines) != len(rows))
        or any(type(line) is not int or line < 1 for line in source_lines)
        or any(left >= right for left, right in zip(source_lines, source_lines[1:], strict=False))
    ):
        raise ValueError("CSV source line metadata must be positive, ordered, and match data rows")
    for row_number, row in enumerate(rows, 1):
        # Public Python callers can also construct or mutate the row list.
        # Report invalid record types as validation failures, not TypeError.
        if not isinstance(row, Mapping):
            raise ValueError(f"CSV data row {row_number} must be a mapping")
        # Keep the long-standing logical record number, and append the actual
        # starting file line for readers that retain physical CSV positions.
        suffix = f" (source line {source_lines[row_number - 1]})" if source_lines else ""
        # DictReader uses None for overflow cells, but caller-constructed
        # mappings may hide an extra field behind any other key. Do not
        # echo arbitrary field names or values in the diagnostic.
        if None in row or any(key not in declared_fields for key in row):
            raise ValueError(f"CSV data row {row_number} has more fields than the header{suffix}")
        if any(row.get(name) is None for name in header):
            raise ValueError(f"CSV data row {row_number} has fewer fields than the header{suffix}")

    # Defer this check until after ragged-row validation to preserve the
    # existing, more specific diagnostics for malformed records.
    skipped = getattr(rows, "blank_source_lines", ())
    if (
        not isinstance(skipped, (tuple, list))
        or any(type(line) is not int or line < 1 for line in skipped)
        or any(left >= right for left, right in zip(skipped, skipped[1:], strict=False))
    ):
        raise ValueError("CSV blank source line metadata must be positive and ordered")
    if skipped:
        raise ValueError(f"blank CSV data row at source line {skipped[0]}")
