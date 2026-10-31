"""Physical CSV source lines are retained for strict row-width failures."""

from __future__ import annotations

import gzip
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import CsvRows, read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class StrictCsvSourceLineTests(unittest.TestCase):
    def test_multiline_data_and_header_preserve_real_source_positions(self) -> None:
        cases = (
            (
                'id,buyer\n1,"North\nSouth"\n2,Andes,extra\n',
                "CSV data row 2 has more fields than the header (source line 4)",
            ),
            (
                'id,"buyer\nname"\n1,"North\nSouth"\n2\n',
                "CSV data row 2 has fewer fields than the header (source line 5)",
            ),
            (
                "id,buyer\n\n1,Andes\n\n2\n",
                "CSV data row 2 has fewer fields than the header (source line 5)",
            ),
            (
                'id,buyer\n1,Andes,"extra\ntext"\n',
                "CSV data row 1 has more fields than the header (source line 2)",
            ),
            (
                'id,buyer\r\n1,"North\r\nSouth"\r\n2\r\n',
                "CSV data row 2 has fewer fields than the header (source line 4)",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                rows = read_csv(Path("-"), stdin=io.StringIO(source))
                with self.assertRaisesRegex(ValueError, "source line") as caught:
                    validate_csv_structure(rows)
                self.assertEqual(str(caught.exception), expected)

    def test_excel_separator_hint_counts_as_physical_source_line(self) -> None:
        source = 'sep=;\nid;buyer\n1;"North\nSouth"\n2\n'
        rows = read_csv(Path("-"), delimiter=None, stdin=io.StringIO(source))
        self.assertEqual(rows.source_lines, (3, 5))
        with self.assertRaisesRegex(ValueError, "source line 5"):
            validate_csv_structure(rows)

    def test_gzip_excel_crlf_source_line_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regional.csv.gz"
            source = 'sep=;\r\nid;buyer\r\n1;"North\r\nSouth"\r\n2\r\n'
            path.write_bytes(gzip.compress(source.encode("utf-8-sig")))
            rows = read_csv(path, delimiter=None)
        self.assertEqual(rows.source_lines, (3, 5))
        with self.assertRaisesRegex(ValueError, "source line 5"):
            validate_csv_structure(rows)

    def test_direct_csvrows_keep_logical_numbers(self) -> None:
        rows = CsvRows(
            [{"id": "1", "buyer": "ok"}, {"id": "2", "buyer": None}],
            ["id", "buyer"],
        )
        self.assertEqual(rows.source_lines, ())
        with self.assertRaises(ValueError) as caught:
            validate_csv_structure(rows)
        self.assertEqual(str(caught.exception), "CSV data row 2 has fewer fields than the header")

    def test_strict_rejects_skipped_blank_rows_across_line_endings(self) -> None:
        cases = (
            ("between", "id,buyer\n1,Andes\n\n2,Paz\n", 3, 2),
            ("before first record", "id,buyer\n\n1,Andes\n", 2, 1),
            ("trailing", "id,buyer\n1,Andes\n\n", 3, 1),
            ("header only with blank", "id,buyer\n\n", 2, 0),
            ("after multiline header", 'id,"buyer\nname"\n1,Andes\n\n2,Paz\n', 4, 2),
        )
        for name, content, line, count in cases:
            for ending in ("\n", "\r\n", "\r"):
                with self.subTest(case=name, ending=repr(ending)):
                    source = content.replace("\n", ending)
                    rows = read_csv(Path("-"), stdin=io.StringIO(source), strict=True)
                    self.assertEqual(len(rows), count)
                    self.assertIn(line, rows.blank_source_lines)
                    with self.assertRaises(ValueError) as captured:
                        validate_csv_structure(rows)
                    self.assertEqual(
                        str(captured.exception),
                        f"blank CSV data row at source line {line}",
                    )

    def test_embedded_blank_line_inside_quoted_field_is_not_skipped(self) -> None:
        for ending in ("\n", "\r\n", "\r"):
            with self.subTest(ending=repr(ending)):
                source = 'id,buyer\n1,"North\n\nSouth"\n2,Paz\n'.replace("\n", ending)
                rows = read_csv(Path("-"), stdin=io.StringIO(source), strict=True)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows.blank_source_lines, ())
                validate_csv_structure(rows)

    def test_excel_directive_and_gzip_report_real_blank_source_line(self) -> None:
        source = "sep=;\r\nid;buyer\r\n1;Andes\r\n\r\n2;Paz\r\n"
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "orders.csv"
            zipped = Path(directory) / "orders.csv.gz"
            plain.write_bytes(source.encode("utf-8-sig"))
            zipped.write_bytes(gzip.compress(source.encode("utf-8-sig")))
            for path in (plain, zipped):
                with self.subTest(path=path.suffix):
                    rows = read_csv(path, delimiter=None, strict=True)
                    self.assertEqual(rows.blank_source_lines, (4,))
                    with self.assertRaisesRegex(ValueError, "blank CSV data row at source line 4"):
                        validate_csv_structure(rows)

    def test_cli_opt_in_rejects_blank_records_legacy_mode_keeps_counts(self) -> None:
        source = "id,buyer\n1,Andes\n\n2,Paz\n"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        base = [sys.executable, "-m", "ops_field_brief", "-", "--required", "id,buyer"]
        strict = subprocess.run(
            [*base, "--strict-csv"], cwd=ROOT, env=env, input=source,
            capture_output=True, text=True, check=False,
        )
        default = subprocess.run(
            base, cwd=ROOT, env=env, input=source,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(strict.returncode, 2)
        self.assertIn("blank CSV data row at source line 3", strict.stderr)
        self.assertEqual(strict.stdout, "")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertIn("Rows: 2", default.stdout)

    def test_cli_reports_physical_line_without_traceback(self) -> None:
        source = 'id,buyer\n1,"North\nSouth"\n2,Andes,extra\n'
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--strict-csv",
                "--required",
                "id,buyer",
            ],
            cwd=ROOT,
            env=env,
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("CSV data row 2 has more fields", result.stderr)
        self.assertIn("(source line 4)", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(result.stdout)


if __name__ == "__main__":
    unittest.main()
