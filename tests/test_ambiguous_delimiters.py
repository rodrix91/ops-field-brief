"""Auto delimiter detection must never guess when two separators both fit."""

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
AMBIGUOUS = "id,buyer;city\n1,Ana;Tarija\n2,Luis;Salta\n"


class AmbiguousDelimiterTests(unittest.TestCase):
    def test_two_consistent_multicolumn_separators_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            _detect_delimiter(AMBIGUOUS)

    def test_ambiguous_stdin_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
            read_csv(Path("-"), delimiter=None, stdin=io.StringIO(AMBIGUOUS), strict=True)

    def test_ambiguous_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.csv"
            path.write_text(AMBIGUOUS, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
                read_csv(path, delimiter=None, strict=True)

    def test_ambiguous_cli_fails_without_a_misleading_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.csv"
            path.write_text(AMBIGUOUS, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, "-m", "ops_field_brief", str(path),
                    "--required", "id", "--delimiter", "auto", "--json",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not detect delimiter", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_explicit_delimiters_still_accept_intentionally_mixed_files(self) -> None:
        for selected, first_header in ((",", "id"), (";", "id,buyer")):
            with self.subTest(delimiter=selected):
                rows = read_csv(
                    Path("-"), delimiter=selected, stdin=io.StringIO(AMBIGUOUS), strict=True
                )
                self.assertEqual(rows.fieldnames[0], first_header)
                self.assertEqual(len(rows), 2)

    def test_unambiguous_semicolon_with_decimal_commas(self) -> None:
        rows = read_csv(
            Path("-"),
            delimiter=None,
            stdin=io.StringIO("sku;price\nA;10,5\nB;7,25\n"),
            strict=True,
        )
        self.assertEqual(rows.fieldnames, ("sku", "price"))
        self.assertEqual(rows[1]["price"], "7,25")

    def test_quoted_separators_do_not_make_a_unique_comma_file_ambiguous(self) -> None:
        text = 'name,notes\nAna,"a;b|c"\nLuis,"x;y"\n'
        self.assertEqual(_detect_delimiter(text), ",")

    def test_single_column_with_quoted_delimiters_still_works(self) -> None:
        self.assertEqual(_detect_delimiter('buyer\n"Andes, Norte"\n"Paz|Sur"\n'), ",")


if __name__ == "__main__":
    unittest.main()
