"""Regression tests for the opt-in proportional incomplete-key gate."""

from __future__ import annotations

import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class IncompleteKeyShareTests(unittest.TestCase):
    def test_composite_keys_use_all_rows_and_keep_duplicate_gates_independent(self) -> None:
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "B", "line": "NA"},
            {"order": "", "line": "4"},
            {"order": "C", "line": "3"},
        ]
        result = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            max_duplicates=1,
            max_incomplete_keys=2,
            max_incomplete_key_share=0.3,
        )
        self.assertEqual(result.incomplete_key_rows, 2)
        self.assertAlmostEqual(result.incomplete_key_share, 0.4)
        self.assertTrue(result.failed_incomplete_key_share)
        self.assertFalse(result.failed_incomplete_keys)
        self.assertEqual(result.duplicate_keys, 1)
        self.assertFalse(result.failed_duplicates)
        self.assertEqual(result.to_dict()["incomplete_key_share"], 0.4)
        self.assertTrue(result.to_dict()["failed_incomplete_key_share"])
        markdown = render(result, False)
        self.assertIn("Observed incomplete-key share: 40.0%", markdown)
        self.assertIn("## Failed incomplete-key share check", markdown)

    def test_equal_limit_passes_and_zero_limit_fails_only_on_missing_keys(self) -> None:
        rows = [{"id": "AA"}, {"id": "NA"}, {"id": "BB"}, {"id": "N/A"}]
        equal = build_brief(rows, ["id"], key="id", max_missing=1, max_incomplete_key_share=0.5)
        self.assertFalse(equal.failed_incomplete_key_share)
        self.assertEqual(equal.incomplete_key_share, 0.5)
        strict = build_brief(rows, ["id"], key="id", max_missing=1, max_incomplete_key_share=0)
        self.assertTrue(strict.failed_incomplete_key_share)
        complete = build_brief([{"id": "AA"}], ["id"], key="id", max_incomplete_key_share=0)
        self.assertFalse(complete.failed_incomplete_key_share)

    def test_header_only_has_zero_share_and_can_be_rejected_by_min_rows(self) -> None:
        empty = CsvRows([], ["id"])
        result = build_brief(empty, ["id"], key="id", max_incomplete_key_share=0, min_rows=1)
        self.assertEqual(result.incomplete_key_share, 0)
        self.assertFalse(result.failed_incomplete_key_share)
        self.assertTrue(result.failed_rows)

    def test_default_report_schema_and_markdown_remain_unchanged(self) -> None:
        rows = [{"id": "A"}, {"id": ""}]
        report = build_brief(rows, ["id"], key="id", max_missing=1)
        payload = report.to_dict()
        self.assertEqual(payload["incomplete_key_rows"], 1)
        self.assertNotIn("max_incomplete_key_share", payload)
        self.assertNotIn("incomplete_key_share", payload)
        self.assertNotIn("failed_incomplete_key_share", payload)
        self.assertNotIn("Observed incomplete-key share", render(report, False))

    def test_invalid_shares_and_missing_key_rejected(self) -> None:
        rows = [{"id": "A"}]
        for value in (-0.1, 1.1, math.nan, math.inf, -math.inf):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "must be between 0 and 1"),
            ):
                build_brief(rows, ["id"], key="id", max_incomplete_key_share=value)
        with self.assertRaisesRegex(ValueError, "requires --key"):
            build_brief(rows, ["id"], max_incomplete_key_share=0.2)

    def test_cli_exits_one_with_json_and_keeps_other_gates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "orders.csv"
            source.write_text("order,line\nA,1\nA,1\nB,\n,9\nC,3\n", encoding="utf-8")
            base = [
                str(source),
                "--required",
                "order",
                "--max-missing",
                "1",
                "--key",
                "order,line",
                "--max-incomplete-keys",
                "2",
                "--json",
            ]
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([*base, "--max-incomplete-key-share", "0.3"])
            self.assertEqual(code, 1)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["incomplete_key_share"], 0.4)
            self.assertTrue(report["failed_incomplete_key_share"])
            self.assertFalse(report["failed_incomplete_keys"])
            self.assertEqual(report["duplicate_keys"], 1)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([*base, "--max-incomplete-key-share", "0.4"])
            self.assertEqual(code, 0)

    def test_cli_bad_threshold_and_absent_key_exit_two_without_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "orders.csv"
            source.write_text("id\nA\n", encoding="utf-8")
            for tail, expected in (
                (["--max-incomplete-key-share", "NaN", "--key", "id"], "between 0 and 1"),
                (["--max-incomplete-key-share", "0.3"], "requires --key"),
            ):
                with self.subTest(tail=tail):
                    output = io.StringIO()
                    errors = io.StringIO()
                    with redirect_stdout(output), redirect_stderr(errors):
                        code = main([str(source), "--required", "id", *tail, "--json"])
                    self.assertEqual(code, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn(expected, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
