"""Regression tests for optional maximum CSV data-row quality gates."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class MaximumRowsTests(unittest.TestCase):
    def test_maximum_is_inclusive_and_independent_of_other_checks(self):
        rows = [{"shipment": "S1"}, {"shipment": "S2"}, {"shipment": "S3"}]
        passing = build_brief(rows, ["shipment"], min_rows=3, max_rows=3)
        self.assertEqual(passing.rows, 3)
        self.assertFalse(passing.failed_rows)
        self.assertFalse(passing.failed_max_rows)
        self.assertEqual(passing.to_dict()["max_rows"], 3)
        self.assertFalse(passing.to_dict()["failed_max_rows"])
        self.assertIn("- Maximum rows: 3", render(passing, False))
        self.assertNotIn("Failed maximum row-count check", render(passing, False))

        failing = build_brief(rows, ["shipment"], min_rows=1, max_rows=2)
        self.assertTrue(failing.failed_max_rows)
        self.assertFalse(failing.failed_rows)
        self.assertIn("Failed maximum row-count check", render(failing, False))
        self.assertIn("Rows (3) exceed the maximum (2)", render(failing, False))

    def test_zero_limit_accepts_header_only_export(self):
        empty = CsvRows([], ["shipment"])
        passed = build_brief(empty, ["shipment"], min_rows=0, max_rows=0)
        self.assertEqual(passed.rows, 0)
        self.assertFalse(passed.failed_max_rows)
        self.assertFalse(passed.failed_rows)

        exceeded = build_brief([{"shipment": "S1"}], ["shipment"], max_rows=0)
        self.assertTrue(exceeded.failed_max_rows)

    def test_original_output_contract_does_not_change_without_maximum(self):
        report = build_brief([{"shipment": "S1"}], ["shipment"], min_rows=1)
        self.assertNotIn("max_rows", report.to_dict())
        self.assertNotIn("failed_max_rows", report.to_dict())
        self.assertNotIn("Maximum rows", render(report, False))
        self.assertFalse(report.failed_max_rows)

    def test_invalid_and_unsatisfiable_boundaries(self):
        rows = [{"shipment": "S1"}]
        with self.assertRaisesRegex(ValueError, "max_rows must be 0 or greater"):
            build_brief(rows, ["shipment"], max_rows=-1)
        with self.assertRaisesRegex(ValueError, "min_rows cannot exceed max_rows"):
            build_brief(rows, ["shipment"], min_rows=2, max_rows=1)
        # Both boundaries of the valid range can be zero.
        accepted = build_brief(CsvRows([], ["shipment"]), ["shipment"], min_rows=0, max_rows=0)
        self.assertFalse(accepted.failed_rows or accepted.failed_max_rows)

    def test_cli_json_markdown_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,Andes\nS3,Paz\n", encoding="utf-8")
            base = [str(path), "--required", "shipment"]

            def run(args: list[str]) -> tuple[int, str, str]:
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    status = main(args)
                return status, stdout.getvalue(), stderr.getvalue()

            code, output, error = run([*base, "--max-rows", "3", "--json"])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["max_rows"], 3)
            self.assertFalse(json.loads(output)["failed_max_rows"])

            code, output, error = run([*base, "--max-rows", "2", "--json"])
            self.assertEqual((code, error), (1, ""))
            self.assertTrue(json.loads(output)["failed_max_rows"])

            code, output, error = run([*base, "--min-rows", "2", "--max-rows", "2"])
            self.assertEqual((code, error), (1, ""))
            self.assertIn("Failed maximum row-count check", output)

            code, output, error = run([*base, "--json"])
            self.assertEqual((code, error), (0, ""))
            self.assertNotIn("max_rows", json.loads(output))

            for options, expected in (
                ([*base, "--max-rows", "-1"], "0 or greater"),
                (
                    [*base, "--min-rows", "4", "--max-rows", "3"],
                    "min_rows cannot exceed max_rows",
                ),
            ):
                with self.subTest(options=options):
                    code, output, error = run(options)
                    self.assertEqual(code, 2)
                    self.assertEqual(output, "")
                    self.assertIn(expected, error)


if __name__ == "__main__":
    unittest.main()
