"""Relative duplicate-key gate regressions, including missing business identifiers."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class DuplicateShareTests(unittest.TestCase):
    def test_share_uses_complete_key_rows_not_the_whole_export(self):
        rows = [
            {"order": "A", "line": "1"},
            {"order": "A", "line": "1"},
            {"order": "B", "line": "2"},
            {"order": "C", "line": "NA"},
            {"order": "null", "line": "9"},
        ]
        passing = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            max_duplicates=1,
            max_duplicate_share=1 / 3,
        )
        self.assertEqual(passing.duplicate_keys, 1)
        self.assertEqual(passing.incomplete_key_rows, 2)
        self.assertEqual(passing.complete_key_rows, 3)
        self.assertAlmostEqual(passing.duplicate_share, 1 / 3)
        self.assertFalse(passing.failed_duplicate_share)
        self.assertFalse(passing.failed_duplicates)
        self.assertEqual(passing.to_dict()["duplicate_share"], 0.3333)
        self.assertIn("Rows with complete keys: 3", render(passing, False))

        failing = build_brief(
            rows,
            ["order"],
            key_fields=["order", "line"],
            max_missing=1,
            max_duplicate_share=0.3,
        )
        self.assertTrue(failing.failed_duplicate_share)
        self.assertIn("Failed duplicate-share check", render(failing, False))
        self.assertIn("exceeds the limit (30.0%)", render(failing, False))

    def test_all_incomplete_keys_fail_closed_only_when_nonempty(self):
        rows = [{"order": "NA"}, {"order": ""}]
        failed = build_brief(
            rows,
            ["order"],
            key="order",
            max_missing=1,
            max_duplicate_share=0,
        )
        self.assertEqual(failed.duplicate_keys, 0)
        self.assertEqual(failed.complete_key_rows, 0)
        self.assertTrue(failed.failed_duplicate_share)
        self.assertIn("No rows have a complete business key", render(failed, False))

        empty = build_brief(
            CsvRows([], ["order"]),
            ["order"],
            key="order",
            max_duplicate_share=0,
        )
        self.assertEqual(empty.complete_key_rows, 0)
        self.assertFalse(empty.failed_duplicate_share)

    def test_key_casefold_and_independent_absolute_limit(self):
        rows = [{"key": "Straße"}, {"key": "STRASSE"}]
        legacy = build_brief(rows, ["key"], key="key")
        self.assertNotIn("max_duplicate_share", legacy.to_dict())
        self.assertNotIn("complete_key_rows", legacy.to_dict())
        self.assertNotIn("duplicate_share", legacy.to_dict())
        self.assertNotIn("Maximum duplicate-key share", render(legacy, False))
        plain = build_brief(rows, ["key"], key="key", max_duplicate_share=0)
        self.assertEqual(plain.duplicate_keys, 0)
        self.assertFalse(plain.failed_duplicate_share)

        folded = build_brief(
            rows,
            ["key"],
            key="key",
            casefold_key=True,
            max_duplicate_share=0.5,
            max_duplicates=0,
        )
        self.assertEqual(folded.complete_key_rows, 2)
        self.assertEqual(folded.duplicate_share, 0.5)
        self.assertFalse(folded.failed_duplicate_share)
        self.assertTrue(folded.failed_duplicates)

    def test_invalid_library_gate_configuration(self):
        rows = [{"key": "A"}]
        for share in (-0.1, 1.1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(share=share):
                with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                    build_brief(rows, ["key"], key="key", max_duplicate_share=share)
        with self.assertRaisesRegex(ValueError, "requires --key"):
            build_brief(rows, ["key"], max_duplicate_share=0)

    def test_cli_pass_fail_json_and_configuration_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "orders.csv"
            path.write_text(
                "order,line\nA,1\nA,1\nB,2\nC,NA\n,9\n",
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

            def execute(args: list[str]) -> tuple[int, str, str]:
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = main(args)
                return code, out.getvalue(), err.getvalue()

            code, out, err = execute([*base, "--max-duplicate-share", "0.3"])
            self.assertEqual((code, err), (1, ""))
            payload = json.loads(out)
            self.assertEqual(payload["complete_key_rows"], 3)
            self.assertEqual(payload["duplicate_share"], 0.3333)
            self.assertTrue(payload["failed_duplicate_share"])
            code, out, err = execute([*base, "--max-duplicate-share", "0.34"])
            self.assertEqual((code, err), (0, ""))
            self.assertFalse(json.loads(out)["failed_duplicate_share"])

            for args, expected in (
                (
                    [str(path), "--required", "order", "--max-duplicate-share", "0"],
                    "requires --key",
                ),
                ([*base, "--max-duplicate-share", "-0.1"], "between 0 and 1"),
                ([*base, "--max-duplicate-share", "nan"], "between 0 and 1"),
            ):
                with self.subTest(args=args):
                    code, out, err = execute(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertIn(expected, err)


if __name__ == "__main__":
    unittest.main()
