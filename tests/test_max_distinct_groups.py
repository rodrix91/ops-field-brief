"""Maximum distinct-group checks complement the existing minimum-diversity gate."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class MaxDistinctGroupsTests(unittest.TestCase):
    def test_cardinality_gate_ignores_missing_and_respects_casefold(self):
        rows = [
            {"buyer": "Straße"},
            {"buyer": "STRASSE"},
            {"buyer": "Andes"},
            {"buyer": "NA"},
            {"buyer": "n/a"},
            {"buyer": "(blank)"},
        ]
        passed = build_brief(
            rows,
            ["buyer"],
            group="buyer",
            max_missing=1,
            casefold_group=True,
            max_distinct_groups=3,
            min_distinct_groups=3,
            top_n=0,
        )
        self.assertEqual(passed.distinct_groups, 3)
        self.assertFalse(passed.failed_max_distinct_groups)
        self.assertFalse(passed.failed_distinct_groups)
        self.assertEqual(passed.top, ())
        self.assertEqual(passed.to_dict()["max_distinct_groups"], 3)
        self.assertEqual(passed.to_dict()["distinct_groups"], 3)
        self.assertFalse(passed.to_dict()["failed_max_distinct_groups"])
        self.assertIn("Maximum distinct non-missing groups: 3", render(passed, False))

        failed = build_brief(
            rows,
            ["buyer"],
            group="buyer",
            max_missing=1,
            casefold_group=True,
            max_distinct_groups=2,
            top_n=0,
        )
        self.assertTrue(failed.failed_max_distinct_groups)
        self.assertIn("Failed group-cardinality check", render(failed, False))
        self.assertIn("exceed the maximum (2)", render(failed, False))

    def test_empty_extract_zero_allowed_and_minimum_can_fail_independently(self):
        empty = CsvRows([], ["buyer"])
        allowed = build_brief(empty, ["buyer"], group="buyer", max_distinct_groups=0)
        self.assertEqual(allowed.distinct_groups, 0)
        self.assertFalse(allowed.failed_max_distinct_groups)
        combined = build_brief(
            empty,
            ["buyer"],
            group="buyer",
            max_distinct_groups=1,
            min_distinct_groups=1,
        )
        self.assertFalse(combined.failed_max_distinct_groups)
        self.assertTrue(combined.failed_distinct_groups)

    def test_invalid_limits_and_unchanged_default_report(self):
        rows = [{"buyer": "Andes"}, {"buyer": "Paz"}]
        with self.assertRaisesRegex(ValueError, "0 or greater"):
            build_brief(rows, ["buyer"], group="buyer", max_distinct_groups=-1)
        with self.assertRaisesRegex(ValueError, "requires --group"):
            build_brief(rows, ["buyer"], max_distinct_groups=1)
        legacy = build_brief(rows, ["buyer"], group="buyer")
        self.assertNotIn("max_distinct_groups", legacy.to_dict())
        self.assertNotIn("distinct_groups", legacy.to_dict())
        self.assertNotIn("Maximum distinct", render(legacy, False))
        self.assertFalse(legacy.failed_max_distinct_groups)

    def test_cli_pass_fail_and_configuration_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "buyers.csv"
            path.write_text(
                "shipment,buyer\nS1,Andes\nS2,Paz\nS3,NA\nS4,Andes\n",
                encoding="utf-8",
            )
            args = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--top",
                "0",
                "--json",
            ]
            for maximum, exit_code, expected_failure in ((2, 0, False), (1, 1, True)):
                with self.subTest(maximum=maximum):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = main([*args, "--max-distinct-groups", str(maximum)])
                    self.assertEqual(result, exit_code)
                    payload = json.loads(stdout.getvalue())
                    self.assertEqual(payload["distinct_groups"], 2)
                    self.assertEqual(payload["top"], [])
                    self.assertEqual(payload["failed_max_distinct_groups"], expected_failure)
            for options, message in (
                ([*args, "--max-distinct-groups", "-1"], "0 or greater"),
                (
                    [str(path), "--required", "shipment", "--max-distinct-groups", "1"],
                    "requires --group",
                ),
            ):
                with self.subTest(options=options):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = main(options)
                    self.assertEqual(result, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn(message, stderr.getvalue())

    def test_conflicting_cardinality_bounds_are_configuration_errors(self):
        rows = [{"buyer": "Andes"}, {"buyer": "Paz"}]
        with self.assertRaisesRegex(
            ValueError, "min_distinct_groups cannot exceed max_distinct_groups"
        ):
            build_brief(
                rows,
                ["buyer"],
                group="buyer",
                min_distinct_groups=3,
                max_distinct_groups=2,
                top_n=0,
            )
        # The contradiction must be rejected even when the CSV has no records.
        with self.assertRaisesRegex(ValueError, "min_distinct_groups cannot exceed"):
            build_brief(
                CsvRows([], ["buyer"]),
                ["buyer"],
                group="buyer",
                min_distinct_groups=1,
                max_distinct_groups=0,
            )

    def test_equal_group_bounds_remain_valid_including_zero(self):
        rows = [{"buyer": "Andes"}, {"buyer": "NA"}, {"buyer": "Andes"}]
        exact = build_brief(
            rows,
            ["buyer"],
            group="buyer",
            min_distinct_groups=1,
            max_distinct_groups=1,
            max_missing=1,
            top_n=0,
        )
        self.assertEqual(exact.distinct_groups, 1)
        self.assertFalse(exact.failed_distinct_groups)
        self.assertFalse(exact.failed_max_distinct_groups)
        empty = build_brief(
            CsvRows([], ["buyer"]),
            ["buyer"],
            group="buyer",
            min_distinct_groups=0,
            max_distinct_groups=0,
        )
        self.assertEqual(empty.distinct_groups, 0)
        self.assertFalse(empty.failed_distinct_groups)
        self.assertFalse(empty.failed_max_distinct_groups)

    def test_cli_conflicting_bounds_exit_two_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "buyers.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,Paz\n", encoding="utf-8")
            args = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--min-distinct-groups",
                "3",
                "--max-distinct-groups",
                "2",
                "--json",
            ]
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(args)
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(
                "min_distinct_groups cannot exceed max_distinct_groups",
                stderr.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
