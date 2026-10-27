"""Protect the documented Excel sep= operations quickstart against regressions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "orders-excel-sep.csv"


class ExcelExampleTests(unittest.TestCase):
    def test_real_example_parses_with_auto_separator(self) -> None:
        rows = read_csv(SAMPLE, delimiter=None, strict=True)
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("order_id", "buyer", "eta"))
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["order_id"] for r in rows], ["O-001", "O-002", "O-003", "O-004"])
        self.assertEqual(rows[2]["eta"], "")

    def test_documented_cli_command_passes_quality_gates(self) -> None:
        command = [
            sys.executable,
            "-m",
            "ops_field_brief",
            "examples/orders-excel-sep.csv",
            "--required",
            "order_id,buyer",
            "--key",
            "order_id",
            "--max-duplicates",
            "0",
            "--group",
            "buyer",
            "--delimiter",
            "auto",
            "--strict-csv",
            "--json",
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["rows"], 4)
        self.assertEqual(data["duplicate_keys"], 0)
        self.assertEqual(data["key"], "order_id")
        self.assertEqual(data["failed_fields"], [])
        self.assertEqual([(x["name"], x["filled"]) for x in data["fields"]], [
            ("order_id", 4),
            ("buyer", 4),
        ])

    def test_explicit_separator_does_not_consume_directive(self) -> None:
        rows = read_csv(SAMPLE, delimiter=";", strict=True)
        self.assertEqual(rows.fieldnames, ("sep=", ""))
        with self.assertRaisesRegex(ValueError, "blank CSV header"):
            validate_csv_structure(rows)


if __name__ == "__main__":
    unittest.main()
