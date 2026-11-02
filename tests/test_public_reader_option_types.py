"""Public CSV reader options must reject malformed types without consuming input."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv


class ReaderOptionTypeTests(unittest.TestCase):
    def test_encoding_type_rejected_before_reading_stdin(self) -> None:
        for value in (None, 12, True, b"utf-8", [], {}, 1.5):
            with self.subTest(value=repr(value)):
                stream = io.StringIO("id,buyer\nA1,Andes\n")
                with self.assertRaisesRegex(ValueError, "encoding must be a string"):
                    read_csv(Path("-"), stdin=stream, encoding=value)
                self.assertEqual(stream.tell(), 0)

    def test_delimiter_type_rejected_before_reading_stdin(self) -> None:
        for value in (12, True, b",", [], {}, 1.5):
            with self.subTest(value=repr(value)):
                stream = io.StringIO("id,buyer\nA1,Andes\n")
                with self.assertRaisesRegex(ValueError, "delimiter must be a string or None"):
                    read_csv(Path("-"), stdin=stream, delimiter=value)
                self.assertEqual(stream.tell(), 0)

    def test_strict_type_rejected_before_reading_stdin(self) -> None:
        for value in (None, 0, 1, "false", [], {}, 1.5):
            with self.subTest(value=repr(value)):
                stream = io.StringIO("id,buyer\nA1,Andes\n")
                with self.assertRaisesRegex(ValueError, "strict must be a boolean"):
                    read_csv(Path("-"), stdin=stream, strict=value)
                self.assertEqual(stream.tell(), 0)

    def test_invalid_options_precede_missing_file_errors(self) -> None:
        missing = Path("no-such-csv-file-for-option-validation.csv")
        for option, message in (
            ({"encoding": None}, "encoding must be a string"),
            ({"delimiter": []}, "delimiter must be a string or None"),
            ({"strict": "false"}, "strict must be a boolean"),
        ):
            with self.subTest(option=option):
                with self.assertRaisesRegex(ValueError, message):
                    read_csv(missing, **option)

    def test_valid_boolean_and_auto_options_keep_existing_behavior(self) -> None:
        for strict in (False, True):
            for delimiter in (",", None):
                with self.subTest(strict=strict, delimiter=delimiter):
                    stream = io.StringIO("id,buyer\nA1,Andes\nA2,Tarija\n")
                    rows = read_csv(
                        Path("-"),
                        stdin=stream,
                        delimiter=delimiter,
                        encoding="utf-8",
                        strict=strict,
                    )
                    self.assertEqual(rows.fieldnames, ("id", "buyer"))
                    self.assertEqual(rows, [
                        {"id": "A1", "buyer": "Andes"},
                        {"id": "A2", "buyer": "Tarija"},
                    ])


if __name__ == "__main__":
    unittest.main()
