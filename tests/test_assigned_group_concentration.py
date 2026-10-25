"""Assigned counterparty concentration must not be hidden by missing labels."""

from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class AssignedGroupConcentrationTests(unittest.TestCase):
    def test_missing_rows_mask_concentration_in_original_all_row_metric(self) -> None:
        rows = [
            *({"shipment": f"A{i}", "buyer": "ACME"} for i in range(6)),
            *({"shipment": f"B{i}", "buyer": "BETA"} for i in range(2)),
            *({"shipment": f"N{i}", "buyer": "NA"} for i in range(12)),
        ]
        original = build_brief(
            rows, ["shipment"], group="buyer", max_group_share=0.60, top_n=0
        )
        self.assertAlmostEqual(original.top_group_share, 0.60)
        self.assertFalse(original.failed_group_share)
        self.assertEqual(original.top, ())
        self.assertNotIn("top_assigned_group_share", original.to_dict())
        self.assertNotIn("assigned-group", render(original, False))

        report = build_brief(
            rows,
            ["shipment"],
            group="buyer",
            max_group_share=0.60,
            max_assigned_group_share=0.60,
            top_n=0,
        )
        self.assertEqual(report.assigned_group_rows, 8)
        self.assertAlmostEqual(report.top_assigned_group_share, 0.75)
        self.assertTrue(report.failed_assigned_group_share)
        self.assertFalse(report.failed_group_share)
        self.assertEqual(report.top, ())
        self.assertEqual(report.to_dict()["assigned_group_rows"], 8)
        self.assertEqual(report.to_dict()["top_assigned_group_share"], 0.75)
        self.assertTrue(report.to_dict()["failed_assigned_group_share"])
        markdown = render(report, False)
        self.assertIn("Rows assigned to a group: 8", markdown)
        self.assertIn("Observed top assigned-group share: 75.0%", markdown)
        self.assertIn("## Failed assigned-group concentration check", markdown)

    def test_missing_only_fails_closed_while_empty_export_keeps_min_rows_contract(self) -> None:
        rows = [{"shipment": "A", "buyer": "NA"}, {"shipment": "B", "buyer": "n/a"}]
        all_missing = build_brief(
            rows, ["shipment"], group="buyer", max_assigned_group_share=1.0
        )
        self.assertEqual(all_missing.assigned_group_rows, 0)
        self.assertEqual(all_missing.top_assigned_group_share, 0.0)
        self.assertTrue(all_missing.failed_assigned_group_share)
        self.assertIn("No rows have an identified group.", render(all_missing, False))

        empty = CsvRows([], ["shipment", "buyer"])
        empty_report = build_brief(
            empty,
            ["shipment"],
            group="buyer",
            max_assigned_group_share=0,
            min_rows=1,
        )
        self.assertEqual(empty_report.assigned_group_rows, 0)
        self.assertFalse(empty_report.failed_assigned_group_share)
        self.assertTrue(empty_report.failed_rows)

    def test_literal_blank_casefold_and_independent_missing_gate(self) -> None:
        rows = [
            {"shipment": "A", "buyer": "Straße"},
            {"shipment": "B", "buyer": "STRASSE"},
            {"shipment": "C", "buyer": "(blank)"},
            {"shipment": "D", "buyer": "null"},
            {"shipment": "E", "buyer": "s/d"},
        ]
        report = build_brief(
            rows,
            ["shipment"],
            group="buyer",
            casefold_group=True,
            max_assigned_group_share=0.60,
            max_missing_group_share=0.40,
            min_distinct_groups=2,
            top_n=0,
        )
        self.assertEqual(report.assigned_group_rows, 3)
        self.assertAlmostEqual(report.top_assigned_group_share, 2 / 3)
        self.assertEqual(report.distinct_groups, 2)
        self.assertEqual(report.missing_group_rows, 2)
        self.assertFalse(report.failed_missing_group_share)
        self.assertFalse(report.failed_distinct_groups)
        self.assertTrue(report.failed_assigned_group_share)
        self.assertTrue(report.casefold_group)

    def test_invalid_settings_fail_before_any_report(self) -> None:
        rows = [{"shipment": "S1", "buyer": "ACME"}]
        for invalid in [-0.01, 1.01, math.nan, math.inf, -math.inf]:
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ValueError, "max_assigned_group_share must be between 0 and 1"
            ):
                build_brief(
                    rows,
                    ["shipment"],
                    group="buyer",
                    max_assigned_group_share=invalid,
                )
        with self.assertRaisesRegex(ValueError, "max_assigned_group_share requires --group"):
            build_brief(rows, ["shipment"], max_assigned_group_share=0.6)

    def test_cli_exits_one_for_assigned_concentration_and_preserves_default(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "buyers.csv"
            path.write_text(
                "shipment,buyer\nA1,ACME\nA2,ACME\nB1,BETA\nN1,NA\nN2,null\n",
                encoding="utf-8",
            )
            args = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--max-group-share",
                "0.6",
                "--top",
                "0",
                "--json",
            ]
            default_stdout = io.StringIO()
            with contextlib.redirect_stdout(default_stdout):
                code = main(args)
            self.assertEqual(code, 0)
            baseline = json.loads(default_stdout.getvalue())
            self.assertNotIn("max_assigned_group_share", baseline)
            self.assertNotIn("assigned_group_rows", baseline)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*args, "--max-assigned-group-share", "0.60"])
            self.assertEqual(code, 1)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["assigned_group_rows"], 3)
            self.assertEqual(report["top_assigned_group_share"], 0.6667)
            self.assertTrue(report["failed_assigned_group_share"])
            self.assertFalse(report["failed_group_share"])

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        str(path),
                        "--required",
                        "shipment",
                        "--group",
                        "buyer",
                        "--max-assigned-group-share",
                        "1.0",
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)

            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        str(path),
                        "--required",
                        "shipment",
                        "--max-assigned-group-share",
                        "0.5",
                        "--json",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("requires --group", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
