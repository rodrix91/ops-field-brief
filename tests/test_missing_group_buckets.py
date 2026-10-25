"""Missing CSV group labels must not hide their combined concentration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, render

ROOT = Path(__file__).resolve().parents[1]


class MissingGroupBucketTests(unittest.TestCase):
    def test_all_missing_value_tokens_share_blank_group_bucket(self):
        tokens = ("", " ", "NA", "N/A", "null", "none", "s/d", "s.d.", "N/D", "N.D.", "-")
        rows = [{"buyer": value} for value in tokens] + [{"buyer": "Andes"}]
        brief = build_brief(rows, ["buyer"], group="buyer", max_missing=1.0)
        self.assertEqual(brief.fields[0].missing, len(tokens))
        self.assertEqual(brief.top, (("(blank)", len(tokens)), ("Andes", 1)))
        self.assertAlmostEqual(brief.top_group_share, len(tokens) / len(rows))
        self.assertEqual(brief.to_dict()["top"][0], {"value": "(blank)", "rows": len(tokens)})

    def test_missing_label_variants_cannot_bypass_concentration_gate(self):
        rows = [{"buyer": value} for value in ("NA", "N/A", "", "n/a")]
        failed = build_brief(rows, ["buyer"], group="buyer", max_missing=1, max_group_share=0.75)
        passed = build_brief(rows, ["buyer"], group="buyer", max_missing=1, max_group_share=1.0)
        self.assertEqual(failed.top, (("(blank)", 4),))
        self.assertEqual(failed.top_group_share, 1.0)
        self.assertTrue(failed.failed_group_share)
        self.assertFalse(passed.failed_group_share)
        self.assertIn("Failed group-concentration check", render(failed, as_json=False))

    def test_nonmissing_business_names_remain_separate(self):
        rows = [
            {"buyer": "NA Logistics"},
            {"buyer": "N/A Express"},
            {"buyer": "S/D Trading"},
            {"buyer": "NA Logistics"},
            {"buyer": " - "},
        ]
        brief = build_brief(rows, ["buyer"], group="buyer", max_missing=1)
        self.assertEqual(
            brief.top,
            (("NA Logistics", 2), ("N/A Express", 1), ("S/D Trading", 1), ("(blank)", 1)),
        )

    def test_cli_json_gate_and_top_zero_use_all_group_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.write_text('buyer\nN/A\nna\n""\nAndes\n', encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            cmd = [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "buyer",
                "--max-missing",
                "1",
                "--group",
                "buyer",
                "--max-group-share",
                "0.5",
                "--json",
            ]
            response = subprocess.run(
                cmd,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            hidden = subprocess.run(
                [*cmd, "--top", "0"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(response.returncode, 1, response.stderr)
        self.assertEqual(hidden.returncode, 1, hidden.stderr)
        payload = json.loads(response.stdout)
        self.assertEqual(payload["fields"][0]["missing"], 3)
        self.assertEqual(
            payload["top"],
            [{"value": "(blank)", "rows": 3}, {"value": "Andes", "rows": 1}],
        )
        self.assertEqual(payload["top_group_share"], 0.75)
        self.assertTrue(payload["failed_group_share"])
        self.assertEqual(json.loads(hidden.stdout)["top"], [])

    def test_literal_blank_group_does_not_merge_with_missing_bucket(self):
        rows = (
            [{"buyer": "(blank)"} for _ in range(3)]
            + [{"buyer": "NA"}, {"buyer": ""}]
            + [{"buyer": "Andes"}, {"buyer": "Andes"}]
        )
        brief = build_brief(
            rows, ["buyer"], group="buyer", max_missing=1.0, max_group_share=0.5
        )
        self.assertFalse(brief.failed_group_share)
        self.assertAlmostEqual(brief.top_group_share, 3 / 7)
        self.assertEqual(
            brief.top, (("(blank)", 3), ("(blank) [missing]", 2), ("Andes", 2))
        )
        self.assertEqual(brief.to_dict()["top"][1]["value"], "(blank) [missing]")

    def test_synthetic_missing_label_never_conflicts_with_real_labels(self):
        rows = [
            {"buyer": "(blank)"},
            {"buyer": "(blank) [missing]"},
            {"buyer": ""},
        ]
        brief = build_brief(rows, ["buyer"], group="buyer", max_missing=1.0)
        self.assertEqual(
            brief.top,
            (
                ("(blank)", 1),
                ("(blank) [missing]", 1),
                ("(blank) [missing 2]", 1),
            ),
        )

    def test_cli_literal_blank_label_does_not_create_false_concentration_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.write_text(
                'buyer\n(blank)\n(blank)\nNA\n""\nAndes\nAndes\n',
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "buyer",
                    "--group",
                    "buyer",
                    "--max-missing",
                    "1",
                    "--max-group-share",
                    "0.5",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["top_group_share"], round(2 / 6, 4))
        self.assertEqual(
            payload["top"],
            [
                {"value": "(blank)", "rows": 2},
                {"value": "(blank) [missing]", "rows": 2},
                {"value": "Andes", "rows": 2},
            ],
        )


if __name__ == "__main__":
    unittest.main()
