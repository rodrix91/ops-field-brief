"""Command line for an operational field brief."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from ops_field_brief import __version__
from ops_field_brief.brief import DELIMITERS, build_brief, read_csv, render
from ops_field_brief.validation import validate_csv_structure


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report fill rate, repeated business keys, and top groups in a CSV."
    )
    parser.add_argument("--version", action="version", version=f"ops-field-brief {__version__}")
    parser.add_argument("csv", type=Path, help="CSV with a header row. Use - to read from stdin.")
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding. Default utf-8. Use cp1252 or latin-1 for Windows Excel exports.",
    )
    parser.add_argument(
        "--required",
        required=True,
        help="Comma-separated fields that should be filled",
    )
    parser.add_argument(
        "--key",
        help="Business key column. Separate multiple columns with commas for a composite key.",
    )
    parser.add_argument(
        "--casefold-key",
        action="store_true",
        help="Compare business-key values without case differences (requires --key)",
    )
    parser.add_argument("--group", help="Column to rank by row count")
    parser.add_argument(
        "--casefold-group",
        action="store_true",
        help="Merge group values differing only in case (requires --group)",
    )
    parser.add_argument(
        "--max-missing",
        type=float,
        default=0.0,
        help="Fail if a required field is missing more than this share (0 to 1)",
    )
    parser.add_argument(
        "--max-missing-column",
        action="append",
        default=[],
        metavar="NAME=SHARE",
        help="Override --max-missing for one required field (repeatable; share 0 to 1)",
    )
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--delimiter",
        choices=["auto", *sorted(DELIMITERS)],
        default="comma",
        help=(
            "Field separator. Use auto to detect comma, semicolon, tab, or pipe. "
            "Default comma keeps the original behavior."
        ),
    )
    parser.add_argument(
        "--max-duplicates",
        type=int,
        default=None,
        help="Fail if extra rows from a repeated key exceed this count",
    )
    parser.add_argument(
        "--min-complete-keys",
        type=int,
        default=None,
        help="Fail if fewer than N rows have complete business keys (requires --key)",
    )
    parser.add_argument(
        "--min-distinct-keys",
        type=int,
        default=None,
        help=(
            "Fail if fewer than N distinct complete business keys exist "
            "(requires --key; duplicate complete rows count once)"
        ),
    )
    parser.add_argument(
        "--max-distinct-keys",
        type=int,
        default=None,
        help=(
            "Fail if more than N distinct complete business keys exist "
            "(requires --key; duplicate complete rows count once)"
        ),
    )
    parser.add_argument(
        "--max-duplicate-share",
        type=float,
        default=None,
        help=(
            "Fail if extra duplicate-key rows exceed this share of complete "
            "business-key rows (0 to 1; requires --key)"
        ),
    )
    parser.add_argument(
        "--max-incomplete-keys",
        type=int,
        default=None,
        help="Fail when more than N rows have a missing component in the --key value",
    )
    parser.add_argument(
        "--max-incomplete-key-share",
        type=float,
        default=None,
        help=(
            "Fail if the share of rows missing any --key component exceeds "
            "this value (0 to 1; requires --key)"
        ),
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=None,
        help="Fail if the CSV has fewer than this many data rows",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Fail if the CSV has more than this many data rows",
    )
    parser.add_argument(
        "--max-group-share",
        type=float,
        default=None,
        help="Fail if the largest --group value exceeds this share of rows (0 to 1)",
    )
    parser.add_argument(
        "--max-assigned-group-share",
        type=float,
        default=None,
        help=(
            "Fail if one non-missing --group value exceeds this share of "
            "assigned rows (0 to 1); requires --group"
        ),
    )
    parser.add_argument(
        "--max-missing-group-share",
        type=float,
        default=None,
        help="Fail if missing --group labels exceed this share of rows (0 to 1)",
    )
    parser.add_argument(
        "--min-distinct-groups",
        type=int,
        default=None,
        help="Fail if fewer than N non-missing distinct --group labels exist",
    )
    parser.add_argument(
        "--max-distinct-groups",
        type=int,
        default=None,
        help="Fail if more than N non-missing distinct --group labels exist",
    )
    parser.add_argument(
        "--strict-csv",
        action="store_true",
        help="Reject malformed quoting, duplicate/blank headers, and ragged rows",
    )
    parser.add_argument(
        "--casefold-headers",
        action="store_true",
        help="With --strict-csv, reject headers equivalent under Unicode casefold",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON instead of Markdown")
    return parser.parse_args(argv)


def _decoded_stdin(encoding: str):
    """Return stdin decoded with the CLI's explicit encoding, independent of OS locale."""
    raw = getattr(sys.stdin, "buffer", None)
    if raw is None:
        return sys.stdin
    normalized = encoding.lower().replace("_", "-")
    codec = "utf-8-sig" if normalized in ("utf-8", "utf8", "utf-8-sig") else encoding
    return io.StringIO(raw.read().decode(codec))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    required = [part.strip() for part in args.required.split(",")]
    if not any(required):
        print("at least one required field is needed", file=sys.stderr)
        return 2
    if any(not field for field in required):
        print("empty column in --required; specify every required field", file=sys.stderr)
        return 2
    key_fields = None
    if args.key is not None:
        key_fields = [part.strip() for part in args.key.split(",")]
        if not any(key_fields):
            print("at least one key field is needed", file=sys.stderr)
            return 2
        if any(not field for field in key_fields):
            print("empty column in --key; specify every key field", file=sys.stderr)
            return 2
    if args.casefold_headers and not args.strict_csv:
        print("--casefold-headers requires --strict-csv", file=sys.stderr)
        return 2
    try:
        missing_limits: dict[str, float] = {}
        for spec in args.max_missing_column:
            name, separator, share = spec.rpartition("=")
            name = name.strip()
            if not separator or not name or not share.strip():
                raise ValueError("--max-missing-column expects NAME=SHARE")
            if name in missing_limits:
                raise ValueError(f"duplicate --max-missing-column field: {name}")
            try:
                missing_limits[name] = float(share)
            except ValueError:
                raise ValueError(f"invalid --max-missing-column share: {share}") from None
        rows = read_csv(
            args.csv,
            delimiter=None if args.delimiter == "auto" else DELIMITERS[args.delimiter],
            encoding=args.encoding,
            stdin=_decoded_stdin(args.encoding) if str(args.csv) == "-" else None,
            strict=args.strict_csv,
        )
        if args.strict_csv:
            validate_csv_structure(rows, casefold_headers=args.casefold_headers)
        brief = build_brief(
            rows,
            required,
            key_fields=key_fields,
            casefold_key=args.casefold_key,
            group=args.group,
            casefold_group=args.casefold_group,
            max_missing=args.max_missing,
            max_missing_columns=missing_limits,
            top_n=args.top,
            max_duplicates=args.max_duplicates,
            min_complete_keys=args.min_complete_keys,
            min_distinct_keys=args.min_distinct_keys,
            max_distinct_keys=args.max_distinct_keys,
            max_duplicate_share=args.max_duplicate_share,
            max_incomplete_keys=args.max_incomplete_keys,
            max_incomplete_key_share=args.max_incomplete_key_share,
            min_rows=args.min_rows,
            max_rows=args.max_rows,
            max_group_share=args.max_group_share,
            max_assigned_group_share=args.max_assigned_group_share,
            max_missing_group_share=args.max_missing_group_share,
            min_distinct_groups=args.min_distinct_groups,
            max_distinct_groups=args.max_distinct_groups,
        )
    except (OSError, ValueError, LookupError, csv_error()) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(render(brief, args.json))
    return (
        1
        if (
            brief.failed_fields
            or brief.failed_duplicates
            or brief.failed_complete_keys
            or brief.failed_distinct_keys
            or brief.failed_max_distinct_keys
            or brief.failed_duplicate_share
            or brief.failed_incomplete_keys
            or brief.failed_incomplete_key_share
            or brief.failed_rows
            or brief.failed_max_rows
            or brief.failed_group_share
            or brief.failed_assigned_group_share
            or brief.failed_distinct_groups
            or brief.failed_max_distinct_groups
            or brief.failed_missing_group_share
        )
        else 0
    )


def csv_error() -> type[Exception]:
    import csv

    return csv.Error


if __name__ == "__main__":
    raise SystemExit(main())
