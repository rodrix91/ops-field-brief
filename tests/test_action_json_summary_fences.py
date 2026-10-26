"""Keep untrusted JSON text enclosed within its GitHub Actions job-summary fence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_action


class JsonSummaryFenceTests(unittest.TestCase):
    def _summary(self, data: str, *, is_json: bool = True) -> str:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.md"
            env = {
                "GITHUB_STEP_SUMMARY": str(target),
                "OPS_FIELD_BRIEF_INPUT_SUMMARY": "true",
            }
            with patch.dict(os.environ, env, clear=True):
                run_action._write_summary(data, is_json=is_json)
            return target.read_text(encoding="utf-8")

    def test_regular_json_retains_three_backtick_fence(self) -> None:
        payload = json.dumps({"rows": 1, "top": [{"value": "Andes", "rows": 1}]})
        self.assertEqual(
            self._summary(payload),
            "## ops-field-brief\n\n```json\n" + payload + "\n```\n",
        )

    def test_json_labels_with_backtick_runs_use_stronger_fence(self) -> None:
        for length in (1, 3, 4, 8, 32):
            with self.subTest(length=length):
                payload = json.dumps({"buyer": "`" * length + " # not a heading"})
                summary = self._summary(payload)
                fence = "`" * max(3, length + 1)
                self.assertEqual(
                    summary,
                    "## ops-field-brief\n\n" + fence + "json\n" + payload + "\n" + fence + "\n",
                )

    def test_fence_is_longer_than_the_longest_run_even_in_multiline_text(self) -> None:
        payload = '{\n  "buyer": "a```b",\n  "note": "cccc``````dddd"\n}'
        summary = self._summary(payload)
        self.assertTrue(summary.startswith("## ops-field-brief\n\n```````json\n"))
        self.assertTrue(summary.endswith(payload + "\n```````\n"))
        self.assertEqual(summary.count(payload), 1)

    def test_markdown_summary_output_is_unchanged(self) -> None:
        self.assertEqual(
            self._summary("# Original report\n", is_json=False),
            "## ops-field-brief\n\n# Original report\n",
        )


if __name__ == "__main__":
    unittest.main()
