"""The Action must verify optional row-bound gates against actual measured rows."""

from __future__ import annotations

import json
import unittest

from ops_field_brief.brief import build_brief
from scripts import run_action


class ActionOptionalRowGatesTests(unittest.TestCase):
    @staticmethod
    def _report(*, count: int = 2, **limits: int) -> dict:
        rows = [{"id": str(n)} for n in range(count)]
        return build_brief(rows, ["id"], **limits).to_dict()

    def test_real_row_bounds_pass_with_correct_cli_exit_codes(self) -> None:
        cases = (
            (2, {}, 0),
            (2, {"min_rows": 0}, 0),
            (2, {"min_rows": 2}, 0),
            (2, {"min_rows": 3}, 1),
            (2, {"max_rows": 2}, 0),
            (2, {"max_rows": 1}, 1),
            (2, {"min_rows": 2, "max_rows": 2}, 0),
            (2, {"min_rows": 3, "max_rows": 4}, 1),
            (2, {"min_rows": 0, "max_rows": 1}, 1),
            (0, {"min_rows": 0, "max_rows": 0}, 0),
            (0, {"min_rows": 1}, 1),
            (0, {"max_rows": 0}, 0),
        )
        for count, limits, code in cases:
            with self.subTest(count=count, limits=limits):
                data = self._report(count=count, **limits)
                self.assertEqual(
                    data.get("failed_rows", False) or data.get("failed_max_rows", False),
                    code == 1,
                )
                self.assertTrue(
                    run_action._has_valid_report(json.dumps(data), is_json=True, exit_code=code)
                )

    def test_missing_or_phantom_row_gate_flags_are_rejected(self) -> None:
        for name, flag in (("min_rows", "failed_rows"), ("max_rows", "failed_max_rows")):
            for data in (
                self._report(**{name: 2}),
                self._report(**{name: 3 if name == "min_rows" else 1}),
            ):
                code = int(data[flag])
                for removed in (name, flag):
                    with self.subTest(name=name, removed=removed, code=code):
                        corrupt = dict(data)
                        del corrupt[removed]
                        self.assertFalse(
                            run_action._has_valid_report(
                                json.dumps(corrupt), is_json=True, exit_code=code
                            )
                        )
                for phantom in (False, True):
                    with self.subTest(name=name, phantom=phantom):
                        bare = self._report()
                        bare[flag] = phantom
                        self.assertFalse(
                            run_action._has_valid_report(json.dumps(bare), is_json=True)
                        )

    def test_malformed_limits_and_contradictory_failures_are_rejected(self) -> None:
        for name, flag, limit in (
            ("min_rows", "failed_rows", 3),
            ("max_rows", "failed_max_rows", 1),
        ):
            valid = self._report(**{name: limit})
            self.assertTrue(
                run_action._has_valid_report(json.dumps(valid), is_json=True, exit_code=1)
            )
            for wrong_limit in (None, -1, True, False, 1.0, "2", [], {}):
                with self.subTest(name=name, limit=wrong_limit):
                    corrupt = dict(valid, **{name: wrong_limit})
                    self.assertFalse(
                        run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=1)
                    )
            corrupt = dict(valid, **{flag: False})
            self.assertFalse(run_action._has_valid_report(json.dumps(corrupt), is_json=True))

            passing = self._report(**{name: 2})
            passing[flag] = True
            self.assertFalse(
                run_action._has_valid_report(json.dumps(passing), is_json=True, exit_code=1)
            )

    def test_impossible_joint_limits_cannot_claim_any_exit_code(self) -> None:
        valid = self._report(min_rows=2, max_rows=2)
        self.assertTrue(run_action._has_valid_report(json.dumps(valid), is_json=True))
        corrupt = dict(valid, min_rows=3, max_rows=1, failed_rows=True, failed_max_rows=True)
        for code in (0, 1):
            with self.subTest(exit_code=code):
                self.assertFalse(
                    run_action._has_valid_report(json.dumps(corrupt), is_json=True, exit_code=code)
                )


if __name__ == "__main__":
    unittest.main()
