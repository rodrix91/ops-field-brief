"""Per-field missing-rate gates keep operational extracts from hiding critical blanks."""

from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import build_brief, render


class MissingColumnLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {"shipment": "S1", "buyer": "Andes", "eta": ""},
            {"shipment": "S2", "buyer": "Paz", "eta": "2026-10-26"},
        ]

    def test_override_allows_one_optional_field_without_relaxing_others(self) -> None:
        baseline = build_brief(self.rows, ["shipment", "buyer", "eta"])
        self.assertEqual(baseline.failed_fields, ("eta",))
        self.assertNotIn("max_missing_columns", baseline.to_dict())
        brief = build_brief(
            self.rows,
            ["shipment", "buyer", "eta"],
            max_missing_columns={"eta": 0.5},
        )
        self.assertEqual(brief.failed_fields, ())
        self.assertEqual(brief.to_dict()["max_missing_columns"], {"eta": 0.5})
        self.assertIn("Field-specific missing limits: eta: 50.0%", render(brief, False))

    def test_override_can_be_stricter_than_global_limit(self) -> None:
        brief = build_brief(
            self.rows,
            ["shipment", "eta"],
            max_missing=1.0,
            max_missing_columns={"eta": 0.0},
        )
        self.assertEqual(brief.failed_fields, ("eta",))

    def test_limits_follow_required_field_order_and_escape_markdown(self) -> None:
        rows = [{"shipment": "S1", "eta|urgent": ""}]
        brief = build_brief(
            rows,
            ["shipment", "eta|urgent"],
            max_missing_columns={"eta|urgent": 1.0, "shipment": 0.0},
        )
        self.assertEqual(
            list(brief.to_dict()["max_missing_columns"]),
            ["shipment", "eta|urgent"],
        )
        self.assertIn("eta\\|urgent: 100.0%", render(brief, False))

    def test_rejects_unknown_or_nonfinite_and_out_of_range_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "required fields: buyer"):
            build_brief(self.rows, ["shipment"], max_missing_columns={"buyer": 0.5})
        for limit in (math.nan, math.inf, -0.1, 1.1):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                    build_brief(
                        self.rows,
                        ["shipment", "eta"],
                        max_missing_columns={"eta": limit},
                    )

    def test_cli_gate_json_and_legacy_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("shipment,buyer,eta\\nS1,Andes,\\nS2,Paz,2026-10-26\\n", encoding="utf-8")
            baseline_stdout = io.StringIO()
            with contextlib.redirect_stdout(baseline_stdout):
                self.assertEqual(main([str(path), "--required", "shipment,buyer,eta", "--json"]), 1)
            self.assertNotIn("max_missing_columns", json.loads(baseline_stdout.getvalue()))
            passed_stdout = io.StringIO()
            with contextlib.redirect_stdout(passed_stdout):
                self.assertEqual(
                    main(
                        [
                            str(path),
                            "--required",
                            "shipment,buyer,eta",
                            "--max-missing-column",
                            "eta=0.5",
                            "--max-missing-column",
                            "buyer=0",
                            "--json",
                        ]
                    ),
                    0,
                )
            payload = json.loads(passed_stdout.getvalue())
            self.assertEqual(payload["max_missing_columns"], {"buyer": 0.0, "eta": 0.5})
            self.assertEqual(payload["failed_fields"], [])
            strict_stdout = io.StringIO()
            with contextlib.redirect_stdout(strict_stdout):
                self.assertEqual(
                    main(
                        [
                            str(path),
                            "--required",
                            "shipment,eta",
                            "--max-missing",
                            "1",
                            "--max-missing-column",
                            "eta=0",
                            "--json",
                        ]
                    ),
                    1,
                )
            self.assertEqual(json.loads(strict_stdout.getvalue())["failed_fields"], ["eta"])

    def test_cli_rejects_malformed_duplicate_and_unknown_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text("shipment,eta\\nS1,\\n", encoding="utf-8")
            cases = (
                (["eta"], "expects NAME=SHARE"),
                (["=0.5"], "expects NAME=SHARE"),
                (["eta="], "expects NAME=SHARE"),
                (["eta=oops"], "invalid --max-missing-column share"),
                (["eta=NaN"], "between 0 and 1"),
                (["eta=1.5"], "between 0 and 1"),
                (["buyer=0.5"], "required fields: buyer"),
                (["eta=0.5", "eta=0.2"], "duplicate --max-missing-column"),
            )
            for specs, message in cases:
                with self.subTest(specs=specs):
                    args = [str(path), "--required", "shipment,eta"]
                    for spec in specs:
                        args.extend(["--max-missing-column", spec])
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = main(args)
                    self.assertEqual(result, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn(message, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
