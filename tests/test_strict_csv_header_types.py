"""Strict CSV validation reports malformed public header metadata clearly."""

from __future__ import annotations

import unittest

from ops_field_brief.brief import CsvRows
from ops_field_brief.validation import validate_csv_structure


class StrictCsvHeaderTypeTests(unittest.TestCase):
    def test_non_string_header_labels_raise_value_error(self) -> None:
        # Caller-constructed CsvRows can contain invalid header metadata,
        # unlike ordinary csv.DictReader headers, which are always strings.
        invalid = (0, 1, True, False, b"buyer", [], {}, object())
        for label in invalid:
            for casefold in (False, True):
                with self.subTest(label=repr(label), casefold=casefold):
                    record = {"id": "A1", "buyer": "Andes"}
                    rows = CsvRows([record.copy()], ("id", label, "buyer"))
                    with self.assertRaisesRegex(
                        ValueError, "CSV header at column 2 must be a string"
                    ):
                        validate_csv_structure(rows, casefold_headers=casefold)
                    self.assertEqual(rows, [record])

    def test_blank_string_header_keeps_existing_diagnostic(self) -> None:
        for label in ("", " ", "\t"):
            with self.subTest(label=repr(label)):
                rows = CsvRows([{"id": "A1"}], ("id", label))
                with self.assertRaisesRegex(ValueError, "blank CSV header at column 2"):
                    validate_csv_structure(rows)

    def test_valid_headers_still_pass_and_preserve_original_names(self) -> None:
        record = {"order id": "A1", "Región": "Tarija"}
        rows = CsvRows([record.copy()], tuple(record))
        for casefold in (False, True):
            with self.subTest(casefold=casefold):
                validate_csv_structure(rows, casefold_headers=casefold)
        self.assertEqual(rows.fieldnames, ("order id", "Región"))
        self.assertEqual(rows, [record])


if __name__ == "__main__":
    unittest.main()
