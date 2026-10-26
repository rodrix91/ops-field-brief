"""Integration checks for strict Unicode headers and usable business-key gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CombinedCsvGatesTests(unittest.TestCase):
    def test_strict_unicode_headers_and_complete_keys_can_run_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text(
                "order_id,line_id,customer\nA,1,Andes\nA,2,Andes\n,3,Altura\n",
                encoding="utf-8",
            )
            options = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "order_id",
                "--max-missing",
                "1",
                "--strict-csv",
                "--casefold-headers",
                "--key",
                "order_id,line_id",
                "--min-complete-keys",
                "2",
                "--max-duplicates",
                "0",
                "--json",
            ]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            passing = subprocess.run(
                options,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)
            self.assertEqual(json.loads(passing.stdout)["complete_key_rows"], 2)
            self.assertFalse(json.loads(passing.stdout)["failed_complete_keys"])

            failing_options = list(options)
            minimum_position = failing_options.index("--min-complete-keys") + 1
            failing_options[minimum_position] = "3"
            failing = subprocess.run(
                failing_options,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(failing.returncode, 1, failing.stderr)
            self.assertTrue(json.loads(failing.stdout)["failed_complete_keys"])

            path.write_text("order_id,ORDER_ID,line_id\nA,A,1\n", encoding="utf-8")
            collision = subprocess.run(
                options,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(collision.returncode, 2)
            self.assertIn("duplicate CSV header columns", collision.stderr)
            self.assertEqual(collision.stdout, "")


if __name__ == "__main__":
    unittest.main()
