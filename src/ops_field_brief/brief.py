"""Operational completeness brief for a CSV export.

This is a complement to column profiling. It answers three business questions
about one extract: are the required fields filled, does the business key
repeat, and which counterparties account for the rows.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MISSING = {"", "na", "n/a", "null", "none", "s/d", "n/d", "-"}

DELIMITERS = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}


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

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "key": self.key,
            "duplicate_keys": self.duplicate_keys,
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
) -> Brief:
    if max_missing < 0 or max_missing > 1:
        raise ValueError("max_missing must be between 0 and 1")
    if not rows and not required:
        raise ValueError("required fields are needed when the file has no header row")

    header = list(rows[0].keys()) if rows else required
    unknown = [name for name in required if name not in header]
    if key and key not in header:
        unknown.append(key)
    if group and group not in header:
        unknown.append(group)
    if unknown:
        raise ValueError("unknown columns: " + ", ".join(unknown))

    fills = {name: FieldFill(name, 0, 0) for name in required}
    keys: list[str] = []
    groups: Counter[str] = Counter()

    for row in rows:
        for name in required:
            current = fills[name]
            if _is_missing(row.get(name, "")):
                fills[name] = FieldFill(name, current.filled, current.missing + 1)
            else:
                fills[name] = FieldFill(name, current.filled + 1, current.missing)
        if key:
            keys.append(_clean(row.get(key, "")))
        if group:
            label = _clean(row.get(group, "")) or "(blank)"
            groups[label] += 1

    duplicate_keys = 0
    if key:
        counts = Counter(value for value in keys if value)
        duplicate_keys = sum(count - 1 for count in counts.values() if count > 1)

    fields = tuple(fills[name] for name in required)
    failed = tuple(field.name for field in fields if field.missing_rate > max_missing)
    return Brief(
        rows=len(rows),
        key=key,
        duplicate_keys=duplicate_keys,
        fields=fields,
        top=tuple(groups.most_common(top_n)),
        failed_fields=failed,
    )


def read_csv(path: Path, delimiter: str = ",", encoding: str = "utf-8") -> list[dict[str, str]]:
    # Excel UTF-8 exports often start with a BOM. utf-8-sig strips it and still reads plain utf-8.
    codec = "utf-8-sig" if encoding.lower().replace("_", "-") == "utf-8" else encoding
    with path.open(newline="", encoding=codec) as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def render_markdown(brief: Brief) -> str:
    lines = [
        "# Operational field brief",
        "",
        f"- Rows: {brief.rows}",
        f"- Business key: {brief.key or 'not set'}",
        f"- Extra rows from a repeated key: {brief.duplicate_keys}",
        "",
        "## Required fields",
        "",
        "| Field | Filled | Missing | Missing rate |",
        "|---|---:|---:|---:|",
    ]
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
    return "\n".join(lines) + "\n"


def render(brief: Brief, as_json: bool) -> str:
    if as_json:
        return json.dumps(brief.to_dict(), indent=2) + "\n"
    return render_markdown(brief)
