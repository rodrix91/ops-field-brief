"""Legacy carriage-return-only CSV is valid in auto mode and Excel exports."""

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


class CarriageReturnCsvTests(unittest.TestCase):
    def test_cr_only_auto_stdin_two_columns_and_real_line_numbers(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            strict=True,
            stdin=io.StringIO("id,buyer\rA1,Andes\rA2,Paz\r"),
        )
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual([row["buyer"] for row in rows], ["Andes", "Paz"])
        self.assertEqual(rows.source_lines, (2, 3))

    def test_cr_only_one_column_auto_stdin(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            strict=True,
            stdin=io.StringIO("buyer\rAndes\rPaz\r"),
        )
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("buyer",))
        self.assertEqual(rows, [{"buyer": "Andes"}, {"buyer": "Paz"}])

    def test_exact_excel_hints_with_cr_and_other_line_endings(self) -> None:
        for delimiter in (",", ";", "\t", "|"):
            for newline in ("\r", "\n", "\r\n"):
                with self.subTest(delimiter=delimiter, newline=repr(newline)):
                    data = f"sep={delimiter}{newline}id{delimiter}buyer"
                    self.assertEqual(
                        _excel_sep_directive(data),
                        (delimiter, f"id{delimiter}buyer"),
                    )

    def test_cr_only_hint_strips_utf8_bom_on_stdin(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            strict=True,
            stdin=io.StringIO("\ufeffsep=;\rid;buyer\rA1;Andes\rA2;Paz\r"),
        )
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(
            rows,
            [
                {"id": "A1", "buyer": "Andes"},
                {"id": "A2", "buyer": "Paz"},
            ],
        )
        self.assertEqual(rows.source_lines, (3, 4))

    def test_cr_only_regular_and_gzip_excel_files(self) -> None:
        raw = "sep=;\rid;buyer\rA1;Andes\rA2;Paz\r".encode("utf-8-sig")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for compressed in (False, True):
                with self.subTest(compressed=compressed):
                    path = root / ("data.csv.gz" if compressed else "data.csv")
                    path.write_bytes(gzip.compress(raw) if compressed else raw)
                    rows = read_csv(path, delimiter=None, strict=True)
                    validate_csv_structure(rows)
                    self.assertEqual(rows.fieldnames, ("id", "buyer"))
                    self.assertEqual(rows.source_lines, (3, 4))
                    self.assertEqual([row["buyer"] for row in rows], ["Andes", "Paz"])

    def test_cr_only_multiline_quoted_field_with_strict_error(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            strict=True,
            stdin=io.StringIO('sep=;\rid;buyer\rA1;"North\rSouth"\rA2\r'),
        )
        self.assertEqual(rows.source_lines, (3, 5))
        self.assertEqual(rows[0]["buyer"], "North\rSouth")
        with self.assertRaises(ValueError) as caught:
            validate_csv_structure(rows)
        self.assertEqual(
            str(caught.exception),
            "CSV data row 2 has fewer fields than the header (source line 5)",
        )

    def test_cr_only_excel_hint_lookalikes_are_not_directives(self) -> None:
        for text in ("SEP=;\rid;buyer", "sep=;extra\rid;buyer", "sep=: \rid:buyer"):
            with self.subTest(text=text):
                self.assertIsNone(_excel_sep_directive(text))

    def test_cr_only_file_cli_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            path.write_bytes(b"sep=;\rorder_id;buyer\rA1;Andes\rA2;Paz\r")
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
        self.assertEqual(report["duplicate_keys"], 0)
        self.assertEqual(report["fields"][0]["filled"], 2)


if __name__ == "__main__":
    unittest.main()
