"""Command line for an operational field brief."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ops_field_brief.brief import DELIMITERS, build_brief, read_csv, render


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report fill rate, repeated business keys, and top groups in a CSV."
    )
    parser.add_argument("csv", type=Path, help="CSV with a header row")
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
    parser.add_argument("--key", help="Business key that should not repeat")
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
        choices=sorted(DELIMITERS),
        default="comma",
        help="Field separator. Default comma keeps the original behavior.",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON instead of Markdown")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    required = [part.strip() for part in args.required.split(",") if part.strip()]
    if not required:
        print("at least one required field is needed", file=sys.stderr)
        return 2
    try:
        rows = read_csv(
            args.csv,
            delimiter=DELIMITERS[args.delimiter],
            encoding=args.encoding,
        )
        brief = build_brief(
            rows,
            required,
            key=args.key,
            group=args.group,
            max_missing=args.max_missing,
            top_n=args.top,
        )
    except (OSError, ValueError, LookupError, csv_error()) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(render(brief, args.json))
    return 1 if brief.failed_fields else 0


def csv_error() -> type[Exception]:
    import csv

    return csv.Error


if __name__ == "__main__":
    raise SystemExit(main())
