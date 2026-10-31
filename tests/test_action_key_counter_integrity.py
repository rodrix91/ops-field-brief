"""Fail closed on contradictory key accounting in reusable Action JSON reports."""

from __future__ import annotations

import json
import unittest

from ops_field_brief.brief import build_brief
from scripts import run_action


class ActionKeyCounterIntegrityTests(unittest.TestCase):
    @staticmethod
    def _data() -> dict:
        # One duplicate complete key, one incomplete key and one unique key.
        brief = build_brief(
            [{"id": "A"}, {"id": "A"}, {"id": ""}, {"id": "B"}],
            ["id"],
            key="id",
            max_duplicates=0,
            max_incomplete_keys=0,
        )
        return brief.to_dict()

    def test_genuine_reports_pass_with_and_without_key_gates(self) -> None:
        reports = [
            (build_brief([{"id": "A"}], ["id"]).to_dict(), 0),
            (build_brief([{"id": "A"}, {"id": "A"}], ["id"], key="id").to_dict(), 0),
            (self._data(), 1),
            (
                build_brief(
                    [{"id": "A"}, {"id": ""}],
                    ["id"],
                    key="id",
                    max_incomplete_keys=0,
                    max_missing=1,
                ).to_dict(),
                1,
            ),
            (
                build_brief(
                    [{"id": "A"}],
                    ["id"],
                    key="id",
                    max_duplicates=0,
                    max_incomplete_keys=0,
                ).to_dict(),
                0,
            ),
        ]
        for data, code in reports:
            with self.subTest(code=code, data=data):
                self.assertTrue(
                    run_action._has_valid_report(json.dumps(data), is_json=True, exit_code=code)
                )

    def test_duplicate_keys_cannot_exceed_complete_key_occurrences_minus_one(self) -> None:
        valid = self._data()
        self.assertTrue(run_action._has_valid_report(json.dumps(valid), is_json=True, exit_code=1))
        for change in (
            {"duplicate_keys": 3},  # 3 complete key rows cannot all repeat
            {"incomplete_key_rows": 3},  # only one complete row left
            {"duplicate_keys": 1, "incomplete_key_rows": 4},
        ):
            with self.subTest(change=change):
                corrupt = dict(valid, **change)
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=1)
                )

    def test_reported_duplicate_gate_must_match_count_and_configured_limit(self) -> None:
        valid = self._data()
        changes = (
            {"failed_duplicates": False},
            {"max_duplicates": None},
            {"max_duplicates": 1},
            {"max_duplicates": 2},
            {"max_duplicates": True},
            {"max_duplicates": -1},
            {"max_duplicates": 1.0},
            {"max_duplicates": "0"},
        )
        for change in changes:
            with self.subTest(change=change):
                corrupt = dict(valid, **change)
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=1)
                )

    def test_reported_incomplete_key_gate_must_match_count_and_limit(self) -> None:
        valid = self._data()
        changes = (
            {"failed_incomplete_keys": False},
            {"max_incomplete_keys": None},
            {"max_incomplete_keys": 1},
            {"max_incomplete_keys": 2},
            {"max_incomplete_keys": True},
            {"max_incomplete_keys": -1},
            {"max_incomplete_keys": 0.0},
            {"max_incomplete_keys": "0"},
        )
        for change in changes:
            with self.subTest(change=change):
                corrupt = dict(valid, **change)
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=1)
                )

    def test_required_limit_keys_and_nonkey_mode_are_checked(self) -> None:
        valid = self._data()
        for name in ("max_duplicates", "max_incomplete_keys"):
            with self.subTest(missing=name):
                corrupt = dict(valid)
                del corrupt[name]
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=1)
                )
        # The standalone Python API cannot legitimately enable key limits
        # while claiming that there are no key fields.
        without_key = build_brief([{"id": "A"}], ["id"]).to_dict()
        without_key["max_duplicates"] = 0
        self.assertFalse(run_action._has_valid_report(json.dumps(without_key), is_json=True))


if __name__ == "__main__":
    unittest.main()
