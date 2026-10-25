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

    def test_embedded_quoted_separators_are_one_column(self):
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO('buyer\n"Andes, Norte"\n"Paz|Sur"\n'),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("buyer",))
        self.assertEqual(rows, [{"buyer": "Andes, Norte"}, {"buyer": "Paz|Sur"}])

    def test_cli_local_file_strict_mode_and_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "buyers.csv"
            source.write_text("buyer\nAndes\nPaz\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "ops_field_brief", str(source),
                    "--required", "buyer", "--delimiter", "auto",
                    "--strict-csv", "--json",
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
