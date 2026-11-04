"""Regression checks for mutated CSV row and source-line metadata."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from ops_field_brief.brief import CsvRows, read_csv
from ops_field_brief.validation import validate_csv_structure


class StrictCsvMetadataIntegrityTests(unittest.TestCase):
    def test_incomplete_or_extra_line_positions_fail_with_value_error(self) -> None:
        for positions in ((2,), (2, 3, 4), (2, 2), (3, 2), (0, 2), (-1, 2), (True, 2), ("2", 3)):
            with self.subTest(positions=positions):
                rows = CsvRows(
                    [{"id": "1", "buyer": "Andes"}, {"id": "2", "buyer": "Paz"}],
                    ["id", "buyer"],
                )
                rows.source_lines = positions
                with self.assertRaisesRegex(ValueError, "source line metadata"):
                    validate_csv_structure(rows)

    def test_line_position_metadata_must_be_a_sequence(self) -> None:
        rows = CsvRows([{"id": "1"}], ["id"])
        for invalid in (None, False, 4, "2", {"line": 2}):
            with self.subTest(invalid=invalid):
                rows.source_lines = invalid
                with self.assertRaisesRegex(ValueError, "source line metadata"):
                    validate_csv_structure(rows)

    def test_mutated_records_fail_with_clear_validation_error(self) -> None:
        for invalid in (None, "row", 3, (), ["not", "a", "mapping"]):
            with self.subTest(invalid=invalid):
                rows = CsvRows([{"id": "1"}], ["id"])
                rows[0] = invalid
                with self.assertRaisesRegex(ValueError, "CSV data row 1 must be a mapping"):
                    validate_csv_structure(rows)

    def test_corrupt_skipped_line_metadata_cannot_be_reported_as_real(self) -> None:
        for invalid in (None, "2", (0,), (-4,), (True,), (2, 2), (5, 3), ("2",)):
            with self.subTest(invalid=invalid):
                rows = CsvRows([{"id": "1"}], ["id"])
                rows.blank_source_lines = invalid
                with self.assertRaisesRegex(ValueError, "blank source line metadata"):
                    validate_csv_structure(rows)

    def test_real_multiline_positions_and_blank_line_errors_stay_unchanged(self) -> None:
        good = read_csv(Path("-"), stdin=io.StringIO('id,buyer\n1,"North\nSouth"\n2,Paz\n'))
        self.assertEqual(good.source_lines, (2, 4))
        validate_csv_structure(good)
        with_blank = read_csv(
            Path("-"), stdin=io.StringIO("id,buyer\n1,Andes\n\n2,Paz\n"), strict=True
        )
        self.assertEqual(with_blank.blank_source_lines, (3,))
        with self.assertRaisesRegex(ValueError, "blank CSV data row at source line 3"):
            validate_csv_structure(with_blank)


if __name__ == "__main__":
    unittest.main()
