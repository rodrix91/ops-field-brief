"""Distinct real customer/supplier labels are an opt-in operational quality gate."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class DistinctGroupGateTests(unittest.TestCase):
    def test_missing_tokens_do_not_inflate_diversity_or_merge_literal_blank(self) -> None:
        rows = [
            {"buyer": "Andes"},
            {"buyer": "Andes"},
            {"buyer": "Paz"},
            {"buyer": "NA"},
            {"buyer": "n/a"},
            {"buyer": " "},
            {"buyer": "(blank)"},
        ]
        passed = build_brief(
            rows,
            ["buyer"],
            group="buyer",
            max_missing=1.0,
            min_distinct_groups=3,
            top_n=0,
        )
        self.assertEqual(passed.distinct_groups, 3)
        self.assertFalse(passed.failed_distinct_groups)
        self.assertEqual(passed.top, ())
        self.assertEqual(passed.to_dict()["distinct_groups"], 3)
        self.assertEqual(passed.to_dict()["min_distinct_groups"], 3)
        self.assertFalse(passed.to_dict()["failed_distinct_groups"])
        self.assertIn("Observed distinct non-missing groups: 3", render(passed, False))
        failed = build_brief(
            rows,
            ["buyer"],
            group="buyer",
            max_missing=1.0,
            min_distinct_groups=4,
            max_group_share=0.5,
        )
        self.assertTrue(failed.failed_distinct_groups)
        self.assertFalse(failed.failed_group_share)
        self.assertIn("Failed group-diversity check", render(failed, False))
        self.assertIn("below the minimum (4)", render(failed, False))

    def test_missing_only_extract_and_header_only_extract_fail_closed(self) -> None:
        only_missing = build_brief(
            [{"buyer": "NA"}, {"buyer": ""}],
            ["buyer"],
            group="buyer",
            max_missing=1.0,
            min_distinct_groups=1,
        )
        self.assertEqual(only_missing.distinct_groups, 0)
        self.assertTrue(only_missing.failed_distinct_groups)
        empty = build_brief(
            CsvRows([], ["buyer"]),
            ["buyer"],
            group="buyer",
            min_distinct_groups=1,
        )
        self.assertEqual(empty.distinct_groups, 0)
        self.assertTrue(empty.failed_distinct_groups)
        zero_allowed = build_brief(
            CsvRows([], ["buyer"]),
            ["buyer"],
            group="buyer",
            min_distinct_groups=0,
        )
        self.assertFalse(zero_allowed.failed_distinct_groups)

    def test_invalid_gate_configuration_and_backward_compatibility(self) -> None:
        rows = [{"buyer": "Andes"}]
        with self.assertRaisesRegex(ValueError, "0 or greater"):
            build_brief(rows, ["buyer"], group="buyer", min_distinct_groups=-1)
        with self.assertRaisesRegex(ValueError, "requires --group"):
            build_brief(rows, ["buyer"], min_distinct_groups=2)
        legacy = build_brief(rows, ["buyer"], group="buyer")
        self.assertNotIn("distinct_groups", legacy.to_dict())
        self.assertNotIn("min_distinct_groups", legacy.to_dict())
        self.assertNotIn("distinct non-missing groups", render(legacy, False))
        self.assertFalse(legacy.failed_distinct_groups)

    def test_cli_pass_fail_and_invalid_usage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "buyers.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,NA\nS3,Paz\n", encoding="utf-8")
            prefix = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--top",
                "0",
                "--json",
            ]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*prefix, "--min-distinct-groups", "2"])
            self.assertEqual(code, 0)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["distinct_groups"], 2)
            self.assertEqual(report["top"], [])
            self.assertFalse(report["failed_distinct_groups"])

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*prefix, "--min-distinct-groups", "3"])
            self.assertEqual(code, 1)
            self.assertTrue(json.loads(stdout.getvalue())["failed_distinct_groups"])

            for args, diagnostic in (
                ([*prefix, "--min-distinct-groups", "-1"], "0 or greater"),
                (
                    [str(path), "--required", "shipment", "--min-distinct-groups", "1"],
                    "requires --group",
                ),
            ):
                with self.subTest(args=args):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = main(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn(diagnostic, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
