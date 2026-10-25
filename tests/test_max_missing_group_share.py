"""An opt-in gate for operational rows lacking assigned counterparties."""

from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import CsvRows, build_brief, render


class MissingGroupShareTests(unittest.TestCase):
    def test_missing_tokens_are_combined_and_literal_blank_is_a_real_group(self) -> None:
        values = ("Andes", "(blank)", "NA", "n/a", "s/d", " ", "")
        rows = [{"shipment": f"S{i}", "buyer": buyer} for i, buyer in enumerate(values)]
        allowed = build_brief(
            rows,
            ["shipment"],
            group="buyer",
            max_missing_group_share=5 / 7,
            min_distinct_groups=2,
            max_group_share=0.75,
            top_n=0,
        )
        self.assertEqual(allowed.missing_group_rows, 5)
        self.assertAlmostEqual(allowed.missing_group_share, 5 / 7)
        self.assertFalse(allowed.failed_missing_group_share)
        self.assertFalse(allowed.failed_distinct_groups)
        self.assertFalse(allowed.failed_group_share)
        self.assertEqual(allowed.top, ())
        self.assertEqual(allowed.to_dict()["missing_group_rows"], 5)
        self.assertEqual(allowed.to_dict()["missing_group_share"], round(5 / 7, 4))
        self.assertEqual(allowed.to_dict()["max_missing_group_share"], 5 / 7)
        self.assertIn("Observed missing-group share: 71.4%", render(allowed, False))

        failed = build_brief(rows, ["shipment"], group="buyer", max_missing_group_share=0.7)
        self.assertTrue(failed.failed_missing_group_share)
        self.assertIn("Failed missing-group check", render(failed, False))
        self.assertIn("exceeds the limit (70.0%)", render(failed, False))

    def test_all_missing_zero_threshold_and_empty_extract(self) -> None:
        rows = [{"buyer": "NA"}, {"buyer": "N/A"}, {"buyer": ""}]
        failed = build_brief(
            rows, ["buyer"], group="buyer", max_missing=1.0, max_missing_group_share=0
        )
        self.assertEqual(failed.missing_group_rows, 3)
        self.assertEqual(failed.missing_group_share, 1.0)
        self.assertTrue(failed.failed_missing_group_share)
        boundary = build_brief(
            rows, ["buyer"], group="buyer", max_missing=1.0, max_missing_group_share=1.0
        )
        self.assertFalse(boundary.failed_missing_group_share)

        empty = build_brief(
            CsvRows([], ["buyer"]),
            ["buyer"],
            group="buyer",
            max_missing_group_share=0,
            min_rows=1,
        )
        self.assertEqual(empty.missing_group_share, 0.0)
        self.assertEqual(empty.missing_group_rows, 0)
        self.assertFalse(empty.failed_missing_group_share)
        self.assertTrue(empty.failed_rows)

    def test_invalid_thresholds_require_group_and_leave_default_output_alone(self) -> None:
        rows = [{"buyer": "Andes"}]
        for value in (-0.1, 1.1, math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                    build_brief(rows, ["buyer"], group="buyer", max_missing_group_share=value)
        with self.assertRaisesRegex(ValueError, "requires --group"):
            build_brief(rows, ["buyer"], max_missing_group_share=0.2)

        old = build_brief(rows, ["buyer"], group="buyer")
        self.assertNotIn("missing_group_share", old.to_dict())
        self.assertNotIn("max_missing_group_share", old.to_dict())
        self.assertNotIn("Rows with missing group labels", render(old, False))
        self.assertFalse(old.failed_missing_group_share)

    def test_cli_gate_pass_fail_and_invalid_argument_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "buyers.csv"
            path.write_text(
                "shipment,buyer\nS1,Andes\nS2,NA\nS3,\nS4,(blank)\n",
                encoding="utf-8",
            )
            prefix = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--top",
                "0",
                "--json",
            ]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*prefix, "--max-missing-group-share", "0.5"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["missing_group_rows"], 2)
            self.assertEqual(payload["missing_group_share"], 0.5)
            self.assertEqual(payload["top"], [])
            self.assertFalse(payload["failed_missing_group_share"])

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*prefix, "--max-missing-group-share", "0.49"])
            self.assertEqual(code, 1)
            self.assertTrue(json.loads(stdout.getvalue())["failed_missing_group_share"])

            for args, diagnosis in (
                ([*prefix, "--max-missing-group-share", "NaN"], "between 0 and 1"),
                ([*prefix, "--max-missing-group-share", "-0.1"], "between 0 and 1"),
                ([*prefix, "--max-missing-group-share", "1.1"], "between 0 and 1"),
                (
                    [str(path), "--required", "shipment", "--max-missing-group-share", "0.2"],
                    "requires --group",
                ),
            ):
                with self.subTest(args=args):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = main(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn(diagnosis, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
