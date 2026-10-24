"""Fail-closed regression tests for non-finite operational quality thresholds."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief

ROOT = Path(__file__).resolve().parents[1]


class FiniteThresholdTests(unittest.TestCase):
    def test_nan_missing_threshold_is_invalid_in_library(self):
        rows = [{"buyer": ""}, {"buyer": "Andes"}]
        with self.assertRaisesRegex(ValueError, "max_missing must be between 0 and 1"):
            build_brief(rows, ["buyer"], max_missing=float("nan"))

    def test_other_nonfinite_thresholds_remain_invalid(self):
        rows = [{"buyer": ""}, {"buyer": "Andes"}]
        for value in ("inf", "-inf", "nan"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "max_missing must be between 0 and 1"):
                    build_brief(rows, ["buyer"], max_missing=float(value))
                with self.assertRaisesRegex(ValueError, "max_group_share must be between 0 and 1"):
                    build_brief(
                        rows,
                        ["buyer"],
                        group="buyer",
                        max_group_share=float(value),
                    )

    def test_cli_rejects_nan_before_reporting_success(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "shipment.csv"
            file.write_text("buyer\\nAndes\\n\\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            command = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(file),
                "--required",
                "buyer",
            ]
            invalid = subprocess.run(
                [*command, "--max-missing", "NaN", "--json"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            valid = subprocess.run(
                [*command, "--max-missing", "0", "--json"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("max_missing must be between 0 and 1", invalid.stderr)
        self.assertFalse(invalid.stdout.strip())
        self.assertEqual(valid.returncode, 1, valid.stderr)


if __name__ == "__main__":
    unittest.main()
