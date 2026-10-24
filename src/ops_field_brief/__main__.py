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
    parser.add_argument("--group", help="Column to rank by row count")
    parser.add_argument(
        "--max-missing",
        type=float,
        default=0.0,
        help="Fail if a required field is missing more than this share (0 to 1)",
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
        "--max-incomplete-keys",
        type=int,
        default=None,
        help="Fail when more than N rows have an empty component in the --key value",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=None,
        help="Fail if the CSV has fewer than this many data rows",
    )
    parser.add_argument(
        "--max-group-share",
        type=float,
        default=None,
        help="Fail if the largest --group value exceeds this share of rows (0 to 1)",
    )
    parser.add_argument(
        "--strict-csv",
        action="store_true",
        help="Reject duplicate/blank headers and rows with too many or too few fields",
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
    required = [part.strip() for part in args.required.split(",") if part.strip()]
    if not required:
        print("at least one required field is needed", file=sys.stderr)
        return 2
    key_fields = None
    if args.key is not None:
        key_fields = [part.strip() for part in args.key.split(",") if part.strip()]
        if not key_fields:
            print("at least one key field is needed", file=sys.stderr)
            return 2
    try:
        rows = read_csv(
            args.csv,
            delimiter=None if args.delimiter == "auto" else DELIMITERS[args.delimiter],
            encoding=args.encoding,
            stdin=_decoded_stdin(args.encoding) if str(args.csv) == "-" else None,
        )
        if args.strict_csv:
            validate_csv_structure(rows)
        brief = build_brief(
            rows,
            required,
            key_fields=key_fields,
            group=args.group,
            max_missing=args.max_missing,
            top_n=args.top,
            max_duplicates=args.max_duplicates,
            max_incomplete_keys=args.max_incomplete_keys,
            min_rows=args.min_rows,
            max_group_share=args.max_group_share,
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
            or brief.failed_incomplete_keys
            or brief.failed_rows
            or brief.failed_group_share
        )
        else 0
    )


def csv_error() -> type[Exception]:
    import csv

    return csv.Error


if __name__ == "__main__":
    raise SystemExit(main())
