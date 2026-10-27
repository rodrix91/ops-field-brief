"""Regression tests for the reusable Action's workspace input boundary."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.brief import build_brief, render_markdown
from scripts import run_action


class ActionPathTests(unittest.TestCase):
    def test_relative_file_stays_inside_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            nested = workspace / "exports"
            nested.mkdir(parents=True)
            csv_file = nested / "shipments.csv"
            csv_file.write_text("shipment,buyer\nA1,B1\n", encoding="utf-8")
            self.assertEqual(
                run_action._validated_csv_path("exports/shipments.csv", str(workspace)),
                csv_file.resolve(),
            )

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            outside = Path(temp) / "private.csv"
            outside.write_text("secret\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stay within GITHUB_WORKSPACE"):
                run_action._validated_csv_path("../private.csv", str(workspace))

    def test_rejects_absolute_path_even_when_inside_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            with self.assertRaisesRegex(ValueError, "must be relative"):
                run_action._validated_csv_path(str(workspace / "shipments.csv"), str(workspace))

    def test_rejects_symlink_outside_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            outside = Path(temp) / "private.csv"
            outside.write_text("secret\n", encoding="utf-8")
            link = workspace / "linked.csv"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("This runner does not permit symlink creation")
            with self.assertRaisesRegex(ValueError, "stay within GITHUB_WORKSPACE"):
                run_action._validated_csv_path("linked.csv", str(workspace))

    def test_rejects_stdin_and_missing_workspace(self):
        with self.assertRaisesRegex(ValueError, "must name a CSV file"):
            run_action._validated_csv_path("-", "/tmp/workspace")
        with self.assertRaisesRegex(ValueError, "GITHUB_WORKSPACE is required"):
            run_action._validated_csv_path("shipments.csv", None)

    def test_main_fails_before_subprocess_on_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            output = Path(temp) / "github-output.txt"
            env = {
                "OPS_FIELD_BRIEF_INPUT_PATH": "../private.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment",
                "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
            }
            with patch.dict(os.environ, env, clear=True):
                with patch.object(run_action.subprocess, "run") as mocked:
                    self.assertEqual(run_action.main(), 2)
                    mocked.assert_not_called()
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "exit-code=2\npassed=false\n",
            )

    def test_main_passes_resolved_workspace_file_to_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            csv_file = workspace / "shipments.csv"
            csv_file.write_text("shipment,buyer\nA1,B1\n", encoding="utf-8")
            output = Path(temp) / "github-output.txt"
            env = {
                "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment --strict-csv",
                "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
            }
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=render_markdown(build_brief([{"shipment": "A1"}], ["shipment"])),
                stderr="",
            )
            with patch.dict(os.environ, env, clear=True):
                with patch.object(run_action.subprocess, "run", return_value=completed) as mocked:
                    self.assertEqual(run_action.main(), 0)
                    command = mocked.call_args.args[0]
                    self.assertEqual(command[3], str(csv_file.resolve()))
                    self.assertEqual(command[4:], ["--required", "shipment", "--strict-csv"])
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "exit-code=0\npassed=true\n",
            )

    def test_informational_flags_fail_closed_before_subprocess(self):
        """Help and version should not turn an unchecked CSV into a green Action."""
        raw_inputs = (
            "-h",
            "--help",
            "--hel",
            "--he",
            "--h",
            "--version",
            "--vers",
            "--ver",
            "--v",
            "--required shipment --version",
        )
        for raw_args in raw_inputs:
            with self.subTest(raw_args=raw_args):
                with tempfile.TemporaryDirectory() as temp:
                    workspace = Path(temp) / "workspace"
                    workspace.mkdir()
                    (workspace / "shipments.csv").write_text(
                        "shipment,buyer\nA1,B1\n", encoding="utf-8"
                    )
                    output = Path(temp) / "github-output.txt"
                    env = {
                        "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                        "OPS_FIELD_BRIEF_INPUT_ARGS": raw_args,
                        "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                        "GITHUB_WORKSPACE": str(workspace),
                        "GITHUB_OUTPUT": str(output),
                        "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
                    }
                    with patch.dict(os.environ, env, clear=True):
                        with patch.object(run_action.subprocess, "run") as mocked:
                            self.assertEqual(run_action.main(), 2)
                            mocked.assert_not_called()
                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        "exit-code=2\npassed=false\n",
                    )

    def test_normal_action_flags_are_not_blocked(self):
        run_action._reject_nonexecuting_flags(
            ["--required", "shipment", "--json", "--strict-csv", "--min-rows", "1"]
        )


if __name__ == "__main__":
    unittest.main()
