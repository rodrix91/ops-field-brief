"""Explicit case-insensitive business-key checks must not change the default audit."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import build_brief, render


class CasefoldBusinessKeyTests(unittest.TestCase):
    def test_opt_in_changes_duplicate_detection_without_rewriting_keys(self) -> None:
        rows = [
            {"order_id": "ORD-51"},
            {"order_id": " ord-51 "},
            {"order_id": "ORD-52"},
        ]
        original = build_brief(rows, ["order_id"], key="order_id", max_duplicates=0)
        self.assertEqual(original.duplicate_keys, 0)
        self.assertFalse(original.failed_duplicates)
        self.assertNotIn("casefold_key", original.to_dict())
        self.assertNotIn("Business-key comparison:", render(original, False))

        folded = build_brief(
            rows,
            ["order_id"],
            key="order_id",
            casefold_key=True,
            max_duplicates=0,
        )
        self.assertEqual(folded.duplicate_keys, 1)
        self.assertTrue(folded.failed_duplicates)
        self.assertEqual(folded.key, "order_id")
        self.assertEqual(folded.key_fields, ("order_id",))
        self.assertTrue(folded.to_dict()["casefold_key"])
        self.assertIn("Business-key comparison: case-insensitive", render(folded, False))

    def test_composite_keys_unicode_and_missing_values(self) -> None:
        rows = [
            {"order_id": "Straße", "line_id": "A"},
            {"order_id": "STRASSE", "line_id": "a"},
            {"order_id": "STRASSE", "line_id": "b"},
            {"order_id": "NA", "line_id": "A"},
            {"order_id": "n/a", "line_id": "a"},
        ]
        default = build_brief(rows, ["line_id"], key_fields=["order_id", "line_id"])
        self.assertEqual(default.duplicate_keys, 0)
        self.assertEqual(default.incomplete_key_rows, 2)

        folded = build_brief(
            rows,
            ["line_id"],
            key_fields=["order_id", "line_id"],
            casefold_key=True,
            max_duplicates=0,
            max_incomplete_keys=1,
        )
        self.assertEqual(folded.duplicate_keys, 1)
        self.assertEqual(folded.incomplete_key_rows, 2)
        self.assertTrue(folded.failed_duplicates)
        self.assertTrue(folded.failed_incomplete_keys)
        self.assertEqual(folded.key, "order_id,line_id")

    def test_requires_explicit_business_key_in_library_and_cli(self) -> None:
        rows = [{"order_id": "ORD-51"}]
        with self.assertRaisesRegex(ValueError, "casefold_key requires --key"):
            build_brief(rows, ["order_id"], casefold_key=True)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "orders.csv"
            path.write_text("order_id\nORD-51\nord-51\n", encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = main([str(path), "--required", "order_id", "--casefold-key", "--json"])
            self.assertEqual(status, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("requires --key", stderr.getvalue())

    def test_cli_opt_in_reports_duplicate_gate_and_preserves_default_json(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "orders.csv"
            path.write_text(
                "order_id,line_id\nStraße,A\nSTRASSE,a\nSTRASSE,b\n",
                encoding="utf-8",
            )
            args = [
                str(path),
                "--required",
                "order_id,line_id",
                "--key",
                "order_id,line_id",
                "--max-duplicates",
                "0",
                "--json",
            ]
            original = io.StringIO()
            with contextlib.redirect_stdout(original):
                baseline_status = main(args)
            self.assertEqual(baseline_status, 0)
            self.assertNotIn("casefold_key", json.loads(original.getvalue()))

            folded = io.StringIO()
            with contextlib.redirect_stdout(folded):
                folded_status = main([*args, "--casefold-key"])
            self.assertEqual(folded_status, 1)
            report = json.loads(folded.getvalue())
            self.assertEqual(report["duplicate_keys"], 1)
            self.assertEqual(report["key_fields"], ["order_id", "line_id"])
            self.assertTrue(report["casefold_key"])
            self.assertTrue(report["failed_duplicates"])


if __name__ == "__main__":
    unittest.main()
