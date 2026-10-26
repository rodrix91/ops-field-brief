"""Upper cardinality limit for fully identified, unique operational business keys."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class MaximumDistinctKeysTests(unittest.TestCase):
    def test_composite_keys_count_uniques_not_repeated_or_incomplete_rows(self) -> None:
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "A", "line": "2"},
            {"order": "B", "line": "NA"},
            {"order": "", "line": "9"},
            {"order": "C", "line": "3"},
        ]
        allowed = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            max_distinct_keys=3,
            min_complete_keys=4,
        )
        self.assertEqual(allowed.distinct_keys, 3)
        self.assertFalse(allowed.failed_max_distinct_keys)
        self.assertFalse(allowed.failed_complete_keys)
        self.assertEqual(allowed.duplicate_keys, 1)
        self.assertEqual(allowed.to_dict()["max_distinct_keys"], 3)
        self.assertEqual(allowed.to_dict()["distinct_keys"], 3)
        self.assertFalse(allowed.to_dict()["failed_max_distinct_keys"])
        self.assertNotIn("min_distinct_keys", allowed.to_dict())
        self.assertNotIn("failed_distinct_keys", allowed.to_dict())
        self.assertIn("Maximum distinct complete business keys: 3", render(allowed, False))
        self.assertIn("Observed distinct complete business keys: 3", render(allowed, False))
        self.assertNotIn("Minimum distinct complete business keys", render(allowed, False))

        blocked = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            max_distinct_keys=2,
        )
        self.assertEqual(blocked.distinct_keys, 3)
        self.assertTrue(blocked.failed_max_distinct_keys)
        self.assertIn("Failed maximum distinct business-key check", render(blocked, False))
        self.assertIn("exceed the maximum (2)", render(blocked, False))

    def test_casefold_and_range_gates_operate_independently(self) -> None:
        rows = [
            {"id": "Straße"},
            {"id": "STRASSE"},
            {"id": "B"},
            {"id": "C"},
        ]
        raw = build_brief(rows, ["id"], key="id", max_distinct_keys=3)
        self.assertEqual(raw.distinct_keys, 4)
        self.assertTrue(raw.failed_max_distinct_keys)
        folded = build_brief(
            rows,
            ["id"],
            key="id",
            casefold_key=True,
            min_distinct_keys=2,
            max_distinct_keys=3,
        )
        self.assertEqual(folded.distinct_keys, 3)
        self.assertFalse(folded.failed_max_distinct_keys)
        self.assertFalse(folded.failed_distinct_keys)
        report = folded.to_dict()
        self.assertEqual(report["distinct_keys"], 3)
        self.assertTrue(report["casefold_key"])
        self.assertEqual(report["max_distinct_keys"], 3)
        self.assertEqual(report["min_distinct_keys"], 2)
        self.assertEqual(
            render(folded, False).count("- Observed distinct complete business keys:"), 1
        )

    def test_empty_and_all_missing_keys_have_zero_distinct(self) -> None:
        empty = CsvRows([], ["id"])
        ok = build_brief(empty, ["id"], key="id", max_distinct_keys=0)
        self.assertEqual(ok.distinct_keys, 0)
        self.assertFalse(ok.failed_max_distinct_keys)
        missing = build_brief(
            [{"id": ""}, {"id": "N/A"}],
            ["id"],
            key="id",
            max_missing=1,
            max_distinct_keys=0,
        )
        self.assertEqual(missing.distinct_keys, 0)
        self.assertFalse(missing.failed_max_distinct_keys)

    def test_default_json_and_markdown_remain_unchanged(self) -> None:
        old = build_brief([{"id": "A"}], ["id"], key="id")
        payload = old.to_dict()
        self.assertNotIn("max_distinct_keys", payload)
        self.assertNotIn("failed_max_distinct_keys", payload)
        self.assertNotIn("distinct_keys", payload)
        self.assertNotIn("Maximum distinct complete business keys", render(old, False))

    def test_invalid_bound_and_missing_keys_fail_before_metrics(self) -> None:
        rows = [{"id": "A"}]
        with self.assertRaisesRegex(ValueError, "max_distinct_keys must be 0 or greater"):
            build_brief(rows, ["id"], key="id", max_distinct_keys=-1)
        with self.assertRaisesRegex(ValueError, "max_distinct_keys requires --key"):
            build_brief(rows, ["id"], max_distinct_keys=1)
        with self.assertRaisesRegex(
            ValueError, "min_distinct_keys cannot exceed max_distinct_keys"
        ):
            build_brief(
                rows,
                ["id"],
                key="id",
                min_distinct_keys=2,
                max_distinct_keys=1,
            )

    def test_cli_success_quality_failure_and_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "orders.csv"
            source.write_text(
                "order,line\nA,1\nA,1\nA,2\nC,3\n,9\n",
                encoding="utf-8",
            )
            base = [str(source), "--required", "order", "--max-missing", "1"]

            def invoke(*args: str) -> tuple[int, str, str]:
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = main([*base, *args])
                return code, stdout.getvalue(), stderr.getvalue()

            good, out, err = invoke(
                "--key",
                "order,line",
                "--max-distinct-keys",
                "3",
                "--json",
            )
            self.assertEqual((good, err), (0, ""))
            self.assertEqual(json.loads(out)["distinct_keys"], 3)
            self.assertFalse(json.loads(out)["failed_max_distinct_keys"])
            bad, out, err = invoke(
                "--key",
                "order,line",
                "--max-distinct-keys",
                "2",
            )
            self.assertEqual((bad, err), (1, ""))
            self.assertIn("Failed maximum distinct business-key check", out)
            for flags, message in (
                (("--max-distinct-keys", "1"), "requires --key"),
                (("--key", "order", "--max-distinct-keys", "-1"), "0 or greater"),
                (
                    ("--key", "order", "--min-distinct-keys", "3", "--max-distinct-keys", "2"),
                    "cannot exceed",
                ),
            ):
                with self.subTest(flags=flags):
                    code, out, err = invoke(*flags)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertIn(message, err)


if __name__ == "__main__":
    unittest.main()
