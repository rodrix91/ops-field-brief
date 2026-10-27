"""Operational completeness brief for a CSV export.

This is a complement to column profiling. It answers three business questions
about one extract: are the required fields filled, does the business key
repeat, and which counterparties account for the rows.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

MISSING = {"", "na", "n/a", "null", "none", "s/d", "s.d.", "n/d", "n.d.", "-"}


# CSV values are untrusted text in Markdown tables and GitHub job summaries.
# Escape Markdown syntax without changing the original CSV or JSON payload.
_MARKDOWN_ESCAPES = {ord(char): "\\" + char for char in r"\*_{}[]()#+-.!|>~" + chr(96)}
_MARKDOWN_ESCAPES.update({ord("&"): "&amp;", ord("<"): "&lt;"})
# Keep untrusted CSV control bytes out of Markdown source and job summaries.
# C0 (including tab/newlines/NUL), DEL and C1 are rendered as visible
# numeric character references without touching the original JSON values.
_MARKDOWN_ESCAPES.update(
    {codepoint: f"&#{codepoint};" for codepoint in (*range(32), *range(127, 160))}
)
# Unicode bidirectional formatting controls can visually reorder a report even
# when HTML numeric references are used (Markdown renderers decode them).
# Render an explicit, inert ASCII marker instead. Leave ordinary RTL letters,
# accents and combining marks unchanged, and preserve the original JSON data.
_BIDI_CONTROLS = (0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x2070))
_MARKDOWN_ESCAPES.update({codepoint: f"[U+{codepoint:04X}]" for codepoint in _BIDI_CONTROLS})
# Unicode line/paragraph separators are valid CSV text but may create visual
# line breaks in rendered Markdown. Use inert markers and preserve the JSON data.
_MARKDOWN_ESCAPES.update({codepoint: f"[U+{codepoint:04X}]" for codepoint in (0x2028, 0x2029)})


def _markdown_text(value: str) -> str:
    """Display an arbitrary CSV value literally on a single Markdown source line."""
    return value.translate(_MARKDOWN_ESCAPES)


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
    max_duplicate_share: float | None = None
    complete_key_rows: int = 0
    duplicate_share: float = 0.0
    failed_duplicate_share: bool = False
    min_rows: int | None = None
    failed_rows: bool = False
    max_rows: int | None = None
    failed_max_rows: bool = False
    max_group_share: float | None = None
    top_group_share: float = 0.0
    failed_group_share: bool = False
    max_assigned_group_share: float | None = None
    top_assigned_group_share: float = 0.0
    assigned_group_rows: int = 0
    failed_assigned_group_share: bool = False
    incomplete_key_rows: int = 0
    max_incomplete_keys: int | None = None
    failed_incomplete_keys: bool = False
    max_incomplete_key_share: float | None = None
    incomplete_key_share: float = 0.0
    failed_incomplete_key_share: bool = False
    max_missing_columns: tuple[tuple[str, float], ...] = ()
    min_distinct_groups: int | None = None
    distinct_groups: int = 0
    failed_distinct_groups: bool = False
    max_distinct_groups: int | None = None
    failed_max_distinct_groups: bool = False
    max_missing_group_share: float | None = None
    missing_group_rows: int = 0
    missing_group_share: float = 0.0
    failed_missing_group_share: bool = False
    casefold_key: bool = False
    casefold_group: bool = False
    min_complete_keys: int | None = None
    failed_complete_keys: bool = False
    min_distinct_keys: int | None = None
    distinct_keys: int = 0
    failed_distinct_keys: bool = False
    max_distinct_keys: int | None = None
    failed_max_distinct_keys: bool = False

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "key": self.key,
            "key_fields": list(self.key_fields),
            **({"casefold_key": True} if self.casefold_key else {}),
            **({"casefold_group": True} if self.casefold_group else {}),
            "duplicate_keys": self.duplicate_keys,
            "incomplete_key_rows": self.incomplete_key_rows,
            "max_incomplete_keys": self.max_incomplete_keys,
            "failed_incomplete_keys": self.failed_incomplete_keys,
            **(
                {
                    "max_incomplete_key_share": self.max_incomplete_key_share,
                    "incomplete_key_share": round(self.incomplete_key_share, 4),
                    "failed_incomplete_key_share": self.failed_incomplete_key_share,
                }
                if self.max_incomplete_key_share is not None
                else {}
            ),
            "max_duplicates": self.max_duplicates,
            "failed_duplicates": self.failed_duplicates,
            **(
                {
                    "min_complete_keys": self.min_complete_keys,
                    "complete_key_rows": self.complete_key_rows,
                    "failed_complete_keys": self.failed_complete_keys,
                }
                if self.min_complete_keys is not None
                else {}
            ),
            **(
                {
                    "max_duplicate_share": self.max_duplicate_share,
                    "complete_key_rows": self.complete_key_rows,
                    "duplicate_share": round(self.duplicate_share, 4),
                    "failed_duplicate_share": self.failed_duplicate_share,
                }
                if self.max_duplicate_share is not None
                else {}
            ),
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
                {
                    "min_distinct_keys": self.min_distinct_keys,
                    "distinct_keys": self.distinct_keys,
                    "failed_distinct_keys": self.failed_distinct_keys,
                }
                if self.min_distinct_keys is not None
                else {}
            ),
            **(
                {
                    "max_distinct_keys": self.max_distinct_keys,
                    "distinct_keys": self.distinct_keys,
                    "failed_max_distinct_keys": self.failed_max_distinct_keys,
                }
                if self.max_distinct_keys is not None
                else {}
            ),
            **(
                {"max_missing_columns": dict(self.max_missing_columns)}
                if self.max_missing_columns
                else {}
            ),
            **(
                {"min_rows": self.min_rows, "failed_rows": self.failed_rows}
                if self.min_rows is not None
                else {}
            ),
            **(
                {"max_rows": self.max_rows, "failed_max_rows": self.failed_max_rows}
                if self.max_rows is not None
                else {}
            ),
            **(
                {
                    "max_group_share": self.max_group_share,
                    "top_group_share": round(self.top_group_share, 4),
                    "failed_group_share": self.failed_group_share,
                }
                if self.max_group_share is not None
                else {}
            ),
            **(
                {
                    "max_assigned_group_share": self.max_assigned_group_share,
                    "top_assigned_group_share": round(self.top_assigned_group_share, 4),
                    "assigned_group_rows": self.assigned_group_rows,
                    "failed_assigned_group_share": self.failed_assigned_group_share,
                }
                if self.max_assigned_group_share is not None
                else {}
            ),
            **(
                {
                    "min_distinct_groups": self.min_distinct_groups,
                    "distinct_groups": self.distinct_groups,
                    "failed_distinct_groups": self.failed_distinct_groups,
                }
                if self.min_distinct_groups is not None
                else {}
            ),
            **(
                {
                    "max_distinct_groups": self.max_distinct_groups,
                    "distinct_groups": self.distinct_groups,
                    "failed_max_distinct_groups": self.failed_max_distinct_groups,
                }
                if self.max_distinct_groups is not None
                else {}
            ),
            **(
                {
                    "max_missing_group_share": self.max_missing_group_share,
                    "missing_group_rows": self.missing_group_rows,
                    "missing_group_share": round(self.missing_group_share, 4),
                    "failed_missing_group_share": self.failed_missing_group_share,
                }
                if self.max_missing_group_share is not None
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
    max_duplicate_share: float | None = None,
    key_fields: list[str] | tuple[str, ...] | None = None,
    min_rows: int | None = None,
    max_group_share: float | None = None,
    max_assigned_group_share: float | None = None,
    max_incomplete_keys: int | None = None,
    max_incomplete_key_share: float | None = None,
    max_missing_columns: dict[str, float] | None = None,
    min_distinct_groups: int | None = None,
    max_distinct_groups: int | None = None,
    max_missing_group_share: float | None = None,
    casefold_key: bool = False,
    casefold_group: bool = False,
    max_rows: int | None = None,
    min_complete_keys: int | None = None,
    min_distinct_keys: int | None = None,
    max_distinct_keys: int | None = None,
) -> Brief:
    if not 0 <= max_missing <= 1:
        raise ValueError("max_missing must be between 0 and 1")
    if top_n < 0:
        raise ValueError("top must be 0 or greater")
    if max_duplicates is not None and max_duplicates < 0:
        raise ValueError("max_duplicates must be 0 or greater")
    if min_complete_keys is not None and min_complete_keys < 0:
        raise ValueError("min_complete_keys must be 0 or greater")
    if min_distinct_keys is not None and min_distinct_keys < 0:
        raise ValueError("min_distinct_keys must be 0 or greater")
    if max_distinct_keys is not None and max_distinct_keys < 0:
        raise ValueError("max_distinct_keys must be 0 or greater")
    if (
        min_distinct_keys is not None
        and max_distinct_keys is not None
        and min_distinct_keys > max_distinct_keys
    ):
        raise ValueError("min_distinct_keys cannot exceed max_distinct_keys")
    if max_duplicate_share is not None and not 0 <= max_duplicate_share <= 1:
        raise ValueError("max_duplicate_share must be between 0 and 1")
    if max_incomplete_keys is not None and max_incomplete_keys < 0:
        raise ValueError("max_incomplete_keys must be 0 or greater")
    if max_incomplete_key_share is not None and not 0 <= max_incomplete_key_share <= 1:
        raise ValueError("max_incomplete_key_share must be between 0 and 1")
    if min_rows is not None and min_rows < 0:
        raise ValueError("min_rows must be 0 or greater")
    if max_rows is not None and max_rows < 0:
        raise ValueError("max_rows must be 0 or greater")
    if min_rows is not None and max_rows is not None and min_rows > max_rows:
        raise ValueError("min_rows cannot exceed max_rows")
    if max_group_share is not None and not 0 <= max_group_share <= 1:
        raise ValueError("max_group_share must be between 0 and 1")
    if max_group_share is not None and not group:
        raise ValueError("max_group_share requires --group")
    if max_assigned_group_share is not None and not 0 <= max_assigned_group_share <= 1:
        raise ValueError("max_assigned_group_share must be between 0 and 1")
    if max_assigned_group_share is not None and not group:
        raise ValueError("max_assigned_group_share requires --group")
    if min_distinct_groups is not None and min_distinct_groups < 0:
        raise ValueError("min_distinct_groups must be 0 or greater")
    if min_distinct_groups is not None and not group:
        raise ValueError("min_distinct_groups requires --group")
    if max_distinct_groups is not None and max_distinct_groups < 0:
        raise ValueError("max_distinct_groups must be 0 or greater")
    if max_distinct_groups is not None and not group:
        raise ValueError("max_distinct_groups requires --group")
    if (
        min_distinct_groups is not None
        and max_distinct_groups is not None
        and min_distinct_groups > max_distinct_groups
    ):
        raise ValueError("min_distinct_groups cannot exceed max_distinct_groups")
    if max_missing_group_share is not None and not 0 <= max_missing_group_share <= 1:
        raise ValueError("max_missing_group_share must be between 0 and 1")
    if max_missing_group_share is not None and not group:
        raise ValueError("max_missing_group_share requires --group")
    overrides = dict(max_missing_columns or {})
    if any(not 0 <= limit <= 1 for limit in overrides.values()):
        raise ValueError("max_missing_columns shares must be between 0 and 1")
    unknown_overrides = [name for name in overrides if name not in required]
    if unknown_overrides:
        raise ValueError(
            "max_missing_columns must reference required fields: " + ", ".join(unknown_overrides)
        )
    if not rows and not required:
        raise ValueError("required fields are needed when the file has no header row")
    duplicate_required = [name for name, count in Counter(required).items() if count > 1]
    if duplicate_required:
        raise ValueError("duplicate required fields: " + ", ".join(duplicate_required))

    if key is not None and key_fields is not None:
        raise ValueError("use either key or key_fields, not both")
    effective_key_fields = tuple(key_fields) if key_fields is not None else ((key,) if key else ())
    if any(not name for name in effective_key_fields):
        raise ValueError("key fields must not be blank")
    repeated_key_fields = [
        name for name, count in Counter(effective_key_fields).items() if count > 1
    ]
    if repeated_key_fields:
        raise ValueError("duplicate key fields: " + ", ".join(repeated_key_fields))
    if max_duplicates is not None and not effective_key_fields:
        raise ValueError("max_duplicates requires --key")
    if min_complete_keys is not None and not effective_key_fields:
        raise ValueError("min_complete_keys requires --key")
    if min_distinct_keys is not None and not effective_key_fields:
        raise ValueError("min_distinct_keys requires --key")
    if max_distinct_keys is not None and not effective_key_fields:
        raise ValueError("max_distinct_keys requires --key")
    if max_duplicate_share is not None and not effective_key_fields:
        raise ValueError("max_duplicate_share requires --key")
    if max_incomplete_keys is not None and not effective_key_fields:
        raise ValueError("max_incomplete_keys requires --key")
    if max_incomplete_key_share is not None and not effective_key_fields:
        raise ValueError("max_incomplete_key_share requires --key")
    if casefold_key and not effective_key_fields:
        raise ValueError("casefold_key requires --key")
    if casefold_group and not group:
        raise ValueError("casefold_group requires --group")

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
    incomplete_key_rows = 0
    # None identifies missing labels independently of any legitimate CSV value.
    groups: Counter[str | None] = Counter()

    for row in rows:
        for name in required:
            current = fills[name]
            if _is_missing(row.get(name, "")):
                fills[name] = FieldFill(name, current.filled, current.missing + 1)
            else:
                fills[name] = FieldFill(name, current.filled + 1, current.missing)
        if effective_key_fields:
            key_value = tuple(_clean(row.get(name, "")) for name in effective_key_fields)
            if all(not _is_missing(value) for value in key_value):
                keys.append(
                    tuple(value.casefold() for value in key_value) if casefold_key else key_value
                )
            else:
                incomplete_key_rows += 1
        if group:
            label = _clean(row.get(group, ""))
            if _is_missing(label):
                groups[None] += 1
            else:
                groups[label.casefold() if casefold_group else label] += 1

    duplicate_keys = 0
    if effective_key_fields:
        counts = Counter(keys)
        duplicate_keys = sum(count - 1 for count in counts.values() if count > 1)

    fields = tuple(fills[name] for name in required)
    failed = tuple(
        field.name
        for field in fields
        if field.missing_rate > overrides.get(field.name, max_missing)
    )
    failed_duplicates = bool(max_duplicates is not None and duplicate_keys > max_duplicates)
    # Only fully identified business keys can be checked for duplicates.
    # A nonempty export without any valid key fails closed when this gate is
    # enabled; missing-key limits remain a separate independent check.
    complete_key_rows = len(keys)
    failed_complete_keys = bool(
        min_complete_keys is not None and complete_key_rows < min_complete_keys
    )
    distinct_keys = (
        len(set(keys)) if min_distinct_keys is not None or max_distinct_keys is not None else 0
    )
    failed_distinct_keys = bool(min_distinct_keys is not None and distinct_keys < min_distinct_keys)
    failed_max_distinct_keys = bool(
        max_distinct_keys is not None and distinct_keys > max_distinct_keys
    )
    duplicate_share = duplicate_keys / complete_key_rows if complete_key_rows else 0.0
    failed_duplicate_share = bool(
        max_duplicate_share is not None
        and ((bool(rows) and complete_key_rows == 0) or duplicate_share > max_duplicate_share)
    )
    failed_incomplete_keys = bool(
        max_incomplete_keys is not None and incomplete_key_rows > max_incomplete_keys
    )
    incomplete_key_share = incomplete_key_rows / len(rows) if rows else 0.0
    failed_incomplete_key_share = bool(
        max_incomplete_key_share is not None and incomplete_key_share > max_incomplete_key_share
    )
    failed_rows = bool(min_rows is not None and len(rows) < min_rows)
    failed_max_rows = bool(max_rows is not None and len(rows) > max_rows)
    top_group_share = groups.most_common(1)[0][1] / len(rows) if group and rows else 0.0
    failed_group_share = bool(max_group_share is not None and top_group_share > max_group_share)
    # Distinguish identified customers/suppliers from the pooled missing bucket.
    # Their share can be high even when many rows are unassigned. This is an
    # independent opt-in metric: the original group-share contract is unchanged.
    assigned_group_rows = len(rows) - groups[None] if group else 0
    largest_assigned = max(
        (count for label, count in groups.items() if label is not None),
        default=0,
    )
    top_assigned_group_share = (
        largest_assigned / assigned_group_rows if assigned_group_rows else 0.0
    )
    failed_assigned_group_share = bool(
        max_assigned_group_share is not None
        and (
            (bool(rows) and assigned_group_rows == 0)
            or top_assigned_group_share > max_assigned_group_share
        )
    )
    # Missing tokens share one display bucket but are not distinct business groups.
    distinct_groups = sum(label is not None for label in groups)
    failed_distinct_groups = bool(
        min_distinct_groups is not None and distinct_groups < min_distinct_groups
    )
    failed_max_distinct_groups = bool(
        max_distinct_groups is not None and distinct_groups > max_distinct_groups
    )
    # Only true missing-group tokens count; a literal "(blank)" customer is valid.
    missing_group_rows = groups[None]
    missing_group_share = missing_group_rows / len(rows) if rows else 0.0
    failed_missing_group_share = bool(
        max_missing_group_share is not None and missing_group_share > max_missing_group_share
    )
    missing_label = "(blank)"
    if None in groups and missing_label in groups:
        # A real "(blank)" group must not merge with missing values or share
        # the same displayed name. Choose an unused name for the missing bucket.
        missing_label = "(blank) [missing]"
        number = 2
        while missing_label in groups:
            missing_label = f"(blank) [missing {number}]"
            number += 1
    top_groups = tuple(
        (missing_label if name is None else name, count)
        for name, count in groups.most_common(top_n)
    )

    return Brief(
        rows=len(rows),
        key=",".join(effective_key_fields) or None,
        duplicate_keys=duplicate_keys,
        fields=fields,
        top=top_groups,
        failed_fields=failed,
        key_fields=effective_key_fields,
        max_duplicates=max_duplicates,
        failed_duplicates=failed_duplicates,
        min_complete_keys=min_complete_keys,
        failed_complete_keys=failed_complete_keys,
        min_distinct_keys=min_distinct_keys,
        distinct_keys=distinct_keys,
        failed_distinct_keys=failed_distinct_keys,
        max_distinct_keys=max_distinct_keys,
        failed_max_distinct_keys=failed_max_distinct_keys,
        max_duplicate_share=max_duplicate_share,
        complete_key_rows=complete_key_rows,
        duplicate_share=duplicate_share,
        failed_duplicate_share=failed_duplicate_share,
        min_rows=min_rows,
        failed_rows=failed_rows,
        max_rows=max_rows,
        failed_max_rows=failed_max_rows,
        max_group_share=max_group_share,
        top_group_share=top_group_share,
        failed_group_share=failed_group_share,
        max_assigned_group_share=max_assigned_group_share,
        top_assigned_group_share=top_assigned_group_share,
        assigned_group_rows=assigned_group_rows,
        failed_assigned_group_share=failed_assigned_group_share,
        incomplete_key_rows=incomplete_key_rows,
        max_incomplete_keys=max_incomplete_keys,
        failed_incomplete_keys=failed_incomplete_keys,
        max_incomplete_key_share=max_incomplete_key_share,
        incomplete_key_share=incomplete_key_share,
        failed_incomplete_key_share=failed_incomplete_key_share,
        max_missing_columns=tuple(
            (name, overrides[name]) for name in required if name in overrides
        ),
        min_distinct_groups=min_distinct_groups,
        distinct_groups=distinct_groups,
        failed_distinct_groups=failed_distinct_groups,
        max_distinct_groups=max_distinct_groups,
        failed_max_distinct_groups=failed_max_distinct_groups,
        max_missing_group_share=max_missing_group_share,
        missing_group_rows=missing_group_rows,
        missing_group_share=missing_group_share,
        failed_missing_group_share=failed_missing_group_share,
        casefold_key=casefold_key,
        casefold_group=casefold_group,
    )


def _detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error as exc:
        # Sniffer cannot identify a separator in valid single-column files.
        # Accept those only when every candidate parses every sampled CSV
        # record as exactly one field; still reject inconsistent or bad CSV.
        try:
            single_column = bool(sample.strip())
            for candidate in DELIMITERS.values():
                if any(
                    len(record) != 1
                    for record in csv.reader(io.StringIO(sample), delimiter=candidate, strict=True)
                    if record  # csv.reader ignores empty physical lines
                ):
                    single_column = False
                    break
            if single_column:
                return ","
        except csv.Error:
            pass
        raise ValueError(
            "could not detect delimiter; use --delimiter comma, semicolon, tab, or pipe"
        ) from exc


def read_csv(
    path: Path,
    delimiter: str | None = ",",
    encoding: str = "utf-8",
    stdin=None,
    strict: bool = False,
) -> list[dict[str, str]]:
    # Excel UTF-8 exports often start with a BOM. utf-8-sig strips it and still reads plain utf-8.
    is_utf8 = encoding.lower().replace("_", "-") in ("utf-8", "utf8", "utf-8-sig")
    codec = "utf-8-sig" if is_utf8 else encoding
    if stdin is not None:
        if delimiter is None:
            text = stdin.read()
            if is_utf8:
                text = text.lstrip("\ufeff")
            try:
                delimiter = _detect_delimiter(text[:8192])
            except ValueError:
                # The sample may stop inside a long quoted CSV field.
                # Stdin is already buffered in full, so retry with whole text.
                if len(text) <= 8192:
                    raise
                delimiter = _detect_delimiter(text)
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter, strict=strict)
            return CsvRows(reader, reader.fieldnames)
        reader = csv.DictReader(stdin, delimiter=delimiter, strict=strict)
        if is_utf8 and reader.fieldnames and reader.fieldnames[0].startswith("\ufeff"):
            fieldnames = list(reader.fieldnames)
            fieldnames[0] = fieldnames[0].lstrip("\ufeff")
            reader.fieldnames = fieldnames
        return CsvRows(reader, reader.fieldnames)
    # Accept compressed operational exports without changing CSV parsing.
    # The suffix selects compression; stdin stays a plain text stream.
    if path.suffix.lower() == ".gz":
        stream = gzip.open(path, "rt", newline="", encoding=codec)
    else:
        stream = path.open(newline="", encoding=codec)
    with stream as handle:
        if delimiter is None:
            sample = handle.read(8192)
            try:
                delimiter = _detect_delimiter(sample)
            except ValueError:
                # Retry on the complete input only when the initial prefix
                # cannot be classified (e.g. a quote crosses character 8192).
                remainder = handle.read()
                if not remainder:
                    raise
                delimiter = _detect_delimiter(sample + remainder)
            handle.seek(0)
        reader = csv.DictReader(handle, delimiter=delimiter, strict=strict)
        return CsvRows(reader, reader.fieldnames)


def render_markdown(brief: Brief) -> str:
    lines = [
        "# Operational field brief",
        "",
        f"- Rows: {brief.rows}",
        f"- Business key: {_markdown_text(brief.key) if brief.key else 'not set'}",
        f"- Extra rows from a repeated key: {brief.duplicate_keys}",
    ]
    if brief.max_duplicate_share is not None:
        lines.append(f"- Maximum duplicate-key share: {brief.max_duplicate_share:.1%}")
        lines.append(f"- Rows with complete keys: {brief.complete_key_rows}")
        lines.append(f"- Observed duplicate-key share: {brief.duplicate_share:.1%}")
    if brief.casefold_key:
        lines.append("- Business-key comparison: case-insensitive (Unicode casefold)")
    if brief.casefold_group:
        lines.append("- Group comparison: case-insensitive (Unicode casefold)")
    if brief.min_distinct_groups is not None:
        lines.append(f"- Minimum distinct non-missing groups: {brief.min_distinct_groups}")
        lines.append(f"- Observed distinct non-missing groups: {brief.distinct_groups}")
    if brief.max_distinct_groups is not None:
        lines.append(f"- Maximum distinct non-missing groups: {brief.max_distinct_groups}")
        lines.append(f"- Observed distinct non-missing groups: {brief.distinct_groups}")
    if brief.max_missing_group_share is not None:
        lines.append(f"- Max allowed missing-group share: {brief.max_missing_group_share:.1%}")
        lines.append(f"- Rows with missing group labels: {brief.missing_group_rows}")
        lines.append(f"- Observed missing-group share: {brief.missing_group_share:.1%}")
    if brief.max_missing_columns:
        limits = ", ".join(
            f"{_markdown_text(name)}: {limit:.1%}" for name, limit in brief.max_missing_columns
        )
        lines.append(f"- Field-specific missing limits: {limits}")
    if brief.min_complete_keys is not None:
        lines.append(f"- Minimum rows with complete business keys: {brief.min_complete_keys}")
        lines.append(f"- Rows with complete business keys: {brief.complete_key_rows}")
    if brief.min_distinct_keys is not None:
        lines.append(f"- Minimum distinct complete business keys: {brief.min_distinct_keys}")
    if brief.max_distinct_keys is not None:
        lines.append(f"- Maximum distinct complete business keys: {brief.max_distinct_keys}")
    if brief.min_distinct_keys is not None or brief.max_distinct_keys is not None:
        lines.append(f"- Observed distinct complete business keys: {brief.distinct_keys}")
    if brief.max_duplicates is not None:
        lines.append(f"- Max allowed duplicate extra rows: {brief.max_duplicates}")
    if brief.key_fields:
        lines.append(f"- Rows with incomplete business keys: {brief.incomplete_key_rows}")
    if brief.max_incomplete_keys is not None:
        lines.append(f"- Max allowed incomplete business keys: {brief.max_incomplete_keys}")
    if brief.max_incomplete_key_share is not None:
        lines.append(f"- Max allowed incomplete-key share: {brief.max_incomplete_key_share:.1%}")
        lines.append(f"- Observed incomplete-key share: {brief.incomplete_key_share:.1%}")
    if brief.min_rows is not None:
        lines.append(f"- Minimum rows: {brief.min_rows}")
    if brief.max_rows is not None:
        lines.append(f"- Maximum rows: {brief.max_rows}")
    if brief.max_group_share is not None:
        lines.append(f"- Max allowed top-group share: {brief.max_group_share:.1%}")
        lines.append(f"- Observed top-group share: {brief.top_group_share:.1%}")
    if brief.max_assigned_group_share is not None:
        lines.append(f"- Max allowed assigned-group share: {brief.max_assigned_group_share:.1%}")
        lines.append(f"- Rows assigned to a group: {brief.assigned_group_rows}")
        lines.append(f"- Observed top assigned-group share: {brief.top_assigned_group_share:.1%}")
    lines.extend(
        [
            "",
            "## Required fields",
            "",
            "| Field | Filled | Missing | Missing rate |",
            "|---|---:|---:|---:|",
        ]
    )
    for field in brief.fields:
        lines.append(
            f"| {_markdown_text(field.name)} | {field.filled} | {field.missing} | "
            f"{field.missing_rate:.1%} |"
        )
    if brief.top:
        lines.extend(["", "## Top groups", ""])
        for value, count in brief.top:
            lines.append(f"- {_markdown_text(value)}: {count}")
    if brief.failed_fields:
        lines.extend(["", "## Failed fill check", ""])
        lines.append(", ".join(_markdown_text(name) for name in brief.failed_fields))
    if brief.failed_complete_keys:
        lines.extend(
            [
                "",
                "## Failed complete-key row-count check",
                "",
                (
                    f"Rows with complete business keys ({brief.complete_key_rows}) are below "
                    f"the minimum ({brief.min_complete_keys})."
                ),
            ]
        )
    if brief.failed_distinct_keys:
        lines.extend(
            [
                "",
                "## Failed distinct business-key check",
                "",
                (
                    f"Distinct complete business keys ({brief.distinct_keys}) are below "
                    f"the minimum ({brief.min_distinct_keys})."
                ),
            ]
        )
    if brief.failed_max_distinct_keys:
        lines.extend(
            [
                "",
                "## Failed maximum distinct business-key check",
                "",
                (
                    f"Distinct complete business keys ({brief.distinct_keys}) exceed "
                    f"the maximum ({brief.max_distinct_keys})."
                ),
            ]
        )
    if brief.failed_duplicates:
        lines.extend(
            [
                "",
                "## Failed duplicate check",
                "",
                (
                    f"Extra rows from a repeated key ({brief.duplicate_keys}) "
                    f"exceed the limit ({brief.max_duplicates})."
                ),
            ]
        )
    if brief.failed_duplicate_share:
        lines.extend(
            [
                "",
                "## Failed duplicate-share check",
                "",
                (
                    "No rows have a complete business key."
                    if brief.complete_key_rows == 0
                    else (
                        f"Duplicate-key share ({brief.duplicate_share:.1%}) exceeds "
                        f"the limit ({brief.max_duplicate_share:.1%})."
                    )
                ),
            ]
        )
    if brief.failed_incomplete_keys:
        lines.extend(
            [
                "",
                "## Failed incomplete-key check",
                "",
                (
                    f"Rows with incomplete business keys ({brief.incomplete_key_rows}) "
                    f"exceed the limit ({brief.max_incomplete_keys})."
                ),
            ]
        )
    if brief.failed_incomplete_key_share:
        lines.extend(
            [
                "",
                "## Failed incomplete-key share check",
                "",
                (
                    f"Incomplete-key share ({brief.incomplete_key_share:.1%}) exceeds "
                    f"the limit ({brief.max_incomplete_key_share:.1%})."
                ),
            ]
        )
    if brief.failed_rows:
        lines.extend(
            [
                "",
                "## Failed row-count check",
                "",
                f"Rows ({brief.rows}) are below the minimum ({brief.min_rows}).",
            ]
        )
    if brief.failed_max_rows:
        lines.extend(
            [
                "",
                "## Failed maximum row-count check",
                "",
                f"Rows ({brief.rows}) exceed the maximum ({brief.max_rows}).",
            ]
        )
    if brief.failed_group_share:
        lines.extend(
            [
                "",
                "## Failed group-concentration check",
                "",
                (
                    f"Top-group share ({brief.top_group_share:.1%}) exceeds the limit "
                    f"({brief.max_group_share:.1%})."
                ),
            ]
        )
    if brief.failed_assigned_group_share:
        lines.extend(
            [
                "",
                "## Failed assigned-group concentration check",
                "",
                (
                    "No rows have an identified group."
                    if brief.assigned_group_rows == 0
                    else (
                        f"Top assigned-group share ({brief.top_assigned_group_share:.1%}) "
                        f"exceeds the limit ({brief.max_assigned_group_share:.1%})."
                    )
                ),
            ]
        )
    if brief.failed_distinct_groups:
        lines.extend(
            [
                "",
                "## Failed group-diversity check",
                "",
                (
                    f"Distinct non-missing groups ({brief.distinct_groups}) are below "
                    f"the minimum ({brief.min_distinct_groups})."
                ),
            ]
        )
    if brief.failed_max_distinct_groups:
        lines.extend(
            [
                "",
                "## Failed group-cardinality check",
                "",
                (
                    f"Distinct non-missing groups ({brief.distinct_groups}) exceed "
                    f"the maximum ({brief.max_distinct_groups})."
                ),
            ]
        )
    if brief.failed_missing_group_share:
        lines.extend(
            [
                "",
                "## Failed missing-group check",
                "",
                (
                    f"Missing-group share ({brief.missing_group_share:.1%}) exceeds the limit "
                    f"({brief.max_missing_group_share:.1%})."
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def render(brief: Brief, as_json: bool) -> str:
    if as_json:
        return json.dumps(brief.to_dict(), indent=2) + "\n"
    return render_markdown(brief)
