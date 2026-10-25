"""Regression checks for malformed quoting in opt-in strict CSV parsing."""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv

ROOT = Path(__file__).resolve().parents[1]


class StrictCsvQuotingTests(unittest.TestCase):
    def test_strict_rejects_unclosed_and_bad_closing_quotes(self):
        cases = (
            'id,buyer\n1,"Andes\n',
            'id,buyer\n1,"Andes"oops\n',
        )
        for source in cases:
            with self.subTest(source=source):
                permissive = read_csv(Path("-"), stdin=io.StringIO(source))
                self.assertEqual(len(permissive), 1)
                with self.assertRaises(csv.Error):
                    read_csv(Path("-"), stdin=io.StringIO(source), strict=True)

    def test_valid_multiline_quoted_value_still_passes(self):
        source = 'id,buyer\n1,"Andes\nNorte"\n'
        rows = read_csv(Path("-"), stdin=io.StringIO(source), strict=True)
        self.assertEqual(rows[0]["buyer"], "Andes\nNorte")

    def test_cli_strict_rejects_invalid_quotes_without_changing_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text('id,buyer\n1,"Andes"oops\n', encoding="utf-8")
            default = self._run(str(path))
            strict = self._run(str(path), "--strict-csv")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(strict.returncode, 2)
        self.assertIn("expected after", strict.stderr)
        self.assertFalse(strict.stdout.strip())

    def test_cli_stdin_strict_rejects_unterminated_quote(self):
        run = self._run("-", "--strict-csv", source='id,buyer\n1,"Andes\n')
        self.assertEqual(run.returncode, 2)
        self.assertIn("unexpected end of data", run.stderr)

    @staticmethod
    def _run(
        path: str, *args: str, source: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        return subprocess.run(
            [sys.executable, "-m", "ops_field_brief", path, "--required", "id,buyer", *args],
            cwd=ROOT,
            env=env,
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
