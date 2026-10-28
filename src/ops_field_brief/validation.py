"""Opt-in CSV structure checks before operational metrics are calculated."""

from __future__ import annotations

from collections import Counter
from unicodedata import normalize


def validate_csv_structure(rows: list[dict[str, str]], *, casefold_headers: bool = False) -> None:
    """Reject ambiguous headers and ragged rows without changing default parsing.

    The normal reader preserves header names on CsvRows, including header-only
    files. Set casefold_headers to also reject Unicode case-equivalent labels,
    without renaming input columns or changing the default strict behavior.
    DictReader maps surplus fields under a None key and missing fields
    to None values, so both cases can be detected without re-reading the CSV.
    """
    header = getattr(rows, "fieldnames", None)
    if header is None:
        raise ValueError("strict CSV validation requires a parsed header")
    if not header:
        raise ValueError("CSV has no header row")

    for position, name in enumerate(header, 1):
        if not name or not name.strip():
            raise ValueError(f"blank CSV header at column {position}")

    names = [name.strip() for name in header]
    # With the opt-in flag, compare both case-insensitively and under Unicode
    # canonical equivalence (NFC). Keep original column names untouched so
    # --required, --key and --group continue to match exactly.
    compared = [normalize("NFC", name.casefold()) if casefold_headers else name for name in names]
    repeated = [name for name, count in Counter(compared).items() if count > 1]
    if repeated:
        raise ValueError("duplicate CSV header columns: " + ", ".join(repeated))

    source_lines: tuple[int, ...] = getattr(rows, "source_lines", ())
    for row_number, row in enumerate(rows, 1):
        # Keep the long-standing logical record number, and append the actual
        # starting file line for readers that retain physical CSV positions.
        suffix = f" (source line {source_lines[row_number - 1]})" if source_lines else ""
        if None in row:
            raise ValueError(f"CSV data row {row_number} has more fields than the header{suffix}")
        if any(row.get(name) is None for name in header):
            raise ValueError(f"CSV data row {row_number} has fewer fields than the header{suffix}")
