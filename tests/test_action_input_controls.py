"""Prevent Action inputs from injecting extra workflow lines or bypassing CSV checks."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_action


class ActionInputControlTests(unittest.TestCase):
    def test_direct_path_and_argument_guards_reject_lf_cr_and_nul(self) -> None:
        for control in ("\n", "\r", "\x00"):
            for label, value in (
                ("path", f"exports/orders{control}::warning::fake.csv"),
                ("args", f"--required shipment{control}--max-rows 1"),
            ):
                with self.subTest(control=repr(control), label=label):
                    with self.assertRaisesRegex(ValueError, "line breaks or NUL"):
                        run_action._reject_input_controls(value, label)
            with self.subTest(control=repr(control), label="path resolver"):
                with self.assertRaisesRegex(ValueError, "line breaks or NUL"):
                    run_action._validated_csv_path(f"file{control}.csv", "/tmp/workspace")

    def test_ordinary_relative_paths_and_flags_remain_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            nested = workspace / "operación"
            nested.mkdir()
            path = nested / "envíos.csv"
            path.write_text("shipment\nA1\n", encoding="utf-8")
            self.assertEqual(
                run_action._validated_csv_path("operación/envíos.csv", directory),
                path.resolve(),
            )
            run_action._reject_input_controls("--required shipment --min-rows 1", "args")
            run_action._reject_input_controls("operación/envíos.csv", "path")

    def test_main_fails_closed_for_multiline_path_or_args_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / "shipments.csv").write_text("shipment\nA1\n", encoding="utf-8")
            output = Path(directory) / "github-output.txt"
            base_env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
                "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment",
            }
            for key, value in (
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\n::warning::fake.csv"),
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\rforged.csv"),
                ("OPS_FIELD_BRIEF_INPUT_ARGS", "--required shipment\n--max-rows 2"),
                ("OPS_FIELD_BRIEF_INPUT_ARGS", "--required shipment\r--max-rows 2"),
            ):
                with self.subTest(key=key, value=repr(value)):
                    output.write_text("", encoding="utf-8")
                    stderr = io.StringIO()
                    with (
                        patch.dict(os.environ, {**base_env, key: value}, clear=True),
                        patch.object(run_action.subprocess, "run") as subprocess_run,
                        contextlib.redirect_stderr(stderr),
                    ):
                        self.assertEqual(run_action.main(), 2)
                        subprocess_run.assert_not_called()
                    self.assertIn("line breaks or NUL", stderr.getvalue())
                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        "exit-code=2\npassed=false\n",
                    )

    def test_terminal_controls_fail_closed_without_changing_tab_behavior(self) -> None:
        for control in ("\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1b", "\x1f", "\x7f"):
            for label, value in (
                ("path", f"exports/shipments{control}fake.csv"),
                ("args", f"--required shipment{control}--max-rows 5"),
            ):
                with self.subTest(control=repr(control), label=label):
                    with self.assertRaisesRegex(ValueError, "terminal control characters"):
                        run_action._reject_input_controls(value, label)
            with self.subTest(control=repr(control), label="path resolver"):
                with self.assertRaisesRegex(ValueError, "terminal control characters"):
                    run_action._validated_csv_path(f"data{control}.csv", "/tmp/workspace")

        # A horizontal tab is a normal shlex delimiter and is not a log-control escape.
        run_action._reject_input_controls("--required\tshipment\t--min-rows 1", "args")
        with self.assertRaisesRegex(ValueError, "terminal control characters"):
            run_action._reject_input_controls("exports\t2026.csv", "path")

        # Ordinary Unicode names remain valid; C1 is not ordinary text.
        run_action._reject_input_controls("operación/輸送.csv", "path")

    def test_every_c1_control_is_rejected_in_paths_and_args(self) -> None:
        for codepoint in range(128, 160):
            control = chr(codepoint)
            for label in ("path", "args"):
                with self.subTest(codepoint=codepoint, label=label):
                    with self.assertRaisesRegex(ValueError, "terminal control characters"):
                        run_action._reject_input_controls(f"shipment{control}danger", label)
            with self.subTest(codepoint=codepoint, label="path resolver"):
                with self.assertRaisesRegex(ValueError, "terminal control characters"):
                    run_action._validated_csv_path(
                        f"exports/shipments{control}.csv", "/tmp/workspace"
                    )

    def test_main_blocks_terminal_controls_before_spawning_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / "shipments.csv").write_text("shipment\nA1\n", encoding="utf-8")
            output = Path(directory) / "github-output.txt"
            base_env = {
                "OPS_FIELD_BRIEF_ACTION_PATH": str(Path(__file__).resolve().parents[1]),
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
                "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment",
            }
            for key, value in (
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\x1b[31m.csv"),
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\x08.csv"),
                ("OPS_FIELD_BRIEF_INPUT_ARGS", "--required shipment\x07--min-rows 1"),
                ("OPS_FIELD_BRIEF_INPUT_ARGS", "--required shipment\x7f--min-rows 1"),
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\t2026.csv"),
                ("OPS_FIELD_BRIEF_INPUT_PATH", "shipments\x85fake.csv"),
                ("OPS_FIELD_BRIEF_INPUT_ARGS", "--required shipment\x9b--min-rows 1"),
            ):
                with self.subTest(key=key, value=repr(value)):
                    output.write_text("", encoding="utf-8")
                    stderr = io.StringIO()
                    with (
                        patch.dict(os.environ, {**base_env, key: value}, clear=True),
                        patch.object(run_action.subprocess, "run") as subprocess_run,
                        contextlib.redirect_stderr(stderr),
                    ):
                        self.assertEqual(run_action.main(), 2)
                        subprocess_run.assert_not_called()
                    self.assertIn("terminal control characters", stderr.getvalue())
                    # Never echo the untrusted control character to the log.
                    self.assertNotIn(value, stderr.getvalue())
                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        "exit-code=2\npassed=false\n",
                    )


if __name__ == "__main__":
    unittest.main()
