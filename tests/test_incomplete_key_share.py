"""Regression tests for optional relative incomplete-business-key quality gates."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class IncompleteKeyShareTests(unittest.TestCase):
    def test_composite_key_percent_gate_is_independent_of_count_and_duplicate_gates(self):
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "B", "line": "NA"},
            {"order": "null", "line": "9"},
            {"order": "C", "line": "3"},
        ]
        arguments = {
            "key_fields": ["order", "line"],
            "max_missing": 1.0,
            "max_duplicates": 1,
            "max_duplicate_share": 0.34,
            "max_incomplete_keys": 2,
        }
        passing = build_brief(rows, ["order"], max_incomplete_key_share=0.4, **arguments)
        self.assertEqual(passing.incomplete_key_rows, 2)
        self.assertEqual(passing.duplicate_keys, 1)
        self.assertEqual(passing.incomplete_key_share, 0.4)
        self.assertFalse(passing.failed_incomplete_key_share)
        self.assertFalse(passing.failed_incomplete_keys)
        self.assertFalse(passing.failed_duplicates)
        self.assertFalse(passing.failed_duplicate_share)
        self.assertEqual(passing.to_dict()["max_incomplete_key_share"], 0.4)
        self.assertEqual(passing.to_dict()["incomplete_key_share"], 0.4)
        self.assertFalse(passing.to_dict()["failed_incomplete_key_share"])
        self.assertIn("Max allowed incomplete-key share: 40.0%", render(passing, False))

        failing = build_brief(rows, ["order"], max_incomplete_key_share=0.39, **arguments)
        self.assertTrue(failing.failed_incomplete_key_share)
        self.assertFalse(failing.failed_incomplete_keys)
        self.assertIn("Failed incomplete-key share check", render(failing, False))
        self.assertIn("exceeds the limit (39.0%)", render(failing, False))

    def test_all_missing_empty_and_complete_business_keys(self):
        rows = [{"order": " "}, {"order": "n/a"}]
        failing = build_brief(
            rows,
            ["order"],
            key="order",
            max_missing=1,
            max_incomplete_key_share=0.99,
        )
        self.assertEqual(failing.incomplete_key_share, 1.0)
        self.assertTrue(failing.failed_incomplete_key_share)
        accepted = build_brief(
            rows,
            ["order"],
            key="order",
            max_missing=1,
            max_incomplete_key_share=1,
        )
        self.assertFalse(accepted.failed_incomplete_key_share)

        empty = build_brief(
            CsvRows([], ["order"]),
            ["order"],
            key="order",
            max_incomplete_key_share=0,
        )
        self.assertEqual(empty.incomplete_key_share, 0)
        self.assertFalse(empty.failed_incomplete_key_share)

        complete = build_brief(
            [{"order": "A"}, {"order": "B"}],
            ["order"],
            key="order",
            max_incomplete_key_share=0,
        )
        self.assertFalse(complete.failed_incomplete_key_share)

    def test_default_json_and_markdown_unchanged_without_opt_in(self):
        plain = build_brief(
            [{"order": "A"}, {"order": ""}],
            ["order"],
            key="order",
            max_missing=1,
        )
        self.assertEqual(plain.incomplete_key_rows, 1)
        self.assertNotIn("max_incomplete_key_share", plain.to_dict())
        self.assertNotIn("incomplete_key_share", plain.to_dict())
        self.assertNotIn("failed_incomplete_key_share", plain.to_dict())
        self.assertNotIn("incomplete-key share", render(plain, False))
        self.assertFalse(plain.failed_incomplete_key_share)

    def test_invalid_thresholds_and_missing_key_are_usage_errors(self):
        rows = [{"order": "A"}]
        for share in (-0.1, 1.1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(share=share):
                with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                    build_brief(rows, ["order"], key="order", max_incomplete_key_share=share)
        with self.assertRaisesRegex(ValueError, "requires --key"):
            build_brief(rows, ["order"], max_incomplete_key_share=0)

    def test_cli_reports_exit_codes_and_optional_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            path.write_text(
                "order,line\nA,1\nA,1\nB,NA\nnull,9\nC,3\n",
                encoding="utf-8",
            )
            base = [
                str(path),
                "--required",
                "order",
                "--max-missing",
                "1",
                "--key",
                "order,line",
                "--json",
            ]

            def execute(arguments: list[str]) -> tuple[int, str, str]:
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    status = main(arguments)
                return status, stdout.getvalue(), stderr.getvalue()

            code, output, error = execute([*base, "--max-incomplete-key-share", "0.4"])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["incomplete_key_share"], 0.4)

            code, output, error = execute([*base, "--max-incomplete-key-share", "0.39"])
            self.assertEqual((code, error), (1, ""))
            self.assertTrue(json.loads(output)["failed_incomplete_key_share"])

            code, output, error = execute(base)
            self.assertEqual((code, error), (0, ""))
            self.assertNotIn("incomplete_key_share", json.loads(output))

            for arguments, expected in (
                ([*base, "--max-incomplete-key-share", "NaN"], "between 0 and 1"),
                ([*base, "--max-incomplete-key-share", "1.01"], "between 0 and 1"),
                (
                    [
                        str(path),
                        "--required",
                        "order",
                        "--max-incomplete-key-share",
                        "0",
                    ],
                    "requires --key",
                ),
            ):
                with self.subTest(arguments=arguments):
                    code, output, error = execute(arguments)
                    self.assertEqual(code, 2)
                    self.assertEqual(output, "")
                    self.assertIn(expected, error)

    def test_header_only_share_preserves_independent_minimum_row_gate(self):
        rows = CsvRows([], ["order"])
        brief = build_brief(
            rows,
            ["order"],
            key="order",
            max_incomplete_key_share=0,
            min_rows=1,
        )
        self.assertEqual(brief.incomplete_key_share, 0)
        self.assertFalse(brief.failed_incomplete_key_share)
        self.assertTrue(brief.failed_rows)
        self.assertIn("Failed row-count check", render(brief, False))

    def test_unicode_casefold_duplicates_do_not_inflate_incomplete_share(self):
        rows = [
            {"order": "Straße", "line": "01"},
            {"order": "STRASSE", "line": "01"},
            {"order": "NA", "line": "02"},
            {"order": " C ", "line": "03"},
        ]
        arguments = {
            "key_fields": ["order", "line"],
            "casefold_key": True,
            "max_missing": 1.0,
            "max_duplicates": 1,
        }
        passing = build_brief(rows, ["order"], max_incomplete_key_share=0.25, **arguments)
        self.assertEqual(passing.duplicate_keys, 1)
        self.assertEqual(passing.incomplete_key_rows, 1)
        self.assertEqual(passing.incomplete_key_share, 0.25)
        self.assertFalse(passing.failed_incomplete_key_share)
        self.assertFalse(passing.failed_duplicates)
        failing = build_brief(rows, ["order"], max_incomplete_key_share=0.24, **arguments)
        self.assertTrue(failing.failed_incomplete_key_share)
        self.assertFalse(failing.failed_duplicates)


if __name__ == "__main__":
    unittest.main()
