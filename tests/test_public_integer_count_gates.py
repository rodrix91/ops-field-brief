"""Public count-based quality gates must accept integer periods, not boolean/float values."""

from __future__ import annotations

import math
import unittest

from ops_field_brief.brief import build_brief

COUNT_LIMITS = (
    "max_duplicates",
    "min_complete_keys",
    "min_distinct_keys",
    "max_distinct_keys",
    "max_incomplete_keys",
    "min_rows",
    "max_rows",
    "min_distinct_groups",
    "max_distinct_groups",
)
ROWS = [
    {"id": "A", "group": "north"},
    {"id": "A", "group": "south"},
    {"id": "B", "group": ""},
]


class PublicIntegerCountGateTests(unittest.TestCase):
    def test_noninteger_limit_types_fail_with_clear_errors_before_reading_rows(self) -> None:
        invalid = (
            True,
            False,
            1.5,
            0.0,
            "2",
            "",
            math.nan,
            math.inf,
            -math.inf,
            [],
            {},
            complex(1, 0),
        )
        for name in COUNT_LIMITS:
            for value in invalid:
                with self.subTest(gate=name, value=repr(value)):
                    with self.assertRaisesRegex(
                        ValueError, f"{name} must be a non-negative integer"
                    ):
                        # Every gate has its required key/group configuration.
                        # There are no rows, so invalid options cannot be hidden
                        # behind misleading computed quality metrics.
                        build_brief(
                            [],
                            ["id"],
                            key="id",
                            group="group",
                            **{name: value},
                        )

    def test_none_zero_and_positive_integer_limits_remain_accepted(self) -> None:
        for name in COUNT_LIMITS:
            for value in (None, 0, 2):
                with self.subTest(gate=name, value=value):
                    report = build_brief(
                        ROWS,
                        ["id"],
                        key="id",
                        group="group",
                        max_missing=1,
                        **{name: value},
                    )
                    self.assertEqual(report.rows, 3)
                    self.assertEqual(report.duplicate_keys, 1)
                    self.assertEqual(report.distinct_groups, 2)

    def test_existing_negative_integer_diagnostics_stay_unchanged(self) -> None:
        for name in COUNT_LIMITS:
            with self.subTest(gate=name):
                with self.assertRaisesRegex(ValueError, f"{name} must be 0 or greater"):
                    build_brief(
                        ROWS,
                        ["id"],
                        key="id",
                        group="group",
                        **{name: -1},
                    )

    def test_invalid_counts_have_priority_over_missing_key_or_group(self) -> None:
        for name in COUNT_LIMITS:
            with self.subTest(gate=name):
                with self.assertRaisesRegex(
                    ValueError, f"{name} must be a non-negative integer"
                ):
                    build_brief([], ["id"], **{name: True})

    def test_ordinary_reports_without_limits_keep_original_schema(self) -> None:
        report = build_brief(ROWS, ["id"], key="id", group="group", max_missing=1)
        self.assertEqual(report.rows, 3)
        self.assertEqual(report.duplicate_keys, 1)
        self.assertEqual(report.distinct_groups, 2)
        self.assertNotIn("max_rows", report.to_dict())
        self.assertNotIn("min_rows", report.to_dict())


if __name__ == "__main__":
    unittest.main()
