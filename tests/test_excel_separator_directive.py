"""Excel sep= directives work with auto delimiter detection, never as a CSV header."""

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


class ExcelSeparatorDirectiveTests(unittest.TestCase):
    def test_exact_supported_hints_and_line_endings(self) -> None:
        for delimiter in (",", ";", "\t", "|"):
            for spelling in ("sep=", "SEP=", "Sep=", "sEp="):
                for ending in ("\n", "\r\n", "\r", ""):
                    with self.subTest(
                        delimiter=delimiter, spelling=spelling, ending=repr(ending)
                    ):
                        self.assertEqual(
                            _excel_sep_directive(
                                f"{spelling}{delimiter}{ending}id{delimiter}buyer"
                            ),
                            (delimiter, f"id{delimiter}buyer") if ending else None,
                        )
        self.assertEqual(_excel_sep_directive("SEP=;"), (";", ""))

    def test_similar_first_lines_are_not_directives(self) -> None:
        for text in ("sép=;\nid;buyer", "sep=: \nid:buyer", "sep=;extra\nid;buyer", ""):
            with self.subTest(text=text):
                self.assertIsNone(_excel_sep_directive(text))

    def test_mixed_case_hint_works_for_stdin_files_and_gzip(self) -> None:
        text = "SeP=;\r\nid;buyer\r\nA1;Andes\r\nA2;Paz\r\n"
        with tempfile.TemporaryDirectory() as directory:
            for source in ("stdin", "file", "gzip"):
                with self.subTest(source=source):
                    path = Path(directory) / (
                        "mixed.csv.gz" if source == "gzip" else "mixed.csv"
                    )
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
                    self.assertEqual(rows.fieldnames, ("id", "buyer"))
                    self.assertEqual([row["buyer"] for row in rows], ["Andes", "Paz"])
                    self.assertEqual(rows.source_lines, (3, 4))

    def test_mixed_case_hint_is_not_skipped_with_explicit_delimiter(self) -> None:
        source = "SeP=;\nid;buyer\nA1;Andes\n"
        rows = read_csv(Path("-"), delimiter=";", stdin=io.StringIO(source))
        self.assertEqual(rows.fieldnames, ("SeP=", ""))
        with self.assertRaisesRegex(ValueError, "blank CSV header"):
            validate_csv_structure(rows)

    def test_malformed_mixed_case_hints_remain_normal_csv(self) -> None:
        for source in ("SEP=;;\nid;buyer\n", "Sep=: \nid:buyer\n", "SEP=x\nid;buyer\n"):
            with self.subTest(source=source):
                self.assertIsNone(_excel_sep_directive(source))

    def test_stdin_auto_uses_declared_delimiter_and_strips_bom(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            strict=True,
            stdin=io.StringIO("\ufeffsep=;\r\nid;buyer\r\nA1;Andes\r\nA2;Paz\r\n"),
        )
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(rows, [{"id": "A1", "buyer": "Andes"}, {"id": "A2", "buyer": "Paz"}])

    def test_stdin_auto_with_header_only_preserves_header(self) -> None:
        rows = read_csv(
            Path("-"), delimiter=None, strict=True, stdin=io.StringIO("sep=|\nid|buyer\n")
        )
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(rows, [])

    def test_standalone_directive_has_no_csv_header(self) -> None:
        rows = read_csv(Path("-"), delimiter=None, stdin=io.StringIO("sep=;"))
        self.assertEqual(rows.fieldnames, ())
        with self.assertRaisesRegex(ValueError, "no header"):
            validate_csv_structure(rows)

    def test_regular_and_gzip_files_honor_excel_hint(self) -> None:
        text = "sep=;\r\nid;buyer\r\nA1;Andes\r\nA2;Paz\r\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for compressed in (False, True):
                with self.subTest(compressed=compressed):
                    path = root / ("sales.CSV.GZ" if compressed else "sales.csv")
                    raw = text.encode("utf-8-sig")
                    path.write_bytes(gzip.compress(raw) if compressed else raw)
                    rows = read_csv(path, delimiter=None, strict=True)
                    validate_csv_structure(rows)
                    self.assertEqual(rows.fieldnames, ("id", "buyer"))
                    self.assertEqual([row["buyer"] for row in rows], ["Andes", "Paz"])

    def test_explicit_delimiter_does_not_skip_excel_hint(self) -> None:
        rows = read_csv(Path("-"), delimiter=";", stdin=io.StringIO("sep=;\nid;buyer\nA1;Andes\n"))
        self.assertEqual(rows.fieldnames, ("sep=", ""))
        with self.assertRaisesRegex(ValueError, "blank CSV header at column 2"):
            validate_csv_structure(rows)

    def test_real_cli_auto_uses_correct_header_and_key_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("Sep=;\norder_id;buyer\nA1;Andes\nA2;Paz\n", encoding="utf-8")
            result = subprocess.run(
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
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["key"], "order_id")
        self.assertEqual(report["duplicate_keys"], 0)
        self.assertEqual(report["fields"][0]["filled"], 2)


if __name__ == "__main__":
    unittest.main()
