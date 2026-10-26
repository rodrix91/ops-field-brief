"""Minimum count of unique, usable business keys in an operational export."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class MinimumDistinctCompleteKeyTests(unittest.TestCase):
    def test_composite_keys_exclude_missing_and_count_duplicates_once(self) -> None:
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "A", "line": "2"},
            {"order": "B", "line": "NA"},
            {"order": "", "line": "9"},
            {"order": "C", "line": "3"},
        ]
        passed = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            min_complete_keys=4,
            min_distinct_keys=3,
            max_duplicates=1,
        )
        self.assertEqual(passed.complete_key_rows, 4)
        self.assertEqual(passed.duplicate_keys, 1)
        self.assertEqual(passed.distinct_keys, 3)
        self.assertFalse(passed.failed_distinct_keys)
        self.assertFalse(passed.failed_complete_keys)
        self.assertFalse(passed.failed_duplicates)
        report = passed.to_dict()
        self.assertEqual(report["min_distinct_keys"], 3)
        self.assertEqual(report["distinct_keys"], 3)
        self.assertFalse(report["failed_distinct_keys"])
        markdown = render(passed, False)
        self.assertIn("Minimum distinct complete business keys: 3", markdown)
        self.assertIn("Observed distinct complete business keys: 3", markdown)

        failed = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            min_complete_keys=4,
            min_distinct_keys=4,
        )
        self.assertFalse(failed.failed_complete_keys)
        self.assertTrue(failed.failed_distinct_keys)
        self.assertIn("Failed distinct business-key check", render(failed, False))
        self.assertIn("Distinct complete business keys (3)", render(failed, False))

    def test_casefold_key_controls_distinctness_for_unicode(self) -> None:
        rows = [
            {"order": "Straße", "line": "1"},
            {"order": "STRASSE", "line": "1"},
            {"order": "B", "line": "2"},
            {"order": "N/A", "line": "3"},
        ]
        plain = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            min_distinct_keys=3,
        )
        self.assertEqual(plain.distinct_keys, 3)
        self.assertFalse(plain.failed_distinct_keys)
        folded = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            min_distinct_keys=3,
            casefold_key=True,
        )
        self.assertEqual(folded.distinct_keys, 2)
        self.assertTrue(folded.failed_distinct_keys)

    def test_empty_csv_and_zero_minimum_are_explicit(self) -> None:
        empty = CsvRows([], ["id"])
        passing = build_brief(empty, ["id"], key="id", min_distinct_keys=0)
        self.assertEqual(passing.distinct_keys, 0)
        self.assertFalse(passing.failed_distinct_keys)
        failing = build_brief(empty, ["id"], key="id", min_distinct_keys=1)
        self.assertTrue(failing.failed_distinct_keys)
        self.assertIn("Failed distinct business-key check", render(failing, False))
        missing_only = build_brief(
            [{"id": ""}, {"id": "NA"}],
            ["id"],
            key="id",
            max_missing=1,
            min_distinct_keys=1,
        )
        self.assertEqual(missing_only.distinct_keys, 0)
        self.assertTrue(missing_only.failed_distinct_keys)

    def test_default_output_and_other_gates_remain_independent(self) -> None:
        rows = [{"id": "A"}, {"id": "A"}, {"id": "B"}]
        original = build_brief(rows, ["id"], key="id")
        self.assertNotIn("min_distinct_keys", original.to_dict())
        self.assertNotIn("distinct_keys", original.to_dict())
        self.assertNotIn("failed_distinct_keys", original.to_dict())
        self.assertNotIn("Minimum distinct complete business keys", render(original, False))
        report = build_brief(
            rows,
            ["id"],
            key="id",
            min_distinct_keys=2,
            min_complete_keys=3,
            max_duplicates=0,
        )
        self.assertFalse(report.failed_distinct_keys)
        self.assertFalse(report.failed_complete_keys)
        self.assertTrue(report.failed_duplicates)

    def test_invalid_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "min_distinct_keys must be 0 or greater"):
            build_brief([{"id": "A"}], ["id"], key="id", min_distinct_keys=-1)
        with self.assertRaisesRegex(ValueError, "min_distinct_keys requires --key"):
            build_brief([{"id": "A"}], ["id"], min_distinct_keys=1)

    def test_cli_json_markdown_and_configuration_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "orders.csv"
            path.write_text(
                "order,line\nA,1\nA,1\nA,2\n,9\n", encoding="utf-8"
            )
            base = [str(path), "--required", "order", "--max-missing", "1"]
            def execute(*opts: str) -> tuple[int, str, str]:
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = main([*base, *opts])
                return code, out.getvalue(), err.getvalue()

            good, stdout, stderr = execute(
                "--key", "order,line", "--min-distinct-keys", "2", "--json"
            )
            self.assertEqual((good, stderr), (0, ""))
            self.assertEqual(json.loads(stdout)["distinct_keys"], 2)
            self.assertFalse(json.loads(stdout)["failed_distinct_keys"])

            bad, markdown, stderr = execute(
                "--key", "order,line", "--min-distinct-keys", "3",
            )
            self.assertEqual((bad, stderr), (1, ""))
            self.assertIn("Failed distinct business-key check", markdown)

            for opts, msg in (
                (("--min-distinct-keys", "1"), "requires --key"),
                (("--key", "order", "--min-distinct-keys", "-1"), "0 or greater"),
            ):
                with self.subTest(opts=opts):
                    code, out, err = execute(*opts)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertIn(msg, err)


if __name__ == "__main__":
    unittest.main()
