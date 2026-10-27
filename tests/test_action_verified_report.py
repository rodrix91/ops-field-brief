"""Reusable Action must never treat reportless or malformed results as checks."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.brief import build_brief
from scripts import run_action


class ActionVerifiedReportTests(unittest.TestCase):
    @staticmethod
    def _report(*, failing: bool = False) -> str:
        rows = [{"id": "A"}, {"id": "A"}] if failing else [{"id": "A"}]
        return json.dumps(build_brief(rows, ["id"], key="id", max_duplicates=0).to_dict()) + "\n"

    def test_valid_and_invalid_rendered_report_payloads(self) -> None:
        good = self._report()
        failed = self._report(failing=True)
        for payload, is_json, code, accepted in (
            ("", False, 0, False),
            ("   \t", False, 0, False),
            ("# Operational field brief\n", False, 0, True),
            ("", True, 0, False),
            (" { ", True, 0, False),
            ('["not a report"]', True, 0, False),
            ('{"rows": 0, "fields": []}', True, 0, False),
            (good, True, 0, True),
            (failed, True, 1, True),
            (failed, True, 0, False),
            (good, True, 1, False),
        ):
            with self.subTest(payload=payload, is_json=is_json, code=code):
                self.assertEqual(
                    run_action._has_valid_report(payload, is_json=is_json, exit_code=code),
                    accepted,
                )

    def test_json_report_shape_and_counts_fail_closed(self) -> None:
        clean = json.loads(self._report())
        invalid = (
            {"rows": True},
            {"rows": -1},
            {"rows": "1"},
            {"fields": []},
            {"fields": "not a list"},
            {"failed_fields": "id"},
            {"failed_fields": [3]},
            {"fields": [{"name": 3, "filled": 1, "missing": 0}]},
            {"fields": [{"name": "id", "filled": True, "missing": 0}]},
            {"fields": [{"name": "id", "filled": -1, "missing": 2}]},
            {"fields": [{"name": "id", "filled": 1, "missing": -1}]},
            {"fields": [{"name": "id", "filled": 0, "missing": 0}]},
            {"fields": ["not a field"]},
            {"failed_duplicates": "false"},
            {"failed_incomplete_keys": None},
        )
        for change in invalid:
            with self.subTest(change=change):
                report = dict(clean, **change)
                self.assertFalse(run_action._has_valid_report(json.dumps(report), is_json=True))
        for deleted in ("rows", "fields", "failed_fields"):
            with self.subTest(deleted=deleted):
                report = dict(clean)
                del report[deleted]
                self.assertFalse(run_action._has_valid_report(json.dumps(report), is_json=True))
        no_flags = {k: v for k, v in clean.items() if not k.startswith("failed_")}
        no_flags["failed_fields"] = []
        self.assertFalse(run_action._has_valid_report(json.dumps(no_flags), is_json=True))

    def test_main_refuses_false_green_and_false_quality_failure(self) -> None:
        good = self._report()
        failed = self._report(failing=True)
        scenarios = (
            (0, "", "", 3, False),
            (0, "   \n", "", 3, False),
            (0, "{not json", "--json", 3, False),
            (0, "[]", "--js", 3, False),
            (1, "", "--required id", 3, False),
            (0, "# Operational field brief\n", "", 0, True),
            (0, good, "--js", 0, True),
            (1, failed, "--json", 1, True),
            (0, failed, "--json", 3, False),
            (1, good, "--json", 3, False),
            (2, "", "--required id", 2, False),
        )
        for code, payload, flags, expected, has_summary in scenarios:
            with self.subTest(code=code, payload=payload, flags=flags):
                with tempfile.TemporaryDirectory() as directory:
                    workspace = Path(directory) / "workspace"
                    workspace.mkdir()
                    (workspace / "orders.csv").write_text("id,buyer\nA,North\n", encoding="utf-8")
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
                        patch.object(run_action.subprocess, "run", return_value=result) as called,
                    ):
                        self.assertEqual(run_action.main(), expected)
                        called.assert_called_once()
                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        f"exit-code={expected}\npassed={'true' if expected == 0 else 'false'}\n",
                    )
                    self.assertEqual(summary.is_file(), has_summary)
                    if has_summary and "--json" in flags:
                        self.assertIn("json\n", summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
