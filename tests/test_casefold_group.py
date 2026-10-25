"""Opt-in casefolding prevents accidental counterparty splitting in group gates."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import build_brief, render


class CasefoldGroupTests(unittest.TestCase):
    def test_casefold_changes_concentration_and_diversity_not_missing_rate(self) -> None:
        rows = [
            {"shipment": "S1", "buyer": "ACME"},
            {"shipment": "S2", "buyer": "Acme"},
            {"shipment": "S3", "buyer": "strasse"},
            {"shipment": "S4", "buyer": "Straße"},
            {"shipment": "S5", "buyer": "NA"},
        ]
        options = {
            "group": "buyer",
            "max_group_share": 0.3,
            "min_distinct_groups": 3,
            "max_missing_group_share": 0.2,
            "top_n": 0,
        }
        plain = build_brief(rows, ["shipment"], **options)
        self.assertEqual(plain.distinct_groups, 4)
        self.assertAlmostEqual(plain.top_group_share, 0.2)
        self.assertFalse(plain.failed_group_share)
        self.assertFalse(plain.failed_distinct_groups)
        self.assertNotIn("casefold_group", plain.to_dict())
        self.assertNotIn("Group comparison:", render(plain, False))

        folded = build_brief(rows, ["shipment"], casefold_group=True, **options)
        self.assertEqual(folded.distinct_groups, 2)
        self.assertEqual(folded.missing_group_rows, 1)
        self.assertAlmostEqual(folded.missing_group_share, 0.2)
        self.assertAlmostEqual(folded.top_group_share, 0.4)
        self.assertTrue(folded.failed_group_share)
        self.assertTrue(folded.failed_distinct_groups)
        self.assertFalse(folded.failed_missing_group_share)
        self.assertEqual(folded.top, ())
        self.assertTrue(folded.to_dict()["casefold_group"])
        self.assertIn("Group comparison: case-insensitive", render(folded, False))
        self.assertIn("Failed group-concentration check", render(folded, False))
        self.assertIn("Failed group-diversity check", render(folded, False))

    def test_missing_bucket_remains_separate_from_real_blank_label_collisions(self) -> None:
        rows = [
            {"shipment": "1", "buyer": "(BLANK)"},
            {"shipment": "2", "buyer": "(blank) [missing]"},
            {"shipment": "3", "buyer": "(blank) [missing 2]"},
            {"shipment": "4", "buyer": "NA"},
            {"shipment": "5", "buyer": "N/A"},
        ]
        brief = build_brief(rows, ["shipment"], group="buyer", casefold_group=True)
        groups = dict(brief.top)
        self.assertEqual(groups["(blank)"], 1)
        self.assertEqual(groups["(blank) [missing]"], 1)
        self.assertEqual(groups["(blank) [missing 2]"], 1)
        self.assertEqual(groups["(blank) [missing 3]"], 2)
        self.assertEqual(brief.distinct_groups, 3)
        self.assertEqual(brief.missing_group_rows, 2)

    def test_requires_group_and_keeps_casefold_key_independent(self) -> None:
        rows = [{"shipment": "A", "buyer": "Acme"}, {"shipment": "a", "buyer": "ACME"}]
        with self.assertRaisesRegex(ValueError, "casefold_group requires --group"):
            build_brief(rows, ["shipment"], casefold_group=True)

        brief = build_brief(
            rows,
            ["shipment"],
            key="shipment",
            group="buyer",
            casefold_key=True,
            casefold_group=True,
        )
        self.assertEqual(brief.duplicate_keys, 1)
        self.assertEqual(brief.distinct_groups, 1)
        self.assertEqual(brief.top, (("acme", 2),))
        self.assertTrue(brief.to_dict()["casefold_key"])
        self.assertTrue(brief.to_dict()["casefold_group"])
        default_key = build_brief(rows, ["shipment"], key="shipment", group="buyer")
        self.assertEqual(default_key.duplicate_keys, 0)
        self.assertEqual(default_key.distinct_groups, 2)

    def test_cli_preserves_default_contract_and_enforces_opt_in_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "buyers.csv"
            path.write_text(
                "shipment,buyer\nS1,ACME\nS2,Acme\nS3,Other\nS4,NA\n",
                encoding="utf-8",
            )
            common = [
                str(path),
                "--required",
                "shipment",
                "--group",
                "buyer",
                "--max-group-share",
                "0.4",
                "--min-distinct-groups",
                "3",
                "--max-missing-group-share",
                "0.25",
                "--top",
                "0",
                "--json",
            ]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                plain_code = main(common)
            self.assertEqual(plain_code, 0)
            plain = json.loads(stdout.getvalue())
            self.assertEqual(plain["distinct_groups"], 3)
            self.assertEqual(plain["top"], [])
            self.assertNotIn("casefold_group", plain)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                folded_code = main([*common, "--casefold-group"])
            self.assertEqual(folded_code, 1)
            folded = json.loads(stdout.getvalue())
            self.assertEqual(folded["distinct_groups"], 2)
            self.assertEqual(folded["top_group_share"], 0.5)
            self.assertTrue(folded["failed_group_share"])
            self.assertTrue(folded["failed_distinct_groups"])
            self.assertEqual(folded["missing_group_rows"], 1)
            self.assertFalse(folded["failed_missing_group_share"])
            self.assertTrue(folded["casefold_group"])

            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                invalid_code = main(
                    [str(path), "--required", "shipment", "--casefold-group", "--json"]
                )
            self.assertEqual(invalid_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("casefold_group requires --group", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
