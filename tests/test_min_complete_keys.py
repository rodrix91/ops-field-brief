"""Regression tests for the opt-in minimum of usable business-key rows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, render_markdown

ROOT = Path(__file__).resolve().parents[1]


class MinimumCompleteKeyTests(unittest.TestCase):
    def test_composite_keys_ignore_missing_components_but_count_repeated_keys(self) -> None:
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "B", "line": "N/A"},
            {"order": "NA", "line": "2"},
            {"order": "C", "line": "3"},
        ]
        brief = build_brief(
            rows, ["order"], key_fields=["order", "line"],
            max_missing=1, min_complete_keys=3,
        )
        self.assertEqual(brief.complete_key_rows, 3)
        self.assertEqual(brief.duplicate_keys, 1)
        self.assertFalse(brief.failed_complete_keys)
        self.assertEqual(brief.to_dict()["min_complete_keys"], 3)
        self.assertEqual(brief.to_dict()["complete_key_rows"], 3)
        self.assertFalse(brief.to_dict()["failed_complete_keys"])
        self.assertIn("Minimum rows with complete business keys: 3", render_markdown(brief))

        failed = build_brief(
            rows, ["order"], key_fields=["order", "line"],
            max_missing=1, min_complete_keys=4,
        )
        self.assertTrue(failed.failed_complete_keys)
        self.assertIn("Failed complete-key row-count check", render_markdown(failed))
        self.assertIn("below the minimum (4)", render_markdown(failed))

    def test_zero_rows_and_disabled_output_are_backward_compatible(self) -> None:
        empty = build_brief([], ["order"], key="order", min_complete_keys=0)
        self.assertFalse(empty.failed_complete_keys)
        self.assertEqual(empty.complete_key_rows, 0)
        failed = build_brief([], ["order"], key="order", min_complete_keys=1)
        self.assertTrue(failed.failed_complete_keys)
        original = build_brief([{"order": "A"}], ["order"], key="order")
        self.assertNotIn("min_complete_keys", original.to_dict())
        self.assertNotIn("failed_complete_keys", original.to_dict())
        self.assertNotIn("Rows with complete business keys:", render_markdown(original))

    def test_works_independently_of_duplicate_and_total_row_gates(self) -> None:
        rows = [{"id": ""}, {"id": "A"}, {"id": "A"}]
        report = build_brief(
            rows, ["id"], key="id", max_missing=1, min_rows=3,
            min_complete_keys=2, max_duplicates=0, max_duplicate_share=0,
        )
        self.assertFalse(report.failed_rows)
        self.assertFalse(report.failed_complete_keys)
        self.assertTrue(report.failed_duplicates)
        self.assertTrue(report.failed_duplicate_share)
        self.assertEqual(report.to_dict()["complete_key_rows"], 2)

    def test_invalid_minimum_and_missing_key_are_configuration_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "min_complete_keys must be 0 or greater"):
            build_brief([{"id": "A"}], ["id"], key="id", min_complete_keys=-1)
        with self.assertRaisesRegex(ValueError, "min_complete_keys requires --key"):
            build_brief([{"id": "A"}], ["id"], min_complete_keys=1)

    def test_cli_exit_codes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("id,line\nA,1\nA,2\n,3\n", encoding="utf-8")
            base = [
                sys.executable, "-m", "ops_field_brief", str(path),
                "--required", "id", "--max-missing", "1",
            ]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            def run(*options: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [*base, *options], cwd=ROOT, env=env,
                    capture_output=True, text=True, check=False,
                )

            good = run("--key", "id,line", "--min-complete-keys", "2", "--json")
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)["complete_key_rows"], 2)
            self.assertFalse(json.loads(good.stdout)["failed_complete_keys"])

            bad = run("--key", "id,line", "--min-complete-keys", "3")
            self.assertEqual(bad.returncode, 1, bad.stderr)
            self.assertIn("Failed complete-key row-count check", bad.stdout)

            missing_key = run("--min-complete-keys", "1")
            self.assertEqual(missing_key.returncode, 2)
            self.assertIn("requires --key", missing_key.stderr)

            negative = run("--key", "id", "--min-complete-keys", "-1")
            self.assertEqual(negative.returncode, 2)
            self.assertIn("must be 0 or greater", negative.stderr)


if __name__ == "__main__":
    unittest.main()
