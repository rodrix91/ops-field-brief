"""Executable, synthetic supplier-risk case study for nontechnical reviewers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = [
    "--required",
    "shipment_id,supplier,eta",
    "--key",
    "shipment_id",
    "--max-duplicates",
    "0",
    "--group",
    "supplier",
    "--casefold-group",
    "--max-missing",
    "0",
    "--max-assigned-group-share",
    "0.60",
    "--max-missing-group-share",
    "0.20",
    "--min-distinct-groups",
    "3",
    "--min-rows",
    "8",
    "--delimiter",
    "auto",
    "--strict-csv",
    "--json",
]


def run_case(filename: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, "-m", "ops_field_brief", f"examples/{filename}", *COMMON],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    if not result.stdout:
        raise AssertionError(f"Missing CLI JSON output: {result.stderr}")
    return result.returncode, json.loads(result.stdout)


class SyntheticSupplierCaseStudyTests(unittest.TestCase):
    def test_at_risk_extract_is_rejected_for_independent_reasons(self) -> None:
        code, report = run_case("supplier-risk-synthetic.csv")
        self.assertEqual(code, 1)
        self.assertEqual(report["rows"], 8)
        self.assertEqual(report["duplicate_keys"], 1)
        self.assertTrue(report["failed_duplicates"])
        self.assertEqual(set(report["failed_fields"]), {"supplier", "eta"})
        self.assertEqual(report["missing_group_rows"], 2)
        self.assertEqual(report["missing_group_share"], 0.25)
        self.assertTrue(report["failed_missing_group_share"])
        self.assertEqual(report["assigned_group_rows"], 6)
        self.assertEqual(report["top_assigned_group_share"], 0.6667)
        self.assertTrue(report["failed_assigned_group_share"])
        self.assertEqual(report["distinct_groups"], 2)
        self.assertTrue(report["failed_distinct_groups"])
        self.assertFalse(report["failed_rows"])
        self.assertEqual(dict((item["value"], item["rows"]) for item in report["top"])["andes freight"], 4)

    def test_corrected_extract_passes_the_exact_same_policy(self) -> None:
        code, report = run_case("supplier-clean-synthetic.csv")
        self.assertEqual(code, 0)
        self.assertEqual(report["rows"], 8)
        self.assertEqual(report["duplicate_keys"], 0)
        self.assertEqual(report["failed_fields"], [])
        self.assertEqual(report["missing_group_rows"], 0)
        self.assertEqual(report["assigned_group_rows"], 8)
        self.assertEqual(report["top_assigned_group_share"], 0.375)
        self.assertEqual(report["distinct_groups"], 3)
        for key in (
            "failed_duplicates",
            "failed_assigned_group_share",
            "failed_missing_group_share",
            "failed_distinct_groups",
            "failed_rows",
        ):
            self.assertFalse(report[key], key)

    def test_identical_thresholds_and_canonical_casefolding(self) -> None:
        _, risk = run_case("supplier-risk-synthetic.csv")
        _, clean = run_case("supplier-clean-synthetic.csv")
        for field in (
            "max_duplicates",
            "max_assigned_group_share",
            "max_missing_group_share",
            "min_distinct_groups",
            "min_rows",
            "casefold_group",
        ):
            self.assertEqual(risk[field], clean[field], field)
        self.assertEqual(risk["casefold_group"], True)


if __name__ == "__main__":
    unittest.main()
