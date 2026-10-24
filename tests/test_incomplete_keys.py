"""Regression tests for the opt-in incomplete business-key quality gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, render

ROOT = Path(__file__).resolve().parents[1]


class IncompleteKeyTests(unittest.TestCase):
    def test_composite_key_counts_incomplete_rows_without_changing_duplicate_logic(self):
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "B", "line": ""},
            {"order": "", "line": "9"},
            {"order": "C", "line": "3"},
        ]
        kwargs = {
            "key_fields": ["order", "line"],
            "max_missing": 1.0,
            "max_duplicates": 1,
        }
        passing = build_brief(rows, ["order"], max_incomplete_keys=2, **kwargs)
        self.assertEqual(passing.incomplete_key_rows, 2)
        self.assertEqual(passing.duplicate_keys, 1)
        self.assertFalse(passing.failed_incomplete_keys)
        self.assertFalse(passing.failed_duplicates)
        self.assertEqual(passing.to_dict()["max_incomplete_keys"], 2)
        self.assertFalse(passing.to_dict()["failed_incomplete_keys"])

        failing = build_brief(rows, ["order"], max_incomplete_keys=1, **kwargs)
        self.assertTrue(failing.failed_incomplete_keys)
        self.assertEqual(failing.duplicate_keys, 1)
        report = render(failing, as_json=False)
        self.assertIn("Rows with incomplete business keys: 2", report)
        self.assertIn("Failed incomplete-key check", report)
        self.assertIn("exceed the limit (1)", report)

    def test_optional_gate_preserves_default_ungated_behavior(self):
        rows = [{"shipment": "S1"}, {"shipment": " "}]
        plain = build_brief(rows, ["shipment"], key="shipment", max_missing=1.0)
        self.assertEqual(plain.incomplete_key_rows, 1)
        self.assertIsNone(plain.max_incomplete_keys)
        self.assertFalse(plain.failed_incomplete_keys)
        self.assertEqual(plain.duplicate_keys, 0)
        self.assertIn("Rows with incomplete business keys: 1", render(plain, False))

        without_key = build_brief([{"shipment": "S1"}], ["shipment"])
        self.assertEqual(without_key.incomplete_key_rows, 0)
        self.assertNotIn("incomplete business keys", render(without_key, False))

    def test_threshold_requires_key_and_nonnegative_limit(self):
        with self.assertRaisesRegex(ValueError, "requires --key"):
            build_brief([{"shipment": "S1"}], ["shipment"], max_incomplete_keys=0)
        with self.assertRaisesRegex(ValueError, "0 or greater"):
            build_brief(
                [{"shipment": "S1"}],
                ["shipment"],
                key="shipment",
                max_incomplete_keys=-1,
            )

    def test_header_only_csv_can_pass_zero_incomplete_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.csv"
            path.write_text("shipment,buyer\n", encoding="utf-8")
            completed = self._run(
                path,
                "--required",
                "shipment",
                "--key",
                "shipment",
                "--max-incomplete-keys",
                "0",
                "--json",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["incomplete_key_rows"], 0)
        self.assertFalse(payload["failed_incomplete_keys"])

    def test_cli_pass_fail_and_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "orders.csv"
            path.write_text(
                "order,line\nA,1\nA,1\nB,\n,9\nC,3\n",
                encoding="utf-8",
            )
            base_args = (
                "--required",
                "order",
                "--key",
                "order,line",
                "--max-missing",
                "1",
            )
            failed = self._run(
                path,
                *base_args,
                "--max-incomplete-keys",
                "1",
                "--json",
            )
            passed = self._run(
                path,
                *base_args,
                "--max-incomplete-keys",
                "2",
            )
            no_key = self._run(
                path,
                "--required",
                "order",
                "--max-incomplete-keys",
                "0",
            )
            negative = self._run(
                path,
                *base_args,
                "--max-incomplete-keys",
                "-1",
            )
        self.assertEqual(failed.returncode, 1, failed.stderr)
        report = json.loads(failed.stdout)
        self.assertEqual(report["incomplete_key_rows"], 2)
        self.assertTrue(report["failed_incomplete_keys"])
        self.assertEqual(report["duplicate_keys"], 1)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn("Max allowed incomplete business keys: 2", passed.stdout)
        self.assertEqual(no_key.returncode, 2)
        self.assertIn("requires --key", no_key.stderr)
        self.assertEqual(negative.returncode, 2)
        self.assertIn("0 or greater", negative.stderr)

    @staticmethod
    def _run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ops_field_brief", str(path), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
