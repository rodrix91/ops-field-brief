"""The reusable Action must not inspect external data through in-workspace hardlinks."""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import run_action


class HardlinkedActionInputTests(unittest.TestCase):
    def test_external_hardlink_is_rejected_before_starting_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            workspace = base / "workspace"
            workspace.mkdir()
            outside = base / "private-shipments.csv"
            secret = "shipment,private_note\nA1,DO-NOT-READ-PRIVATE-DATA\n"
            outside.write_text(secret, encoding="utf-8")
            alias = workspace / "shipments.csv"
            try:
                os.link(outside, alias)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"Hardlinks unavailable on this runner: {error}")
            self.assertEqual(alias.resolve(), workspace.resolve() / alias.name)
            self.assertGreater(alias.stat().st_nlink, 1)
            with self.assertRaisesRegex(ValueError, "must not be a hard-linked CSV"):
                run_action._validated_csv_path("shipments.csv", str(workspace))

            output = base / "github-output"
            env = {
                "OPS_FIELD_BRIEF_INPUT_PATH": "shipments.csv",
                "OPS_FIELD_BRIEF_INPUT_ARGS": "--required shipment",
                "OPS_FIELD_BRIEF_ACTION_PATH": str(base),
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "false",
            }
            stdout = StringIO()
            stderr = StringIO()
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(run_action.subprocess, "run") as spawned,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                self.assertEqual(run_action.main(), 2)
                spawned.assert_not_called()
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("must not be a hard-linked CSV", stderr.getvalue())
            self.assertNotIn("DO-NOT-READ-PRIVATE-DATA", stderr.getvalue())
            self.assertEqual(output.read_text(encoding="utf-8"), "exit-code=2\npassed=false\n")
            self.assertEqual(outside.read_text(encoding="utf-8"), secret)

    def test_multiple_links_inside_workspace_are_also_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            one = workspace / "one.csv"
            one.write_text("shipment\nA1\n", encoding="utf-8")
            two = workspace / "two.csv"
            try:
                os.link(one, two)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"Hardlinks unavailable on this runner: {error}")
            for name in ("one.csv", "two.csv"):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "must not be a hard-linked CSV"):
                        run_action._validated_csv_path(name, str(workspace))

    def test_single_link_regular_file_and_internal_symlink_remain_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            file = workspace / "shipments.csv"
            file.write_text("shipment\nA1\n", encoding="utf-8")
            self.assertEqual(run_action._validated_csv_path(file.name, root), file.resolve())
            alias = workspace / "shortcut.csv"
            try:
                alias.symlink_to(file)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"Symlinks unavailable on this runner: {error}")
            self.assertEqual(run_action._validated_csv_path(alias.name, root), file.resolve())


if __name__ == "__main__":
    unittest.main()
