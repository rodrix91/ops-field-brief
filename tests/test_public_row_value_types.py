"""Direct build_brief calls must reject non-CSV row types predictably."""

from __future__ import annotations

import unittest

from ops_field_brief.brief import build_brief


class PublicRowValueValidationTests(unittest.TestCase):
    def test_nonmapping_rows_are_reported_as_configuration_errors(self) -> None:
        for rows in (
            None,
            "id,region",
            {"id": "A"},
            [["A", "North"]],
            [{"id": "A", "region": "North"}, None],
            [{"id": "A", "region": "North"}, "not a mapping"],
        ):
            with self.subTest(rows=repr(rows)):
                with self.assertRaisesRegex(
                    ValueError, "rows must be a sequence of CSV field mappings"
                ):
                    build_brief(rows, ["id"], group="region")

    def test_selected_nontext_values_get_a_bounded_row_diagnostic(self) -> None:
        for selected, options in (
            ({"id": 123, "region": "North"}, {}),
            ({"id": b"A", "region": "North"}, {"key": "id"}),
            ({"id": "A", "region": ["North"]}, {"group": "region"}),
            ({"id": "A", "region": {"private": "secret"}}, {"group": "region"}),
        ):
            with self.subTest(value=repr(selected)):
                with self.assertRaisesRegex(
                    ValueError, "CSV data row 2 selected values must be strings or None"
                ) as error:
                    build_brief([{"id": "ok", "region": "South"}, selected], ["id"], **options)
                self.assertNotIn("secret", str(error.exception))
                self.assertLess(len(str(error.exception)), 100)

    def test_missing_none_values_and_ignored_ragged_overflow_remain_supported(self) -> None:
        rows = [
            {"id": "A", "region": None},
            {"id": None, "region": "North"},
            {"id": "C", "region": "North", None: ["overflow", "ignored"]},
        ]
        report = build_brief(rows, ["id"], key="id", group="region")
        self.assertEqual(report.rows, 3)
        self.assertEqual(report.fields[0].missing, 1)
        self.assertEqual(report.incomplete_key_rows, 1)
        self.assertEqual(report.top, (("North", 2), ("(blank)", 1)))

    def test_unselected_nontext_extra_columns_remain_ignored(self) -> None:
        report = build_brief(
            [{"id": "A", "region": "North", "ignored-extra": object()}],
            ["id"],
            group="region",
        )
        self.assertEqual(report.rows, 1)
        self.assertEqual(report.top, (("North", 1),))


if __name__ == "__main__":
    unittest.main()
