"""Direct Python callers must use explicit string column selectors."""

from __future__ import annotations

import unittest

from ops_field_brief.brief import build_brief

ROWS = [
    {"id": "A", "region": "North"},
    {"id": "B", "region": "South"},
]


class PublicColumnNameTypesTests(unittest.TestCase):
    def test_required_rejects_scalar_and_non_string_names(self) -> None:
        invalid = (None, "id", {"id"}, ["id", None], ["id", []], (42,))
        for value in invalid:
            with self.subTest(required=repr(value)):
                with self.assertRaisesRegex(
                    ValueError, "required must contain string column names"
                ):
                    build_brief(ROWS, value)

    def test_single_key_rejects_non_string_selections(self) -> None:
        for value in (1, True, False, [], {}, ("id",)):
            with self.subTest(key=repr(value)):
                with self.assertRaisesRegex(ValueError, "key must be a string column name"):
                    build_brief(ROWS, ["id"], key=value)

    def test_composite_key_rejects_scalar_or_non_string_names(self) -> None:
        invalid = ("id", 1, True, {"id"}, ["id", None], ["id", []], (42,))
        for value in invalid:
            with self.subTest(key_fields=repr(value)):
                with self.assertRaisesRegex(
                    ValueError, "key_fields must contain string column names"
                ):
                    build_brief(ROWS, ["id"], key_fields=value)

    def test_group_rejects_non_string_selections(self) -> None:
        for value in (1, True, False, [], {}, ("region",)):
            with self.subTest(group=repr(value)):
                with self.assertRaisesRegex(ValueError, "group must be a string column name"):
                    build_brief(ROWS, ["id"], group=value)

    def test_valid_single_and_composite_selectors_remain_compatible(self) -> None:
        original = build_brief(ROWS, ["id"], key="id", group="region")
        self.assertEqual(original.rows, 2)
        self.assertEqual(original.duplicate_keys, 0)
        self.assertEqual(original.top, (("North", 1), ("South", 1)))

        composite = build_brief(ROWS, ("id", "region"), key_fields=("id", "region"))
        self.assertEqual(composite.key_fields, ("id", "region"))
        self.assertEqual([field.name for field in composite.fields], ["id", "region"])
        self.assertEqual(composite.duplicate_keys, 0)


if __name__ == "__main__":
    unittest.main()
