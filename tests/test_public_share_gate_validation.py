"""Regression tests for share-based quality gates called from Python."""

from __future__ import annotations

import math
import unittest
from decimal import Decimal

from ops_field_brief.brief import build_brief

SHARE_LIMITS = (
    "max_missing",
    "max_duplicate_share",
    "max_incomplete_key_share",
    "max_group_share",
    "max_assigned_group_share",
    "max_missing_group_share",
)
ROWS = [
    {"id": "A", "group": "North", "eta": ""},
    {"id": "B", "group": "South", "eta": "2026-11-01"},
]


def report(**limits: object):
    return build_brief(ROWS, ["id", "eta"], key="id", group="group", **limits)


class PublicShareGateValidationTests(unittest.TestCase):
    def test_invalid_share_types_and_nonfinite_values_fail_cleanly(self) -> None:
        invalid = (
            True,
            False,
            "0.5",
            [],
            {},
            complex(0.5, 0),
            math.nan,
            math.inf,
            -math.inf,
            Decimal("NaN"),
            -0.1,
            1.1,
        )
        for name in SHARE_LIMITS:
            for value in invalid:
                with self.subTest(gate=name, value=repr(value)):
                    with self.assertRaisesRegex(ValueError, f"{name} must be between 0 and 1"):
                        report(**{name: value})
        with self.assertRaisesRegex(ValueError, "max_missing must be between 0 and 1"):
            report(max_missing=None)

    def test_invalid_field_specific_shares_fail_cleanly(self) -> None:
        for value in (True, False, "0.5", [], math.nan, math.inf, Decimal("NaN")):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(
                    ValueError, "max_missing_columns shares must be between 0 and 1"
                ):
                    report(max_missing_columns={"eta": value})

    def test_valid_numeric_boundaries_and_optional_none_remain_supported(self) -> None:
        for name in SHARE_LIMITS:
            for value in (0, 0.5, 1):
                with self.subTest(gate=name, value=value):
                    result = report(**{name: value})
                    self.assertEqual(result.rows, 2)
                    self.assertEqual(result.duplicate_keys, 0)
            if name != "max_missing":
                with self.subTest(gate=name, value=None):
                    self.assertEqual(report(**{name: None}).rows, 2)
        for value in (0, 0.5, 1):
            with self.subTest(field_specific=value):
                self.assertEqual(report(max_missing_columns={"eta": value}).rows, 2)

    def test_existing_decimal_and_fraction_comparisons_still_work(self) -> None:
        from fractions import Fraction

        for value in (Decimal("0.5"), Fraction(1, 2)):
            with self.subTest(value=repr(value)):
                self.assertEqual(report(max_missing=value).rows, 2)
                self.assertEqual(report(max_missing_columns={"eta": value}).rows, 2)


if __name__ == "__main__":
    unittest.main()
