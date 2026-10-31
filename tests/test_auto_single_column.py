"""One-column auto detection must not weaken ambiguous CSV handling."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import _detect_delimiter, read_csv

ROOT = Path(__file__).resolve().parents[1]


class SingleColumnAutoDelimiterTests(unittest.TestCase):
    def test_library_reads_single_column_stdin(self):
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO("sku\nAB-101\nAB-102\n"),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("sku",))
        self.assertEqual(rows, [{"sku": "AB-101"}, {"sku": "AB-102"}])

    def test_blank_physical_lines_do_not_invalidate_one_column(self):
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO("sku\nAB-101\n\nAB-102\n"),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("sku",))
        self.assertEqual(rows, [{"sku": "AB-101"}, {"sku": "AB-102"}])

    def test_embedded_quoted_separators_are_one_column(self):
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO('buyer\n"Andes, Norte"\n\n"Paz|Sur"\n'),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("buyer",))
        self.assertEqual(rows, [{"buyer": "Andes, Norte"}, {"buyer": "Paz|Sur"}])

    def test_cli_file_blank_lines_are_strict_errors_but_keep_default_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "buyers.csv"
            source.write_text("buyer\nAndes\n\nPaz\n", encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(source),
                "--required",
                "buyer",
                "--delimiter",
                "auto",
                "--json",
            ]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            strict = subprocess.run(
                [*command, "--strict-csv"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            permissive = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(strict.returncode, 2)
        self.assertIn("blank CSV data row at source line 3", strict.stderr)
        self.assertEqual(strict.stdout, "")
        self.assertEqual(permissive.returncode, 0, permissive.stderr)
        report = json.loads(permissive.stdout)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["fields"][0]["filled"], 2)

    def test_cli_local_file_strict_mode_and_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "buyers.csv"
            source.write_text("buyer\nAndes\nPaz\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(source),
                    "--required",
                    "buyer",
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
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["fields"][0]["filled"], 2)

    def test_physically_blank_only_file_does_not_invent_header(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter("\n\n")

    def test_blank_lines_do_not_hide_inconsistent_multicolumn_content(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter("shipment|buyer\n\nS1\n")

    def test_long_quoted_stdin_field_beyond_sample_boundary(self):
        large = "x" * 9000
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO('buyer\n"' + large + '"\n'),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("buyer",))
        self.assertEqual(rows, [{"buyer": large}])

    def test_long_quoted_two_column_file_beyond_sample_boundary(self):
        large = "x" * 9000
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            path.write_text('buyer,shipment\n"' + large + '",S1\n', encoding="utf-8")
            rows = read_csv(path, delimiter=None, strict=True)
        self.assertEqual(rows.fieldnames, ("buyer", "shipment"))
        self.assertEqual(rows, [{"buyer": large, "shipment": "S1"}])

    def test_long_unterminated_quote_remains_rejected(self):
        large = "x" * 9000
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text('buyer\n"' + large, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
                read_csv(path, delimiter=None, strict=True)

    def test_short_ambiguous_stdin_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            read_csv(
                Path("-"),
                delimiter=None,
                stdin=io.StringIO("shipment|buyer\nS1\nS2\n"),
                strict=True,
            )

    def test_long_quoted_field_cli_strict_csv_counts_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            path.write_text('buyer\n"' + "x" * 9000 + '"\n', encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "buyer",
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
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["rows"], 1)
        self.assertEqual(report["fields"][0]["filled"], 1)

    def test_no_content_is_not_assumed_to_be_a_valid_column(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter("")

    def test_unbalanced_quoted_record_remains_invalid(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter('sku\n"unterminated\n')

    def test_inconsistent_multicolumn_sample_remains_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter("shipment|buyer\nS1\nS2\n")


if __name__ == "__main__":
    unittest.main()
