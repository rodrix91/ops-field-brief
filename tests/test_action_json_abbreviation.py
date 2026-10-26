"""Guard JSON summary fencing for argparse's accepted long-option abbreviations."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_action


class JsonAbbreviationSafetyTests(unittest.TestCase):
    def test_supported_json_prefixes_are_all_detected(self) -> None:
        for flag in ("--j", "--js", "--jso", "--json"):
            with self.subTest(flag=flag):
                self.assertTrue(run_action._requests_json(["--required", "shipment", flag]))

    def test_other_options_keep_markdown_summary(self) -> None:
        for args in (
            ["--required", "shipment"],
            ["--group", "buyer"],
            ["--strict-csv"],
            ["--json=invalid"],
            ["--joined"],
        ):
            with self.subTest(args=args):
                self.assertFalse(run_action._requests_json(args))

    def test_main_fences_untrusted_json_for_every_accepted_abbreviation(self) -> None:
        payload = json.dumps({"buyer": "supplier ```\n## forged heading"})
        for flag in ("--j", "--js", "--jso", "--json"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory) / "workspace"
                workspace.mkdir()
                (workspace / "shipments.csv").write_text(
                    "shipment,buyer\nA1,B1\n", encoding="utf-8"
                )
                summary = Path(directory) / "summary.md"
                output = Path(directory) / "outputs.txt"
                env = {
                    "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                    "GITHUB_WORKSPACE": str(workspace),
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                    "OPS_FIELD_BRIEF_INPUT_ARGS": f"--required shipment {flag}",
                    "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
                }
                done = subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")
                with (
                    patch.dict(os.environ, env, clear=True),
                    patch.object(run_action.subprocess, "run", return_value=done) as fake,
                ):
                    self.assertEqual(run_action.main(), 0)
                    self.assertIn(flag, fake.call_args.args[0])
                self.assertEqual(
                    summary.read_text(encoding="utf-8"),
                    "## ops-field-brief\n\n````json\n" + payload + "\n````\n",
                )
                self.assertEqual(
                    output.read_text(encoding="utf-8"),
                    "exit-code=0\npassed=true\n",
                )


if __name__ == "__main__":
    unittest.main()
