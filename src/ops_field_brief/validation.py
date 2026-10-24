"""Opt-in CSV structure checks before operational metrics are calculated."""

from __future__ import annotations

from collections import Counter


def validate_csv_structure(rows: list[dict[str, str]]) -> None:
    """Reject ambiguous headers and ragged rows without changing default parsing.

    The normal reader preserves header names on CsvRows, including header-only
    files. DictReader maps surplus fields under a None key and missing fields
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
    repeated = [name for name, count in Counter(names).items() if count > 1]
    if repeated:
        raise ValueError("duplicate CSV header columns: " + ", ".join(repeated))

    for row_number, row in enumerate(rows, 1):
        if None in row:
            raise ValueError(f"CSV data row {row_number} has more fields than the header")
        if any(row.get(name) is None for name in header):
            raise ValueError(f"CSV data row {row_number} has fewer fields than the header")
