"""Double-quoted Excel separator hints are exact auto-mode preambles."""

from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import _excel_sep_directive, read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class QuotedExcelSeparatorTests(unittest.TestCase):
    def test_exact_quoted_and_unquoted_hints_accept_all_delimiters_and_endings(self) -> None:
        for delimiter in (",", ";", "\t", "|"):
            for spelling in ("sep=", "SEP=", "SeP="):
                for quoted in (False, True):
                    first = f"{spelling}{delimiter}"
                    if quoted:
                        first = f'"{first}"'
                    for newline in ("\n", "\r\n", "\r"):
                        with self.subTest(first=first, newline=repr(newline)):
                            rest = f"id{delimiter}buyer"
                            self.assertEqual(
                                _excel_sep_directive(first + newline + rest),
                                (delimiter, rest),
                            )
                    self.assertEqual(_excel_sep_directive(first), (delimiter, ""))

    def test_near_misses_remain_data_not_directives(self) -> None:
        for text in (
            '"sep=;x\nid;buyer',
            "sep=;xx\nid;buyer",
            '"sep=;;"\nid;buyer',
            '"sep=;"extra\nid;buyer',
            'sep=;"\nid;buyer',
            '"sep=x"\nid;buyer',
            '"sep=;" "ignored"\nid;buyer',
            "'sep=;'\nid;buyer",
        ):
            with self.subTest(text=text):
                self.assertIsNone(_excel_sep_directive(text))

    def test_quoted_hint_from_stdin_plain_and_gzip_keeps_physical_lines(self) -> None:
        text = '"SeP=;"\r\norder_id;buyer\r\nA1;Andes\r\nA2;Paz\r\n'
        with tempfile.TemporaryDirectory() as dirname:
            for source in ("stdin", "plain", "gzip"):
                with self.subTest(source=source):
                    path = Path(dirname) / ("orders.csv.gz" if source == "gzip" else "orders.csv")
                    if source != "stdin":
                        raw = text.encode("utf-8-sig")
                        path.write_bytes(gzip.compress(raw) if source == "gzip" else raw)
                    rows = (
                        read_csv(
                            Path("-"),
                            delimiter=None,
                            strict=True,
                            stdin=io.StringIO("\ufeff" + text),
                        )
                        if source == "stdin"
                        else read_csv(path, delimiter=None, strict=True)
                    )
                    validate_csv_structure(rows)
                    self.assertEqual(rows.fieldnames, ("order_id", "buyer"))
                    self.assertEqual(rows.source_lines, (3, 4))
                    self.assertEqual([r["buyer"] for r in rows], ["Andes", "Paz"])

    def test_cr_only_quoted_directive_preserves_multiline_error_line(self) -> None:
        source = '"SEP=;"\rorder_id;buyer\rA1;"North\rSouth"\rA2\r'
        rows = read_csv(Path("-"), delimiter=None, strict=True, stdin=io.StringIO(source))
        self.assertEqual(rows.source_lines, (3, 5))
        with self.assertRaisesRegex(ValueError, "source line 5"):
            validate_csv_structure(rows)

    def test_explicit_delimiter_never_skips_quoted_hint(self) -> None:
        source = '"sep=;"\norder_id;buyer\nA1;Andes\n'
        rows = read_csv(Path("-"), delimiter=";", stdin=io.StringIO(source), strict=True)
        self.assertEqual(rows.fieldnames, ("sep=;",))
        with self.assertRaisesRegex(ValueError, "more fields than the header"):
            validate_csv_structure(rows)

    def test_quoted_hint_without_header_still_fails_strict_validation(self) -> None:
        for text in ('"sep=;"', '"sep=;"\n'):
            with self.subTest(text=text):
                rows = read_csv(Path("-"), delimiter=None, stdin=io.StringIO(text))
                self.assertEqual(rows.fieldnames, ())
                with self.assertRaisesRegex(ValueError, "no header"):
                    validate_csv_structure(rows)

    def test_real_cli_recognizes_quoted_excel_hint(self) -> None:
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "orders.csv"
            path.write_text(
                '"SEP=;"\norder_id;buyer\nA1;Andes\nA2;Paz\n',
                encoding="utf-8",
            )
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "order_id,buyer",
                    "--key",
                    "order_id",
                    "--max-duplicates",
                    "0",
                    "--delimiter",
                    "auto",
                    "--strict-csv",
                    "--json",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["duplicate_keys"], 0)
        self.assertEqual(report["fields"][0]["filled"], 2)


if __name__ == "__main__":
    unittest.main()
