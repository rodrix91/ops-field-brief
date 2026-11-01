"""Invisible format characters in source CSV must be visible in Markdown only."""

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
INVISIBLE = (0x00AD, 0x200B, *range(0x2060, 0x2065), 0xFEFF)


class MarkdownInvisibleFormatTests(unittest.TestCase):
    def test_group_values_show_markers_while_json_is_lossless(self) -> None:
        for codepoint in INVISIBLE:
            original = f"Andes{chr(codepoint)}Norte"
            with self.subTest(codepoint=codepoint):
                brief = build_brief(
                    [{"shipment": "S1", "buyer": original}],
                    ["shipment"],
                    group="buyer",
                )
                markdown = render(brief, as_json=False)
                self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"Andes[U+{codepoint:04X}]Norte", markdown)
                payload = json.loads(render(brief, as_json=True))
                self.assertEqual(payload["top"][0]["value"], original)

    def test_required_column_and_business_key_show_markers_only_in_markdown(self) -> None:
        for codepoint in INVISIBLE:
            original = f"order{chr(codepoint)}id"
            with self.subTest(codepoint=codepoint):
                brief = build_brief([{original: "A1"}], [original], key=original)
                markdown = render(brief, as_json=False)
                self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"order[U+{codepoint:04X}]id", markdown)
                payload = json.loads(render(brief, as_json=True))
                self.assertEqual(payload["key"], original)
                self.assertEqual(payload["fields"][0]["name"], original)

    def test_normal_multilingual_text_and_script_joiners_are_unchanged(self) -> None:
        original = "São Paulo 日本語 क्\u200dषि\u200c مشتری"
        brief = build_brief([{"id": "A1", "buyer": original}], ["id"], group="buyer")
        self.assertIn(original, render(brief, as_json=False))
        self.assertEqual(json.loads(render(brief, as_json=True))["top"][0]["value"], original)

    def test_cli_escapes_labels_in_markdown_but_preserves_json(self) -> None:
        buyer = "An\u200bdes\u00adNorte\u2060\u2063S.A.\ufeff"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(("shipment", "buyer"))
                writer.writerow(("S1", buyer))
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
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            markdown = subprocess.run(
                args, cwd=ROOT, env=env, capture_output=True, text=True, check=False
            )
            data = subprocess.run(
                [*args, "--json"], cwd=ROOT, env=env, capture_output=True, text=True, check=False
            )
        self.assertEqual(markdown.returncode, 0, markdown.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertIn("An[U+200B]des[U+00AD]Norte[U+2060][U+2063]S\\.A\\.[U+FEFF]", markdown.stdout)
        for codepoint in INVISIBLE:
            self.assertNotIn(chr(codepoint), markdown.stdout)
        self.assertEqual(json.loads(data.stdout)["top"][0]["value"], buyer)


if __name__ == "__main__":
    unittest.main()
