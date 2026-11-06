"""Keep malformed CSV column selections from forging or flooding diagnostic logs."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import build_brief


class BoundedColumnSelectionDiagnosticsTests(unittest.TestCase):
    @staticmethod
    def _error(call) -> str:
        try:
            call()
        except ValueError as error:
            return str(error)
        raise AssertionError("expected a column-selection validation failure")

    def test_short_names_keep_actionable_error_messages(self) -> None:
        rows = [{"shipment": "S1", "buyer": "Andes"}]
        cases = (
            (lambda: build_brief(rows, ["shipment"], max_missing_columns={"other": 0.5}),
             "max_missing_columns must reference required fields: other"),
            (lambda: build_brief(rows, ["shipment", "shipment"]),
             "duplicate required fields: shipment"),
            (lambda: build_brief(rows, ["shipment"], key_fields=["buyer", "buyer"]),
             "duplicate key fields: buyer"),
            (lambda: build_brief(rows, ["shipment", "missing"]),
             "unknown columns: missing"),
        )
        for call, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self._error(call), expected)

    def test_column_error_kinds_bound_and_escape_malicious_names(self) -> None:
        rows = [{"shipment": "S1", "buyer": "Andes"}]
        column = "region\n::error::forged\r\x1b[31m\u202e" + "x" * 9000 + "PRIVATE-END"
        cases = (
            lambda: build_brief(rows, ["shipment"], max_missing_columns={column: 0.5}),
            lambda: build_brief(rows, [column, column]),
            lambda: build_brief(rows, ["shipment"], key_fields=[column, column]),
            lambda: build_brief(rows, ["shipment", column]),
            lambda: build_brief(rows, ["shipment"], key=column),
            lambda: build_brief(rows, ["shipment"], group=column),
        )
        for call in cases:
            with self.subTest(case=cases.index(call)):
                message = self._error(call)
                self.assertIn("[truncated]", message)
                self.assertNotIn("PRIVATE-END", message)
                self.assertNotIn("\n", message)
                self.assertNotIn("\r", message)
                self.assertNotIn("\x1b", message)
                self.assertNotIn("\u202e", message)
                self.assertLess(len(message), 230)

    def test_large_unknown_column_inventories_report_count(self) -> None:
        rows = [{"shipment": "S1"}]
        names = [f"missing{number}" for number in range(12)]
        message = self._error(lambda: build_brief(rows, ["shipment", *names]))
        self.assertEqual(
            message,
            "unknown columns: missing0, missing1, missing2 (+9 more)",
        )
        self.assertEqual(len(names), 12, "source selectors must never be changed")

    def test_cli_never_echoes_raw_bad_selectors_or_share_values(self) -> None:
        malicious = "secret\n::warning::forged\x1b\u202e" + "x" * 5000 + "PRIVATE-END"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            path.write_text("shipment,buyer\nS1,Andes\n", encoding="utf-8")
            base = [str(path), "--required", "shipment"]
            cases = (
                (base + ["--required", "shipment," + malicious], "unknown columns:"),
                (
                    base
                    + ["--max-missing-column", malicious + "=0.5",
                       "--max-missing-column", malicious + "=0.2"],
                    "duplicate --max-missing-column field:",
                ),
                (
                    base + ["--max-missing-column", "shipment=" + malicious],
                    "invalid --max-missing-column share:",
                ),
                (
                    base + ["--max-missing-column", malicious + "=0.5"],
                    "max_missing_columns must reference required fields:",
                ),
            )
            for args, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic):
                    output, errors = io.StringIO(), io.StringIO()
                    with (
                        contextlib.redirect_stdout(output),
                        contextlib.redirect_stderr(errors),
                    ):
                        result = main(args)
                    message = errors.getvalue()
                    self.assertEqual(result, 2)
                    self.assertEqual(output.getvalue(), "")
                    self.assertIn(diagnostic, message)
                    self.assertIn("[truncated]", message)
                    self.assertNotIn("PRIVATE-END", message)
                    self.assertNotIn("\x1b", message)
                    self.assertNotIn("\u202e", message)
                    self.assertEqual(message.count("\n"), 1)
                    self.assertLess(len(message), 260)


if __name__ == "__main__":
    unittest.main()
