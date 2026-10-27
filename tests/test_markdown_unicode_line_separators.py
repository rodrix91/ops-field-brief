"""Unicode line and paragraph separators in CSV must not split Markdown labels."""

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
SEPARATORS = (0x2028, 0x2029)


class MarkdownUnicodeLineSeparatorsTests(unittest.TestCase):
    def test_group_values_render_visibly_but_json_retains_original(self) -> None:
        for codepoint in SEPARATORS:
            with self.subTest(codepoint=codepoint):
                original = f"Andes{chr(codepoint)}Norte"
                report = build_brief(
                    [{"shipment": "A1", "buyer": original}],
                    ["shipment"],
                    group="buyer",
                )
                markdown = render(report, as_json=False)
                self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"Andes[U+{codepoint:04X}]Norte", markdown)
                self.assertEqual(
                    json.loads(render(report, as_json=True))["top"][0]["value"],
                    original,
                )

    def test_field_names_and_business_keys_are_safe_without_changing_json(self) -> None:
        for codepoint in SEPARATORS:
            with self.subTest(codepoint=codepoint):
                original = f"order{chr(codepoint)}id"
                report = build_brief([{original: "A1"}], [original], key=original)
                markdown = render(report, as_json=False)
                self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"order[U+{codepoint:04X}]id", markdown)
                payload = json.loads(render(report, as_json=True))
                self.assertEqual(payload["key"], original)
                self.assertEqual(payload["fields"][0]["name"], original)

    def test_csv_cli_markdown_sanitizes_separator_and_json_is_lossless(self) -> None:
        original = "Cliente\u2028Norte\u2029Sucursal"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(("shipment", "buyer"))
                writer.writerow(("A1", original))
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            args = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
            ]
            markdown = subprocess.run(
                args, cwd=ROOT, env=env, capture_output=True, text=True, check=False
            )
            data = subprocess.run(
                [*args, "--json"], cwd=ROOT, env=env, capture_output=True, text=True,
                check=False
            )
        self.assertEqual(markdown.returncode, 0, markdown.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertNotIn("\u2028", markdown.stdout)
        self.assertNotIn("\u2029", markdown.stdout)
        self.assertIn("Cliente[U+2028]Norte[U+2029]Sucursal", markdown.stdout)
        self.assertEqual(json.loads(data.stdout)["top"][0]["value"], original)


if __name__ == "__main__":
    unittest.main()
