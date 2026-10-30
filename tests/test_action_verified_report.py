"""Reusable Action must never treat reportless or malformed results as checks."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.brief import build_brief, render_markdown
from scripts import run_action


class ActionVerifiedReportTests(unittest.TestCase):
    @staticmethod
    def _report(*, failing: bool = False) -> str:
        rows = [{"id": "A"}, {"id": "A"}] if failing else [{"id": "A"}]
        return json.dumps(build_brief(rows, ["id"], key="id", max_duplicates=0).to_dict()) + "\n"

    def test_valid_and_invalid_rendered_report_payloads(self) -> None:
        good = self._report()
        failed = self._report(failing=True)
        good_markdown = render_markdown(build_brief([{"id": "A"}], ["id"]))
        bad_markdown = render_markdown(build_brief([{"id": ""}], ["id"]))
        for payload, is_json, code, accepted in (
            ("", False, 0, False),
            ("   \t", False, 0, False),
            ("# Operational field brief\n", False, 0, False),
            (good_markdown, False, 0, True),
            (bad_markdown, False, 1, True),
            (bad_markdown, False, 0, False),
            (good_markdown, False, 1, False),
            ("completed successfully\n", False, 0, False),
            (good_markdown.split("## Required fields")[0], False, 0, False),
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

    def test_json_report_rejects_duplicate_keys_at_every_depth(self) -> None:
        clean = self._report()
        for marker in (
            '"rows": 1',
            '"name": "id"',
            '"filled": 1',
            '"failed_duplicates": false',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, clean)
                corrupted = clean.replace(marker, marker + ", " + marker, 1)
                self.assertFalse(
                    run_action._has_valid_report(corrupted, is_json=True, exit_code=0)
                )
        # A late conflicting value must not be allowed to overwrite a measured result.
        overwritten = clean.replace('"rows": 1', '"rows": 999, "rows": 1', 1)
        self.assertFalse(run_action._has_valid_report(overwritten, is_json=True))

    def test_markdown_report_requires_structural_measurements(self) -> None:
        source = render_markdown(build_brief([{"id": "A"}], ["id"]))
        for corrupted in (
            source.replace("- Rows: 1", "- Rows: unknown"),
            source.replace("| id | 1 | 0 |", "| id | 0 | 0 |"),
            source.replace("|---|---:|---:|---:|", "|---|---|---|---|"),
            source.replace("## Required fields", "## Missing fields"),
            source.replace("| id | 1 | 0 | 0.0% |", ""),
            source[:-1],
            "OK\n",
        ):
            with self.subTest(corrupted=corrupted):
                self.assertFalse(
                    run_action._has_valid_report(corrupted, is_json=False, exit_code=0)
                )
        empty = render_markdown(build_brief([], ["id"]))
        self.assertTrue(run_action._has_valid_report(empty, is_json=False, exit_code=0))

    def test_markdown_fails_closed_on_corrupt_percentages_and_duplicate_fields(self) -> None:
        good = render_markdown(build_brief([{"id": "A"}, {"id": ""}, {"id": "B"}], ["id"]))
        self.assertTrue(run_action._has_valid_report(good, is_json=False, exit_code=1))
        measured_row = "| id | 2 | 1 | 33.3% |"
        self.assertIn(measured_row, good)
        corrupted = (
            good.replace(measured_row, "| id | 2 | 1 | 0.0% |"),
            good.replace(measured_row, "| id | 2 | 1 | 33.4% |"),
            good.replace(measured_row, "| id | 2 | 1 | 333.3% |"),
            good.replace(measured_row, "| id | 2 | 1 | -1.0% |"),
            good.replace(measured_row, "| id | 2 | 1 | nan% |"),
            good.replace(measured_row, "| id | 2 | 1 | 33.33% |"),
            good.replace(measured_row, "| id | 02 | 1 | 33.3% |"),
            good.replace(measured_row, "| id | 2 | 01 | 33.3% |"),
            good.replace(measured_row, measured_row + "\n" + measured_row),
            good.replace(measured_row, "|   | 2 | 1 | 33.3% |"),
        )
        for report in corrupted:
            with self.subTest(report=report):
                self.assertFalse(run_action._has_valid_report(report, is_json=False, exit_code=1))
        empty = render_markdown(build_brief([], ["id"]))
        self.assertTrue(run_action._has_valid_report(empty, is_json=False, exit_code=0))
        escaped_name = render_markdown(build_brief([{"SLA|met": "yes"}], ["SLA|met"]))
        self.assertTrue(run_action._has_valid_report(escaped_name, is_json=False, exit_code=0))

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

    def test_json_report_rejects_corrupted_missingness_and_field_identity(self) -> None:
        clean = json.loads(self._report())
        base_field = clean["fields"][0]
        invalid_fields = (
            {"missing_rate": None},
            {"missing_rate": True},
            {"missing_rate": -0.1},
            {"missing_rate": 1.1},
            {"missing_rate": float("nan")},
            {"missing_rate": float("inf")},
            {"missing_rate": 0.5},
            {"missing_rate": "0.0"},
            {"missing_rate": 0.0, "name": ""},
            {"missing_rate": 0.0, "name": "  "},
        )
        for change in invalid_fields:
            with self.subTest(change=change):
                report = dict(clean, fields=[dict(base_field, **change)])
                self.assertFalse(run_action._has_valid_report(json.dumps(report), is_json=True))
        duplicated = dict(clean, fields=[base_field, dict(base_field)])
        self.assertFalse(run_action._has_valid_report(json.dumps(duplicated), is_json=True))
        for names in (["unknown"], ["id", "id"]):
            with self.subTest(failed_fields=names):
                report = dict(clean, failed_fields=names)
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(report), is_json=True, exit_code=1)
                )
        empty = json.loads(json.dumps(build_brief([], ["id"]).to_dict()))
        self.assertTrue(run_action._has_valid_report(json.dumps(empty), is_json=True))

    def test_json_report_requires_real_base_flags_and_key_counters(self) -> None:
        clean = json.loads(self._report())
        for missing in (
            "failed_duplicates",
            "failed_incomplete_keys",
            "duplicate_keys",
            "incomplete_key_rows",
            "key_fields",
            "key",
        ):
            with self.subTest(missing=missing):
                report = dict(clean)
                del report[missing]
                self.assertFalse(run_action._has_valid_report(json.dumps(report), is_json=True))

        changes = (
            {"failed_made_up": True},
            {"failed_made_up": False},
            {"duplicate_keys": True},
            {"duplicate_keys": -1},
            {"duplicate_keys": 2},
            {"incomplete_key_rows": True},
            {"incomplete_key_rows": -1},
            {"incomplete_key_rows": 2},
            {"key_fields": "id"},
            {"key_fields": [None]},
            {"key_fields": ["id", "id"]},
            {"key_fields": []},
            {"key": None},
            {"key": "other"},
            {"key_fields": ["other"]},
        )
        for change in changes:
            with self.subTest(change=change):
                report = dict(clean, **change)
                self.assertFalse(run_action._has_valid_report(json.dumps(report), is_json=True))

        # Optional named quality gates remain valid, including genuine failures.
        rows = [{"id": "A", "group": "north"}, {"id": "A", "group": ""}]
        for options in (
            {"max_duplicate_share": 0.1},
            {"min_complete_keys": 3},
            {"min_distinct_keys": 2},
            {"max_distinct_keys": 0},
            {"max_group_share": 0.4},
            {"max_assigned_group_share": 0.4},
            {"min_distinct_groups": 2},
            {"max_distinct_groups": 0},
            {"max_missing_group_share": 0.0},
        ):
            with self.subTest(options=options):
                report = build_brief(rows, ["id"], key="id", group="group", **options)
                self.assertTrue(
                    run_action._has_valid_report(
                        json.dumps(report.to_dict()), is_json=True, exit_code=1
                    )
                )

    def test_main_refuses_false_green_and_false_quality_failure(self) -> None:
        good = self._report()
        failed = self._report(failing=True)
        good_md = render_markdown(build_brief([{"id": "A"}], ["id"]))
        bad_md = render_markdown(build_brief([{"id": ""}], ["id"]))
        duplicate_json = good.replace('"rows": 1', '"rows": 1, "rows": 1', 1)
        scenarios = (
            (0, duplicate_json, "--json", 3, False),
            (0, "", "", 3, False),
            (0, "   \n", "", 3, False),
            (0, "{not json", "--json", 3, False),
            (0, "[]", "--js", 3, False),
            (1, "", "--required id", 3, False),
            (0, good_md, "", 0, True),
            (1, bad_md, "--required id", 1, True),
            (0, "# Operational field brief\n", "", 3, False),
            (0, "OK\n", "", 3, False),
            (1, good_md, "--required id", 3, False),
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
