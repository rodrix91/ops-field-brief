"""Repeated business-key components must not appear as independent fields."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief

ROOT = Path(__file__).resolve().parents[1]


class DuplicateKeyFieldTests(unittest.TestCase):
    def test_library_rejects_duplicate_key_fields(self):
        rows = [{"order": "O1", "line": "1"}]
        for fields in (["order", "order"], ["order", "line", "order"]):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, "duplicate key fields: order"):
                    build_brief(rows, ["order"], key_fields=fields)

    def test_valid_composite_key_retains_distinct_components(self):
        rows = [
            {"order": "O1", "line": "1"},
            {"order": "O1", "line": "2"},
            {"order": "O1", "line": "1"},
        ]
        brief = build_brief(rows, ["order"], key_fields=["order", "line"])
        self.assertEqual(brief.key_fields, ("order", "line"))
        self.assertEqual(brief.duplicate_keys, 1)

    def test_cli_rejects_duplicate_key_without_emitting_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("order,line\nO1,1\nO1,2\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            for key in ("order,order", "order,line,order"):
                with self.subTest(key=key):
                    proc = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "ops_field_brief",
                            str(path),
                            "--required",
                            "order",
                            "--key",
                            key,
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertIn("duplicate key fields: order", proc.stderr)
                    self.assertFalse(proc.stdout)

    def test_cli_valid_composite_key_still_counts_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("order,line\nO1,1\nO1,2\nO1,1\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "order",
                    "--key",
                    "order,line",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["key_fields"], ["order", "line"])
        self.assertEqual(payload["duplicate_keys"], 1)


if __name__ == "__main__":
    unittest.main()
