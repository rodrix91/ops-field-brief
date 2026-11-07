"""Untrusted encoding names must never forge multiline or oversized diagnostics."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from ops_field_brief.__main__ import main
from ops_field_brief.brief import read_csv


class BoundedEncodingDiagnosticTests(unittest.TestCase):
    def test_malformed_encoding_diagnostics_are_bounded_and_noninjectable(self) -> None:
        values = (
            "forged\\n::error::fake\\r\\x1b[31m\\u202eSECRET",
            "utf-8\\x00PRIVATE",
            "Z" * 129 + "PRIVATE-TAIL",
            "\\u202e" * 65,
        )
        for value in values:
            with self.subTest(encoding=value[:16]):
                stream = io.StringIO("id,buyer\\nA1,Andes\\n")
                with self.assertRaises(ValueError) as raised:
                    read_csv(Path("-"), stdin=stream, encoding=value)
                message = str(raised.exception)
                self.assertLess(len(message), 220)
                self.assertNotIn("\\n", message)
                self.assertNotIn("\\r", message)
                self.assertNotIn("\\x1b", message)
                self.assertNotIn("\\u202e", message)
                self.assertNotIn("PRIVATE-TAIL", message)
                self.assertEqual(stream.tell(), 0)

    def test_cli_stdin_rejects_bad_codec_without_reading_private_data(self) -> None:
        content = b"id,buyer\\nA1,Andes\\nPRIVATE-CONTENT\\n"
        for encoding in ("broken\\n::warning::fake", "utf-8\\x00PRIVATE", "X" * 10000):
            with self.subTest(encoding=encoding[:12]):
                stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8")
                stdout, stderr = io.StringIO(), io.StringIO()
                with (
                    patch("sys.stdin", stream),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    status = main(["-", "--required", "id", "--encoding", encoding])
                self.assertEqual(status, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stream.buffer.tell(), 0)
                message = stderr.getvalue()
                self.assertEqual(message.count("\\n"), 1)
                self.assertNotIn("::warning::fake\\n", message)
                self.assertNotIn("PRIVATE-CONTENT", message)
                self.assertLess(len(message), 240)
                stream.close()

    def test_valid_codec_aliases_still_parse_stdin(self) -> None:
        for codec in ("utf-8", "cp65001", "latin-1"):
            with self.subTest(codec=codec):
                rows = read_csv(
                    Path("-"),
                    stdin=io.StringIO("id,buyer\\nA1,Andes\\n"),
                    encoding=codec,
                )
                self.assertEqual(rows, [{"id": "A1", "buyer": "Andes"}])


if __name__ == "__main__":
    unittest.main()
