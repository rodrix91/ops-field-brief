"""Bound duplicate CSV header diagnostics while preserving exact validation."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

from ops_field_brief.brief import CsvRows, read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class BoundedDuplicateHeaderDiagnosticsTests(unittest.TestCase):
    def _error(self, *headers: str, casefold: bool = False) -> str:
        rows = CsvRows([], headers)
        with self.assertRaises(ValueError) as caught:
            validate_csv_structure(rows, casefold_headers=casefold)
        return str(caught.exception)

    def test_short_names_and_unicode_casefold_keep_existing_diagnostics(self) -> None:
        self.assertEqual(self._error("id", "id"), "duplicate CSV header columns: id")
        self.assertEqual(
            self._error("id", "ID", casefold=True),
            "duplicate CSV header columns: id",
        )
        self.assertEqual(
            self._error("Straße", "STRASSE", casefold=True),
            "duplicate CSV header columns: strasse",
        )

    def test_control_characters_and_bidi_formatting_are_escaped(self) -> None:
        for name in (
            "buyer\nregion",
            "buyer\rregion",
            "buyer\tregion",
            "buyer\x1b[31m",
            "buyer\u202eregion",
        ):
            with self.subTest(name=repr(name)):
                message = self._error(name, name)
                self.assertIn("duplicate CSV header columns:", message)
                self.assertIn(repr(name), message)
                for control in ("\n", "\r", "\t", "\x1b", "\u202e"):
                    self.assertNotIn(control, message)
                self.assertLess(len(message), 180)

    def test_long_plain_and_escaped_labels_remain_bounded(self) -> None:
        normal = "part-" + "A" * 50000
        escaped = "\x1b" * 200
        for name in (normal, escaped):
            with self.subTest(length=len(name)):
                message = self._error(name, name)
                self.assertIn("[truncated]", message)
                self.assertLess(len(message), 220)
                self.assertNotIn("\x1b", message)
                self.assertNotIn("A" * 500, message)
        # repr() expansion alone must be bounded, even below 80 input chars.
        short_controls = "\x1b" * 60
        output = self._error(short_controls, short_controls)
        self.assertIn("[truncated]", output)
        self.assertLess(len(output), 220)

    def test_many_duplicate_groups_are_summarized_in_input_order(self) -> None:
        headers = tuple(name for index in range(12) for name in (f"field{index}", f"field{index}"))
        message = self._error(*headers)
        self.assertEqual(
            message,
            "duplicate CSV header columns: field0, field1, field2 (+9 more)",
        )

    def test_multiline_quoted_csv_header_does_not_inject_cli_log_lines(self) -> None:
        csv_text = 'id,buyer,"region\nname","region\nname"\n1,Andes,2,3\n'
        rows = read_csv(Path("-"), stdin=io.StringIO(csv_text))
        message = self._error(*rows.fieldnames)
        self.assertIn(r"\n", message)
        self.assertNotIn("\n", message)

        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--required",
                "id,buyer",
                "--strict-csv",
            ],
            cwd=ROOT,
            env=env,
            input=csv_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(r"\n", result.stderr)
        self.assertEqual(result.stderr.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
