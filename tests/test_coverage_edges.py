"""Focused regression tests for previously uncovered edge branches."""

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief import __main__ as cli
from ops_field_brief.brief import build_brief, read_csv, render
from ops_field_brief.validation import validate_csv_structure


class CoverageEdgeTests(unittest.TestCase):
    def test_decoded_stdin_reuses_text_stream_without_buffer(self):
        stream = io.StringIO("id,buyer\n1,Andes\n")
        with patch.object(sys, "stdin", stream):
            self.assertIs(cli._decoded_stdin("utf-8"), stream)

    def test_build_brief_rejects_invalid_api_combinations(self):
        cases = (
            (
                lambda: build_brief([], []),
                "required fields are needed",
            ),
            (
                lambda: build_brief(
                    [{"id": "1"}],
                    ["id"],
                    key="id",
                    key_fields=["id"],
                ),
                "either key or key_fields",
            ),
            (
                lambda: build_brief(
                    [{"id": "1"}],
                    ["id"],
                    key_fields=[""],
                ),
                "key fields must not be blank",
            ),
        )
        for operation, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    operation()

    def test_none_cell_counts_as_missing(self):
        brief = build_brief([{"id": None}], ["id"])
        self.assertEqual(brief.fields[0].filled, 0)
        self.assertEqual(brief.fields[0].missing, 1)

    def test_stdin_auto_detection_with_non_utf8_encoding(self):
        rows = read_csv(
            Path("-"),
            delimiter=None,
            encoding="latin-1",
            stdin=io.StringIO("id;buyer\n1;Andes\n"),
        )
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(rows[0]["buyer"], "Andes")

    def test_explicit_delimiter_strips_bom_from_direct_stdin(self):
        rows = read_csv(
            Path("-"),
            delimiter=",",
            encoding="utf-8",
            stdin=io.StringIO("\ufeffid,buyer\n1,Andes\n"),
        )
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(rows[0]["id"], "1")

    def test_markdown_reports_group_share_limit_and_failure(self):
        brief = build_brief(
            [
                {"id": "1", "buyer": "A"},
                {"id": "2", "buyer": "A"},
                {"id": "3", "buyer": "B"},
            ],
            ["id", "buyer"],
            group="buyer",
            max_group_share=0.5,
        )
        text = render(brief, as_json=False)
        self.assertIn("Max allowed top-group share: 50.0%", text)
        self.assertIn("Observed top-group share: 66.7%", text)
        self.assertIn("Failed group-concentration check", text)

    def test_strict_validation_requires_parsed_header_metadata(self):
        with self.assertRaisesRegex(ValueError, "requires a parsed header"):
            validate_csv_structure([])


if __name__ == "__main__":
    unittest.main()
