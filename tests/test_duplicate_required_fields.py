"""Duplicated requested columns must not inflate operational fill counts."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief

ROOT = Path(__file__).resolve().parents[1]


class DuplicateRequiredFieldsTests(unittest.TestCase):
    def test_library_rejects_duplicate_required_fields(self):
        rows = [{"shipment": "S1", "buyer": "Andes"}]
        with self.assertRaisesRegex(ValueError, "duplicate required fields: buyer"):
            build_brief(rows, ["shipment", "buyer", "buyer"])
        with self.assertRaisesRegex(ValueError, "duplicate required fields: shipment, buyer"):
            build_brief(rows, ["shipment", "buyer", "shipment", "buyer"])

    def test_distinct_required_fields_retain_expected_counts(self):
        brief = build_brief(
            [{"shipment": "S1", "buyer": "Andes"}, {"shipment": "S2", "buyer": ""}],
            ["shipment", "buyer"],
            max_missing=0.5,
        )
        self.assertEqual(brief.rows, 2)
        self.assertEqual(
            [(f.name, f.filled, f.missing) for f in brief.fields],
            [
                ("shipment", 2, 0),
                ("buyer", 1, 1),
            ],
        )
        self.assertFalse(brief.failed_fields)

    def test_cli_rejects_duplicate_required_fields_before_reporting(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "data.csv"
            file.write_text("shipment,buyer\nS1,Andes\nS2,Paz\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(file),
                    "--required",
                    "shipment,buyer,buyer",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate required fields: buyer", result.stderr)
        self.assertFalse(result.stdout)


if __name__ == "__main__":
    unittest.main()
