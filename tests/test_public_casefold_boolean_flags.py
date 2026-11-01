"""Public casefold switches must be boolean to protect operational metrics."""

from __future__ import annotations

import unittest

from ops_field_brief.brief import build_brief

ROWS = [
    {"order_id": "ORD-51", "buyer": "ACME"},
    {"order_id": "ord-51", "buyer": "Acme"},
]


class PublicCasefoldBooleanTests(unittest.TestCase):
    def test_invalid_key_and_group_switches_raise_before_calculating_metrics(self) -> None:
        invalid = ("false", "true", "", 0, 1, 0.0, None, [], {}, object())
        for name in ("casefold_key", "casefold_group"):
            for value in invalid:
                with self.subTest(option=name, value=repr(value)):
                    with self.assertRaisesRegex(ValueError, f"{name} must be a boolean"):
                        build_brief(
                            ROWS,
                            ["order_id"],
                            key="order_id",
                            group="buyer",
                            **{name: value},
                        )

    def test_invalid_flags_are_rejected_even_without_key_or_group(self) -> None:
        for name in ("casefold_key", "casefold_group"):
            with self.subTest(option=name):
                with self.assertRaisesRegex(ValueError, f"{name} must be a boolean"):
                    build_brief([], ["order_id"], **{name: "false"})

    def test_actual_false_and_true_preserve_documented_comparison_behavior(self) -> None:
        normal = build_brief(
            ROWS,
            ["order_id"],
            key="order_id",
            group="buyer",
            casefold_key=False,
            casefold_group=False,
        )
        self.assertEqual(normal.duplicate_keys, 0)
        self.assertEqual(normal.distinct_groups, 2)
        self.assertNotIn("casefold_key", normal.to_dict())
        self.assertNotIn("casefold_group", normal.to_dict())

        folded = build_brief(
            ROWS,
            ["order_id"],
            key="order_id",
            group="buyer",
            casefold_key=True,
            casefold_group=True,
        )
        self.assertEqual(folded.duplicate_keys, 1)
        self.assertEqual(folded.distinct_groups, 1)
        self.assertTrue(folded.to_dict()["casefold_key"])
        self.assertTrue(folded.to_dict()["casefold_group"])


if __name__ == "__main__":
    unittest.main()
