"""An absent CSV header is not a valid operational extract."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, read_csv

ROOT = Path(__file__).resolve().parents[1]


class HeaderlessExportTests(unittest.TestCase):
    def test_parsed_empty_input_is_rejected_by_library(self):
        for source in ("", "\n\n"):
            with self.subTest(source=repr(source)):
                parsed = read_csv(Path("-"), stdin=io.StringIO(source))
                with self.assertRaisesRegex(ValueError, "CSV has no header row"):
                    build_brief(parsed, ["order_id"])

    def test_default_cli_does_not_report_success_for_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            for source in ("", "\n\n"):
                with self.subTest(source=repr(source)):
                    path.write_text(source, encoding="utf-8")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "ops_field_brief",
                            str(path),
                            "--required",
                            "order_id",
                            "--json",
                        ],
                        cwd=ROOT,
                        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("CSV has no header row", completed.stderr)
                    self.assertEqual(completed.stdout, "")

    def test_empty_stdin_does_not_report_success(self):
        completed = subprocess.run(
            [sys.executable, "-m", "ops_field_brief", "-", "--required", "order_id"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            input="",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CSV has no header row", completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_header_only_export_and_explicit_api_schema_still_work(self):
        parsed = read_csv(Path("-"), stdin=io.StringIO("order_id\n"))
        brief = build_brief(parsed, ["order_id"])
        self.assertEqual(brief.rows, 0)
        self.assertEqual(brief.failed_fields, ())
        self.assertEqual(build_brief([], ["order_id"]).rows, 0)


if __name__ == "__main__":
    unittest.main()
