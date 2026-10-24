"""Regression tests for opt-in structural validation of operational CSV files."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class StrictCsvTests(unittest.TestCase):
    def _rows(self, source: str, delimiter: str | None = ","):
        return read_csv(Path("-"), delimiter=delimiter, stdin=io.StringIO(source))

    def _cli(self, path: str, *options: str, input_text: str | None = None):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ops_field_brief", path, "--required", "id,buyer", *options],
            cwd=ROOT,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_valid_csv_accepts_quoted_delimiter_and_empty_cells(self):
        rows = self._rows('id,buyer\n1,"Andes, Norte"\n2,\n')
        validate_csv_structure(rows)
        self.assertEqual(rows[0]["buyer"], "Andes, Norte")
        self.assertEqual(rows[1]["buyer"], "")

    def test_header_only_is_valid_but_no_header_is_not(self):
        validate_csv_structure(self._rows("id,buyer\n"))
        with self.assertRaisesRegex(ValueError, "no header"):
            validate_csv_structure(self._rows(""))

    def test_rejects_ambiguous_headers(self):
        cases = (
            ("id,id\n1,2\n", "duplicate CSV header columns: id"),
            ("id, id\n1,2\n", "duplicate CSV header columns: id"),
            ("id,buyer,\n1,Andes,\n", "blank CSV header at column 3"),
        )
        for source, message in cases:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, message):
                    validate_csv_structure(self._rows(source))

    def test_rejects_ragged_rows_with_logical_row_number(self):
        cases = (
            ("id,buyer\n1,Andes\n2,Paz,extra\n", "row 2 has more fields"),
            ("id,buyer\n1,Andes\n2\n", "row 2 has fewer fields"),
        )
        for source, message in cases:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, message):
                    validate_csv_structure(self._rows(source))

    def test_cli_strict_mode_rejects_ragged_file_without_breaking_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ragged.csv"
            path.write_text("id,buyer\n1,Andes,extra\n", encoding="utf-8")
            strict = self._cli(str(path), "--strict-csv")
            permissive = self._cli(str(path))
        self.assertEqual(strict.returncode, 2)
        self.assertIn("more fields", strict.stderr)
        self.assertEqual(permissive.returncode, 0, permissive.stderr)
        self.assertIn("Rows: 1", permissive.stdout)

    def test_cli_stdin_supports_strict_mode_and_bom(self):
        good = self._cli("-", "--strict-csv", input_text="\ufeffid,buyer\n1,Andes\n")
        bad = self._cli(
            "-",
            "--strict-csv",
            "--delimiter",
            "semicolon",
            input_text="id;buyer\n1;Andes;extra\n",
        )
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("more fields", bad.stderr)


if __name__ == "__main__":
    unittest.main()
