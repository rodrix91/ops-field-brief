"""Fail closed on omitted required columns in CLI quality gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MalformedRequiredFieldTests(unittest.TestCase):
    def test_empty_required_slots_fail_without_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            path.write_text("shipment,buyer,eta\nS1,Andes,2026-10-25\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            for required in (
                "shipment,,eta",
                ",shipment,eta",
                "shipment,eta,",
                "shipment, ,eta",
            ):
                with self.subTest(required=required):
                    proc = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "ops_field_brief",
                            str(path),
                            "--required",
                            required,
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertIn("empty column in --required", proc.stderr)
                    self.assertFalse(proc.stdout)

    def test_trimmed_distinct_required_fields_still_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            path.write_text("shipment,buyer\nS1,Andes\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    " shipment , buyer ",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        fields = json.loads(proc.stdout)["fields"]
        self.assertEqual([field["name"] for field in fields], ["shipment", "buyer"])
        self.assertEqual([field["filled"] for field in fields], [1, 1])


if __name__ == "__main__":
    unittest.main()
