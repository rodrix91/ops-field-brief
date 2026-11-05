"""Untrusted checkout files must not become executable Action Python modules."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.brief import build_brief, render_markdown
from scripts import run_action

ACTION_ROOT = Path(__file__).resolve().parents[1]


class ActionModuleIsolationTests(unittest.TestCase):
    def test_checked_out_package_cannot_shadow_trusted_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "untrusted-checkout"
            workspace.mkdir()
            fixture = workspace / "exports" / "shipments.csv"
            fixture.parent.mkdir()
            fixture.write_text("shipment,region\nA,東京\nB,Tarija\n", encoding="utf-8")

            # A malicious checked-out package wins over PYTHONPATH when the
            # child interpreter runs with its working directory at checkout.
            fake = workspace / "ops_field_brief"
            fake.mkdir()
            (fake / "__init__.py").write_text("", encoding="utf-8")
            execution_marker = root / "untrusted-module-executed.txt"
            (fake / "__main__.py").write_text(
                "from pathlib import Path\n"
                + f"Path({str(execution_marker)!r}).write_text('executed')\n"
                + "print('not an operational report')\n",
                encoding="utf-8",
            )

            outputs = root / "github-output.txt"
            summary = root / "github-summary.txt"
            env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(ACTION_ROOT),
                "OPS_FIELD_BRIEF_INPUT_PATH": "exports/shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment --group region --json",
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(outputs),
                "GITHUB_STEP_SUMMARY": str(summary),
                "PYTHONPATH": str(fake.parent),
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            # Retain Windows interpreter bootstrap variables while simulating
            # a hostile checkout and a custom parent PYTHONPATH.
            with (
                patch.dict(os.environ, env),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = run_action.main()

            self.assertEqual(result, 0, stderr.getvalue())
            self.assertFalse(execution_marker.exists(), "untrusted Python code ran")
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["rows"], 2)
            self.assertEqual(report["fields"][0]["name"], "shipment")
            self.assertIn("東京", [item["value"] for item in report["top"]])
            self.assertEqual(outputs.read_text(encoding="utf-8"), "exit-code=0\npassed=true\n")
            self.assertIn('"rows": 2', summary.read_text(encoding="utf-8"))

    def test_cli_subprocess_uses_action_directory_not_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "shipments.csv").write_text(
                "shipment\nA\n", encoding="utf-8"
            )
            env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(ACTION_ROOT),
                "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment",
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
                "GITHUB_WORKSPACE": str(workspace),
            }
            measured = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=render_markdown(build_brief([{"shipment": "A"}], ["shipment"])),
                stderr="",
            )
            with (
                patch.dict(os.environ, env),
                patch.object(run_action.subprocess, "run", return_value=measured) as run,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(run_action.main(), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[3], str((workspace / "shipments.csv").resolve()))
            self.assertEqual(run.call_args.kwargs["cwd"], ACTION_ROOT)
