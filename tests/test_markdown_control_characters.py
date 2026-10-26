"""CSV control characters must not reach Markdown reports or workflow summaries."""

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


class MarkdownControlCharacterTests(unittest.TestCase):
    def test_all_c0_del_and_c1_controls_are_safely_encoded(self) -> None:
        for codepoint in (*range(32), *range(127, 160)):
            original = f"customer{chr(codepoint)}north"
            with self.subTest(codepoint=codepoint):
                report = build_brief(
                    [{"shipment": "A1", "buyer": original}],
                    ["shipment"],
                    group="buyer",
                )
                markdown = render(report, as_json=False)
                # Line feeds are part of the Markdown document structure;
                # only CSV-originated line feeds must be escaped.
                if codepoint != 10:
                    self.assertNotIn(chr(codepoint), markdown)
                self.assertIn(f"customer&#{codepoint};north", markdown)
                parsed_json = json.loads(render(report, as_json=True))
                self.assertEqual(parsed_json["top"][0]["value"], original)

    def test_field_names_and_keys_keep_original_values_in_json(self) -> None:
        original = "shipment\x1b\x07\x7f\x9b\x00"
        report = build_brief([{original: "X1"}], [original], key=original)
        markdown = render(report, as_json=False)
        self.assertIn("shipment&#27;&#7;&#127;&#155;&#0;", markdown)
        self.assertNotIn("\x1b", markdown)
        self.assertNotIn("\x07", markdown)
        self.assertNotIn("\x7f", markdown)
        self.assertNotIn("\x9b", markdown)
        self.assertNotIn("\x00", markdown)
        payload = json.loads(render(report, as_json=True))
        self.assertEqual(payload["key"], original)
        self.assertEqual(payload["fields"][0]["name"], original)

    def test_cli_preserves_original_csv_data_but_sanitizes_markdown(self) -> None:
        buyer = "Andes\x1b[31m\x08\x00\x7f\x9b\tNorte"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operators.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(("shipment", "buyer"))
                writer.writerow(("A1", buyer))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
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
                args,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            data = subprocess.run(
                [*args, "--json"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(markdown.returncode, 0, markdown.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        for char in ("\x1b", "\x08", "\x00", "\x7f", "\x9b", "\t"):
            self.assertNotIn(char, markdown.stdout)
        for codepoint in (27, 8, 0, 127, 155, 9):
            self.assertIn(f"&#{codepoint};", markdown.stdout)
        self.assertEqual(json.loads(data.stdout)["top"][0]["value"], buyer)


if __name__ == "__main__":
    unittest.main()
