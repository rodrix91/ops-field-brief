"""Untrusted CSV bidirectional controls must not spoof rendered Markdown text."""

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
BIDI_CONTROLS = (0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x2070))


class MarkdownBidiControlsTests(unittest.TestCase):
    def test_all_direction_controls_are_visible_and_json_is_lossless(self) -> None:
        for codepoint in BIDI_CONTROLS:
            label = f"client{chr(codepoint)}north"
            with self.subTest(codepoint=codepoint):
                report = build_brief(
                    [{"shipment": "A1", "buyer": label}],
                    ["shipment"],
                    group="buyer",
                )
                markdown = render(report, as_json=False)
                self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"client[U+{codepoint:04X}]north", markdown)
                self.assertEqual(json.loads(render(report, as_json=True))["top"][0]["value"], label)

    def test_field_names_and_keys_are_visible_without_changing_json(self) -> None:
        field = "order\u202e_id"
        report = build_brief([{field: "A1"}], [field], key=field)
        markdown = render(report, as_json=False)
        self.assertIn("order[U+202E]_id", markdown)
        self.assertNotIn("\u202e", markdown)
        payload = json.loads(render(report, as_json=True))
        self.assertEqual(payload["key"], field)
        self.assertEqual(payload["fields"][0]["name"], field)

    def test_normal_multilingual_text_remains_intact(self) -> None:
        label = "مشتري São Paulo 日本語"
        report = build_brief([{"shipment": "A1", "buyer": label}], ["shipment"], group="buyer")
        self.assertIn(label, render(report, as_json=False))
        self.assertEqual(json.loads(render(report, as_json=True))["top"][0]["value"], label)

    def test_cli_sanitizes_markdown_and_preserves_json(self) -> None:
        label = "Andes\u202e[verified]\u2066 Norte"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shipments.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("shipment", "buyer"))
                writer.writerow(("A1", label))
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
                [*args, "--json"], cwd=ROOT, env=env, capture_output=True, text=True, check=False
            )
        self.assertEqual(markdown.returncode, 0, markdown.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertNotIn("\u202e", markdown.stdout)
        self.assertNotIn("\u2066", markdown.stdout)
        self.assertIn("[U+202E]", markdown.stdout)
        self.assertIn("[U+2066]", markdown.stdout)
        self.assertEqual(json.loads(data.stdout)["top"][0]["value"], label)


if __name__ == "__main__":
    unittest.main()
