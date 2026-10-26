"""Reusable Action must never treat reportless or malformed results as checks."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_action


class ActionVerifiedReportTests(unittest.TestCase):
    def test_valid_and_invalid_rendered_report_payloads(self) -> None:
        for payload, is_json, accepted in (
            ("", False, False),
            ("   \t", False, False),
            ("# Operational field brief\n", False, True),
            ("", True, False),
            (" { ", True, False),
            ('["not a report"]', True, False),
            ('{"rows": 0, "fields": []}', True, True),
            ('{ "label": "A ``` markdown" }', True, True),
        ):
            with self.subTest(payload=payload, is_json=is_json):
                self.assertEqual(
                    run_action._has_valid_report(payload, is_json=is_json), accepted
                )

    def test_main_refuses_false_green_and_false_quality_failure(self) -> None:
        scenarios = (
            (0, "", "", 3, False),
            (0, "   \n", "", 3, False),
            (0, "{not json", "--json", 3, False),
            (0, "[]", "--js", 3, False),
            (1, "", "--required id", 3, False),
            (0, "# Operational field brief\n", "", 0, True),
            (0, '{"rows": 1, "fields": []}\n', "--js", 0, True),
            (1, '{"rows": 1, "fields": []}\n', "--json", 1, True),
            (2, "", "--required id", 2, False),
        )
        for code, payload, flags, expected, has_summary in scenarios:
            with self.subTest(code=code, payload=payload, flags=flags):
                with tempfile.TemporaryDirectory() as directory:
                    workspace = Path(directory) / "workspace"
                    workspace.mkdir()
                    (workspace / "orders.csv").write_text(
                        "id,buyer\nA,North\n", encoding="utf-8"
                    )
                    output = Path(directory) / "output.txt"
                    summary = Path(directory) / "summary.md"
                    env = {
                        "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                        "OPS_FIELD_BRIEF_INPUT_PATH": "orders.csv",
                        "OPS_FIELD_BRIEF_INPUT_ARGS": flags,
                        "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
                        "GITHUB_WORKSPACE": str(workspace),
                        "GITHUB_OUTPUT": str(output),
                        "GITHUB_STEP_SUMMARY": str(summary),
                    }
                    result = subprocess.CompletedProcess(
                        args=[], returncode=code, stdout=payload, stderr=""
                    )
                    with (
                        patch.dict(os.environ, env, clear=True),
                        patch.object(
                            run_action.subprocess, "run", return_value=result
                        ) as called,
                    ):
                        self.assertEqual(run_action.main(), expected)
                        called.assert_called_once()
                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        f"exit-code={expected}\n"
                        f"passed={'true' if expected == 0 else 'false'}\n",
                    )
                    self.assertEqual(summary.is_file(), has_summary)
                    if has_summary and "--json" in flags:
                        self.assertIn("json\n", summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
