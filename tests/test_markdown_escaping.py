"""Markdown output must not interpret CSV content as links, headers or table cells."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, render

ROOT = Path(__file__).resolve().parents[1]


class MarkdownEscapingTests(unittest.TestCase):
    def test_normal_operational_labels_are_unchanged(self):
        report = build_brief(
            [{"shipment": "A1", "buyer": "Andes"}],
            ["shipment"],
            key="shipment",
            group="buyer",
        )
        output = render(report, as_json=False)
        self.assertIn("- Business key: shipment", output)
        self.assertIn("| shipment | 1 | 0 | 0.0% |", output)
        self.assertIn("- Andes: 1", output)

    def test_table_field_names_and_business_keys_escape_markdown(self):
        field = "order|line*<test>&"
        report = build_brief(
            [{field: ""}],
            [field],
            key=field,
        )
        output = render(report, as_json=False)
        expected = r"order\|line\*&lt;test\>&amp;"
        self.assertIn("- Business key: " + expected, output)
        self.assertIn("| " + expected + " | 0 | 1 | 100.0% |", output)
        self.assertIn("## Failed fill check\n\n" + expected, output)
        self.assertNotIn("| order|line", output)
        payload = json.loads(render(report, as_json=True))
        self.assertEqual(payload["key"], field)
        self.assertEqual(payload["failed_fields"], [field])
        self.assertEqual(payload["fields"][0]["name"], field)

    def test_multiline_and_link_like_group_values_stay_on_one_source_line(self):
        value = "[Open invoice](https://example.invalid)\n## APPROVED\n<script>&"
        report = build_brief(
            [{"buyer": value}],
            ["buyer"],
            group="buyer",
        )
        output = render(report, as_json=False)
        self.assertNotIn("\n## APPROVED\n", output)
        self.assertNotIn("[Open invoice](https://example.invalid)", output)
        self.assertIn(r"\[Open invoice\]\(https://example\.invalid\)", output)
        self.assertIn("&#10;##", output.replace(r"\#", "#"))
        self.assertIn("&lt;script", output)
        self.assertIn("&amp;", output)
        payload = json.loads(render(report, as_json=True))
        self.assertEqual(payload["top"][0]["value"], value)

    def test_cli_csv_fixture_preserves_json_and_sanitizes_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "operations.csv"
            risky = "- [Unsafe link](https://example.invalid)\r\n## NEW SECTION"
            with file.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("shipment", "buyer"))
                writer.writerow(("S1", risky))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            command = [
                sys.executable, "-m", "ops_field_brief", str(file),
                "--required", "shipment", "--group", "buyer",
            ]
            markdown = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )
            data = subprocess.run(
                [*command, "--json"],
                cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )
        self.assertEqual(markdown.returncode, 0, markdown.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertNotIn("\n## NEW SECTION", markdown.stdout)
        self.assertIn("&#13;&#10;", markdown.stdout)
        self.assertIn(r"\[Unsafe link\]", markdown.stdout)
        self.assertEqual(json.loads(data.stdout)["top"][0]["value"], risky)


if __name__ == "__main__":
    unittest.main()
