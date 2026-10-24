"""Missing-value tokens must not be mistaken for valid business keys."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief

ROOT = Path(__file__).resolve().parents[1]


class MissingKeyTokenTests(unittest.TestCase):
    def test_single_key_missing_tokens_are_incomplete(self):
        for token in ("NA", "N/A", "null", "none", "s/d", "N.D.", "-"):
            with self.subTest(token=token):
                rows = [{"order": token}, {"order": token}, {"order": "O-1"}]
                brief = build_brief(
                    rows, ["order"], key="order", max_missing=0,
                    max_incomplete_keys=1, max_duplicates=0,
                )
                self.assertEqual(brief.incomplete_key_rows, 2)
                self.assertEqual(brief.duplicate_keys, 0)
                self.assertTrue(brief.failed_incomplete_keys)
                self.assertFalse(brief.failed_duplicates)
                self.assertEqual(brief.failed_fields, ("order",))
                payload = brief.to_dict()
                self.assertEqual(payload["incomplete_key_rows"], 2)
                self.assertEqual(payload["duplicate_keys"], 0)

    def test_composite_key_matches_required_field_missing_rules(self):
        rows = [
            {"order": "O-1", "line": "1"},
            {"order": "O-1", "line": "1"},
            {"order": "O-2", "line": " NA "},
            {"order": "O-2", "line": "n/a"},
            {"order": "O-3", "line": "2"},
        ]
        brief = build_brief(
            rows, ["line"], key_fields=["order", "line"],
            max_incomplete_keys=0, max_duplicates=0,
        )
        self.assertEqual(brief.duplicate_keys, 1)
        self.assertEqual(brief.incomplete_key_rows, 2)
        self.assertTrue(brief.failed_incomplete_keys)
        self.assertTrue(brief.failed_duplicates)
        self.assertEqual(brief.failed_fields, ("line",))

    def test_cli_gate_exits_one_and_preserves_json(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            source = Path(directory) / "orders.csv"
            source.write_text("order\nN/A\nNA\nO-1\n", encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            cmd = [
                sys.executable, "-m", "ops_field_brief", str(source),
                "--required", "order", "--key", "order",
                "--max-incomplete-keys", "0", "--json",
            ]
            run = subprocess.run(
                cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )
        self.assertEqual(run.returncode, 1, run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual(payload["incomplete_key_rows"], 2)
        self.assertTrue(payload["failed_incomplete_keys"])
        self.assertEqual(payload["duplicate_keys"], 0)
        self.assertEqual(payload["fields"][0]["missing"], 2)


if __name__ == "__main__":
    unittest.main()
