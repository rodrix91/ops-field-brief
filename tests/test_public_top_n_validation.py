"""Regression tests for the public group-ranking limit, not only the CLI parser."""

from __future__ import annotations

import math
import unittest

from ops_field_brief.brief import build_brief

ROWS = [
    {"shipment": "S1", "buyer": "Andes"},
    {"shipment": "S2", "buyer": "Paz"},
    {"shipment": "S3", "buyer": "Andes"},
]


class TopNApiValidationTests(unittest.TestCase):
    def test_non_integer_limits_fail_before_grouping(self) -> None:
        invalid = (True, False, 1.5, "2", None, math.nan, math.inf, -math.inf)
        for top_n in invalid:
            for group in (None, "buyer"):
                with self.subTest(top_n=top_n, group=group):
                    with self.assertRaisesRegex(ValueError, "top must be a non-negative integer"):
                        build_brief(ROWS, ["shipment", "buyer"], group=group, top_n=top_n)

    def test_invalid_limit_is_rejected_even_with_no_rows(self) -> None:
        with self.assertRaisesRegex(ValueError, "top must be a non-negative integer"):
            build_brief([], ["shipment"], top_n=True)

    def test_negative_integer_keeps_existing_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "top must be 0 or greater"):
            build_brief(ROWS, ["shipment", "buyer"], group="buyer", top_n=-1)

    def test_zero_limit_preserves_business_metrics(self) -> None:
        report = build_brief(ROWS, ["shipment", "buyer"], group="buyer", top_n=0)
        self.assertEqual(report.top, ())
        self.assertEqual(report.rows, 3)
        self.assertEqual(report.top_group_share, 2 / 3)
        self.assertEqual(report.failed_fields, ())

    def test_valid_integer_limits_preserve_group_ranking(self) -> None:
        report = build_brief(ROWS, ["shipment", "buyer"], group="buyer", top_n=1)
        self.assertEqual(report.top, (("Andes", 2),))
        report_all = build_brief(ROWS, ["shipment", "buyer"], group="buyer", top_n=5)
        self.assertEqual(report_all.top, (("Andes", 2), ("Paz", 1)))


if __name__ == "__main__":
    unittest.main()
