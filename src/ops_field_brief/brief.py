"""Operational completeness brief for a CSV export.

This is a complement to column profiling. It answers three business questions
about one extract: are the required fields filled, does the business key
repeat, and which counterparties account for the rows.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MISSING = {"", "na", "n/a", "null", "none", "s/d", "s.d.", "n/d", "n.d.", "-"}

DELIMITERS = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}


class CsvRows(list[dict[str, str]]):
    """CSV rows that retain the parsed header even when there are no data rows."""

    def __init__(
        self,
        rows: Iterable[dict[str, str]],
        fieldnames: Iterable[str | None] | None,
    ) -> None:
        super().__init__(rows)
        self.fieldnames = tuple(name for name in (fieldnames or ()) if name is not None)


@dataclass(frozen=True)
class FieldFill:
    name: str
    filled: int
    missing: int

    @property
    def missing_rate(self) -> float:
        total = self.filled + self.missing
        if total == 0:
            return 0.0
        return self.missing / total


@dataclass(frozen=True)
class Brief:
    rows: int
    key: str | None
    duplicate_keys: int
    fields: tuple[FieldFill, ...]
    top: tuple[tuple[str, int], ...]
    failed_fields: tuple[str, ...]
    key_fields: tuple[str, ...] = ()
    max_duplicates: int | None = None
    failed_duplicates: bool = False
    min_rows: int | None = None
    failed_rows: bool = False

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "key": self.key,
            "key_fields": list(self.key_fields),
            "duplicate_keys": self.duplicate_keys,
            "max_duplicates": self.max_duplicates,
            "failed_duplicates": self.failed_duplicates,
            "fields": [
                {
                    "name": field.name,
                    "filled": field.filled,
                    "missing": field.missing,
                    "missing_rate": round(field.missing_rate, 4),
                }
                for field in self.fields
            ],
            "top": [{"value": value, "rows": count} for value, count in self.top],
            "failed_fields": list(self.failed_fields),
            **(
                {"min_rows": self.min_rows, "failed_rows": self.failed_rows}
                if self.min_rows is not None
                else {}
            ),
        }


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _is_missing(value: str) -> bool:
    return _clean(value).lower() in MISSING


def build_brief(
    rows: list[dict[str, str]],
    required: list[str],
    key: str | None = None,
    group: str | None = None,
    max_missing: float = 0.0,
    top_n: int = 5,
    max_duplicates: int | None = None,
    key_fields: list[str] | tuple[str, ...] | None = None,
    min_rows: int | None = None,
) -> Brief:
    if max_missing < 0 or max_missing > 1:
        raise ValueError("max_missing must be between 0 and 1")
    if top_n < 0:
        raise ValueError("top must be 0 or greater")
    if max_duplicates is not None and max_duplicates < 0:
        raise ValueError("max_duplicates must be 0 or greater")
    if min_rows is not None and min_rows < 0:
        raise ValueError("min_rows must be 0 or greater")
    if not rows and not required:
        raise ValueError("required fields are needed when the file has no header row")

    if key is not None and key_fields is not None:
        raise ValueError("use either key or key_fields, not both")
    effective_key_fields = tuple(key_fields) if key_fields is not None else ((key,) if key else ())
    if any(not name for name in effective_key_fields):
        raise ValueError("key fields must not be blank")

    preserved_header = list(getattr(rows, "fieldnames", ()))
    header = preserved_header or (list(rows[0].keys()) if rows else required)
    unknown = [name for name in required if name not in header]
    unknown.extend(name for name in effective_key_fields if name not in header)
    if group and group not in header:
        unknown.append(group)
    if unknown:
        raise ValueError("unknown columns: " + ", ".join(unknown))

    fills = {name: FieldFill(name, 0, 0) for name in required}
    keys: list[tuple[str, ...]] = []
    groups: Counter[str] = Counter()

    for row in rows:
        for name in required:
            current = fills[name]
            if _is_missing(row.get(name, "")):
                fills[name] = FieldFill(name, current.filled, current.missing + 1)
            else:
                fills[name] = FieldFill(name, current.filled + 1, current.missing)
        if effective_key_fields:
            key_value = tuple(_clean(row.get(name, "")) for name in effective_key_fields)
            if all(key_value):
                keys.append(key_value)
        if group:
            label = _clean(row.get(group, "")) or "(blank)"
            groups[label] += 1

    duplicate_keys = 0
    if effective_key_fields:
        counts = Counter(keys)
        duplicate_keys = sum(count - 1 for count in counts.values() if count > 1)

    fields = tuple(fills[name] for name in required)
    failed = tuple(field.name for field in fields if field.missing_rate > max_missing)
    failed_duplicates = bool(max_duplicates is not None and duplicate_keys > max_duplicates)
    failed_rows = bool(min_rows is not None and len(rows) < min_rows)

    return Brief(
        rows=len(rows),
        key=",".join(effective_key_fields) or None,
        duplicate_keys=duplicate_keys,
        fields=fields,
        top=tuple(groups.most_common(top_n)),
        failed_fields=failed,
        key_fields=effective_key_fields,
        max_duplicates=max_duplicates,
        failed_duplicates=failed_duplicates,
        min_rows=min_rows,
        failed_rows=failed_rows,
    )


def _detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error as exc:
        raise ValueError(
            "could not detect delimiter; use --delimiter comma, semicolon, tab, or pipe"
        ) from exc


def read_csv(
    path: Path,
    delimiter: str | None = ",",
    encoding: str = "utf-8",
    stdin=None,
) -> list[dict[str, str]]:
    # Excel UTF-8 exports often start with a BOM. utf-8-sig strips it and still reads plain utf-8.
    is_utf8 = encoding.lower().replace("_", "-") in ("utf-8", "utf8", "utf-8-sig")
    codec = "utf-8-sig" if is_utf8 else encoding
    if stdin is not None:
        if delimiter is None:
            text = stdin.read()
            if is_utf8:
                text = text.lstrip("\ufeff")
            delimiter = _detect_delimiter(text[:8192])
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            return CsvRows(reader, reader.fieldnames)
        reader = csv.DictReader(stdin, delimiter=delimiter)
        if is_utf8 and reader.fieldnames and reader.fieldnames[0].startswith("\ufeff"):
            reader.fieldnames[0] = reader.fieldnames[0].lstrip("\ufeff")
        return CsvRows(reader, reader.fieldnames)
    with path.open(newline="", encoding=codec) as handle:
        if delimiter is None:
            sample = handle.read(8192)
            delimiter = _detect_delimiter(sample)
            handle.seek(0)
        reader = csv.DictReader(handle, delimiter=delimiter)
        return CsvRows(reader, reader.fieldnames)


def render_markdown(brief: Brief) -> str:
    lines = [
        "# Operational field brief",
        "",
        f"- Rows: {brief.rows}",
        f"- Business key: {brief.key or 'not set'}",
        f"- Extra rows from a repeated key: {brief.duplicate_keys}",
    ]
    if brief.max_duplicates is not None:
        lines.append(f"- Max allowed duplicate extra rows: {brief.max_duplicates}")
    if brief.min_rows is not None:
        lines.append(f"- Minimum rows: {brief.min_rows}")
    lines.extend([
        "",
        "## Required fields",
        "",
        "| Field | Filled | Missing | Missing rate |",
        "|---|---:|---:|---:|",
    ])
    for field in brief.fields:
        lines.append(
            f"| {field.name} | {field.filled} | {field.missing} | {field.missing_rate:.1%} |"
        )
    if brief.top:
        lines.extend(["", "## Top groups", ""])
        for value, count in brief.top:
            lines.append(f"- {value}: {count}")
    if brief.failed_fields:
        lines.extend(["", "## Failed fill check", ""])
        lines.append(", ".join(brief.failed_fields))
    if brief.failed_duplicates:
        lines.extend([
            "",
            "## Failed duplicate check",
            "",
            (\n                f"Extra rows from a repeated key ({brief.duplicate_keys}) "\n                f"exceed the limit ({brief.max_duplicates})."\n            ),
        ])
    if brief.failed_rows:
        lines.extend([
            "",
            "## Failed row-count check",
            "",
            f"Rows ({brief.rows}) are below the minimum ({brief.min_rows}).",
        ])
    return "\n".join(lines) + "\n"


def render(brief: Brief, as_json: bool) -> str:
    if as_json:
        return json.dumps(brief.to_dict(), indent=2) + "\n"
    return render_markdown(brief)
