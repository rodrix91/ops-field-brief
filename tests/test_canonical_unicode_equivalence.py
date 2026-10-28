"""Canonical Unicode equivalents must not evade opt-in operational quality gates."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.__main__ import main
from ops_field_brief.brief import build_brief, read_csv
from ops_field_brief.validation import validate_csv_structure


class CanonicalUnicodeCasefoldTests(unittest.TestCase):
    def test_opt_in_merges_composed_and_decomposed_business_values(self) -> None:
        rows = [
            {"order_id": "Café", "buyer": "Élite"},
            {"order_id": "Cafe\u0301", "buyer": "E\u0301lite"},
        ]
        plain = build_brief(
            rows, ["order_id"], key="order_id", group="buyer",
            max_duplicates=0, max_group_share=0.5, min_distinct_groups=2,
        )
        self.assertEqual(plain.duplicate_keys, 0)
        self.assertEqual(plain.distinct_groups, 2)
        self.assertFalse(plain.failed_group_share)
        self.assertFalse(plain.failed_distinct_groups)
        self.assertNotIn("casefold_key", plain.to_dict())
        self.assertNotIn("casefold_group", plain.to_dict())

        canonical = build_brief(
            rows, ["order_id"], key="order_id", group="buyer",
            max_duplicates=0, max_group_share=0.5, min_distinct_groups=2,
            casefold_key=True, casefold_group=True,
        )
        self.assertEqual(canonical.duplicate_keys, 1)
        self.assertTrue(canonical.failed_duplicates)
        self.assertEqual(canonical.distinct_groups, 1)
        self.assertEqual(canonical.top, (("élite", 2),))
        self.assertTrue(canonical.failed_group_share)
        self.assertTrue(canonical.failed_distinct_groups)
        self.assertEqual(canonical.key, "order_id")
        self.assertEqual(rows[1]["buyer"], "E\u0301lite")
        self.assertEqual(rows[1]["order_id"], "Cafe\u0301")

    def test_composite_keys_preserve_missing_component_accounting(self) -> None:
        rows = [
            {"id": "Cafe\u0301", "line": "A"},
            {"id": "CAFÉ", "line": "a"},
            {"id": "NA", "line": "A"},
        ]
        plain = build_brief(rows, ["id"], key_fields=["id", "line"])
        canonical = build_brief(
            rows, ["id"], key_fields=["id", "line"],
            casefold_key=True, max_duplicates=0, min_distinct_keys=2,
        )
        self.assertEqual(plain.duplicate_keys, 0)
        self.assertEqual(canonical.duplicate_keys, 1)
        self.assertEqual(canonical.distinct_keys, 1)
        self.assertTrue(canonical.failed_duplicates)
        self.assertTrue(canonical.failed_distinct_keys)
        self.assertEqual(canonical.incomplete_key_rows, 1)

    def test_nfc_does_not_fold_unrelated_compatibility_characters(self) -> None:
        rows = [
            {"id": "①", "group": "①"},
            {"id": "1", "group": "1"},
        ]
        folded = build_brief(
            rows, ["id"], key="id", group="group",
            casefold_key=True, casefold_group=True,
        )
        self.assertEqual(folded.duplicate_keys, 0)
        self.assertEqual(folded.distinct_groups, 2)

    def test_strict_header_collision_is_opt_in_and_original_names_remain(self) -> None:
        source = "id,Café,Cafe\u0301\nA,x,y\n"
        rows = read_csv(Path("-"), stdin=io.StringIO(source), strict=True)
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "Café", "Cafe\u0301"))
        self.assertEqual(rows[0]["Cafe\u0301"], "y")
        with self.assertRaisesRegex(ValueError, "duplicate CSV header columns: café"):
            validate_csv_structure(rows, casefold_headers=True)

    def test_cli_canonical_equivalence_changes_only_opt_in_quality_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "customers.csv"
            path.write_text(
                "id,buyer\nCafé,Élite\nCafe\u0301,E\u0301lite\n", encoding="utf-8"
            )
            common = [
                str(path), "--required", "id", "--key", "id", "--group", "buyer",
                "--max-duplicates", "0", "--max-group-share", "0.5",
                "--min-distinct-groups", "2", "--json",
            ]
            plain_out = io.StringIO()
            with contextlib.redirect_stdout(plain_out):
                plain_code = main(common)
            self.assertEqual(plain_code, 0)
            self.assertEqual(json.loads(plain_out.getvalue())["distinct_groups"], 2)

            canonical_out = io.StringIO()
            with contextlib.redirect_stdout(canonical_out):
                canonical_code = main([*common, "--casefold-key", "--casefold-group"])
            self.assertEqual(canonical_code, 1)
            report = json.loads(canonical_out.getvalue())
            self.assertEqual(report["duplicate_keys"], 1)
            self.assertEqual(report["distinct_groups"], 1)
            self.assertTrue(report["failed_group_share"])
            self.assertTrue(report["failed_distinct_groups"])
            self.assertEqual(report["top"], [{"value": "élite", "rows": 2}])

    def test_cli_canonical_duplicate_headers_fail_before_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.csv"
            path.write_text("id,Café,Cafe\u0301\nA,x,y\n", encoding="utf-8")
            common = [str(path), "--required", "id", "--strict-csv", "--json"]
            plain_out = io.StringIO()
            with contextlib.redirect_stdout(plain_out):
                self.assertEqual(main(common), 0)
            self.assertEqual(json.loads(plain_out.getvalue())["rows"], 1)
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                exit_code = main([*common, "--casefold-headers"])
            self.assertEqual(exit_code, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("duplicate CSV header columns: café", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
