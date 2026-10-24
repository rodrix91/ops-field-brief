"""Reject malformed composite business-key selection rather than silently dropping columns."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MalformedCompositeKeyTests(unittest.TestCase):
    def test_empty_slot_in_composite_key_returns_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("order,line\nO1,1\nO1,2\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            for key in ("order,,line", ",order,line", "order,line,", "order, ,line"):
                with self.subTest(key=key):
                    run = subprocess.run(
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
                    self.assertEqual(run.returncode, 2, run.stderr)
                    self.assertIn("empty column in --key", run.stderr)
                    self.assertFalse(run.stdout.strip())

    def test_well_formed_composite_key_still_uses_every_component(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("order,line\nO1,1\nO1,2\nO1,1\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "order",
                    "--key",
                    " order , line ",
                    "--max-duplicates",
                    "0",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(run.returncode, 1, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["key_fields"], ["order", "line"])
        self.assertEqual(report["duplicate_keys"], 1)
        self.assertTrue(report["failed_duplicates"])


if __name__ == "__main__":
    unittest.main()
