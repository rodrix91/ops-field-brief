"""Duplicate-key gates must not silently pass without a business key."""

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


class DuplicateGateRequiresKeyTests(unittest.TestCase):
    def test_library_rejects_duplicate_gate_without_key(self):
        rows = [{"shipment": "S1"}, {"shipment": "S1"}]
        with self.assertRaisesRegex(ValueError, "max_duplicates requires --key"):
            build_brief(rows, ["shipment"], max_duplicates=0)

    def test_library_keeps_valid_keyed_duplicate_gate(self):
        rows = [{"shipment": "S1"}, {"shipment": "S1"}]
        report = build_brief(rows, ["shipment"], key="shipment", max_duplicates=0)
        self.assertEqual(report.duplicate_keys, 1)
        self.assertTrue(report.failed_duplicates)

    def test_cli_rejects_gate_without_key_and_emits_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate-orders.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS1,Paz\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            cmd = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment",
                "--max-duplicates",
                "0",
                "--json",
            ]
            invalid = subprocess.run(
                cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False
            )
            valid = subprocess.run(
                [*cmd, "--key", "shipment"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("max_duplicates requires --key", invalid.stderr)
        self.assertEqual(invalid.stdout, "")
        self.assertEqual(valid.returncode, 1, valid.stderr)
        report = json.loads(valid.stdout)
        self.assertEqual(report["duplicate_keys"], 1)
        self.assertTrue(report["failed_duplicates"])


if __name__ == "__main__":
    unittest.main()
