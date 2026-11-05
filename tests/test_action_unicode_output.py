"""Ensure reusable Action subprocess output remains UTF-8 on every runner OS."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.brief import build_brief, render_markdown
from scripts import run_action

ROOT = Path(__file__).resolve().parents[1]


class ActionUnicodeOutputTests(unittest.TestCase):
    def test_main_forces_unicode_encoding_on_child_and_decodes_it_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            source = workspace / "envíos.csv"
            source.write_text("pedido,región\\nA,東京\\n", encoding="utf-8")
            output = Path(directory) / "action-output.txt"
            summary = Path(directory) / "summary.md"
            expected = render_markdown(
                build_brief([{"pedido": "A", "región": "東京"}], ["pedido"], group="región")
            )
            env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(ROOT),
                "OPS_FIELD_BRIEF_INPUT_PATH": "envíos.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required pedido --group región",
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "GITHUB_STEP_SUMMARY": str(summary),
                "PYTHONIOENCODING": "cp1252",
                "PYTHONPATH": "legacy-parent-path",
            }
            stdout = io.StringIO()
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=expected, stderr=""
            )
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(run_action.subprocess, "run", return_value=completed) as run,
                contextlib.redirect_stdout(stdout),
            ):
                self.assertEqual(run_action.main(), 0)
            options = run.call_args.kwargs
            self.assertEqual(options["encoding"], "utf-8")
            self.assertEqual(options["env"]["PYTHONIOENCODING"], "utf-8")
            self.assertEqual(options["env"]["PYTHONPATH"].split(os.pathsep)[0], str(ROOT / "src"))
            self.assertIn("東京", stdout.getvalue())
            self.assertIn("東京", summary.read_text(encoding="utf-8"))
            self.assertEqual(output.read_text(encoding="utf-8"), "exit-code=0\\npassed=true\\n")

    def test_actual_cli_preserves_non_ascii_report_under_a_legacy_parent_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / "envíos.csv").write_text(
                "pedido,región\\nA,東京\\nB,Bolivia\\n", encoding="utf-8"
            )
            output = Path(directory) / "action-output.txt"
            summary = Path(directory) / "summary.md"
            env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(ROOT),
                "OPS_FIELD_BRIEF_INPUT_PATH": "envíos.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required pedido --group región",
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "GITHUB_STEP_SUMMARY": str(summary),
                "PYTHONIOENCODING": "cp1252",
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.dict(os.environ, env, clear=True),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = run_action.main()
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertIn("東京", stdout.getvalue())
            self.assertIn("región", stdout.getvalue())
            self.assertIn("東京", summary.read_text(encoding="utf-8"))
            self.assertEqual(output.read_text(encoding="utf-8"), "exit-code=0\\npassed=true\\n")

    def test_action_entrypoint_explicitly_configures_utf8_for_its_own_console(self) -> None:
        workflow = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("PYTHONIOENCODING: utf-8", workflow)
