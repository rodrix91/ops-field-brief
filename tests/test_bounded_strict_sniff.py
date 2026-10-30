"""Keep strict delimiter sniffing bounded on long unquoted CSV records."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ops_field_brief.brief import _complete_sniff_records, read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class _BoundedReader(io.TextIOWrapper):
    """Replicate Path.open(newline="") including legacy bare-CR line boundaries."""

    def __init__(self, source: str) -> None:
        super().__init__(io.BytesIO(source.encode("utf-8")), encoding="utf-8", newline="")

    def read(self, size: int = -1) -> str:
        if size < 0:
            raise AssertionError("unexpected unbounded read() during strict delimiter detection")
        return super().read(size)


class BoundedStrictSniffTests(unittest.TestCase):
    def test_only_trim_after_two_complete_physical_lines(self) -> None:
        self.assertEqual(_complete_sniff_records("no newline"), "no newline")
        self.assertEqual(
            _complete_sniff_records("id,buyer\nA1,unfinished"), "id,buyer\nA1,unfinished"
        )
        self.assertEqual(
            _complete_sniff_records("id,buyer\rA1,Ana\rA2,unfinished"),
            "id,buyer\rA1,Ana\r",
        )
        self.assertEqual(
            _complete_sniff_records("id;buyer\r\nA1;Ana\r\nA2;unfinished"),
            "id;buyer\r\nA1;Ana\r\n",
        )

    def test_strict_file_sniffs_long_unquoted_records_without_read_to_eof(self) -> None:
        for separator in (",", ";", "\t", "|"):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(separator=repr(separator), newline=repr(newline)):
                    source = (
                        f"id{separator}buyer{newline}"
                        f"A1{separator}Andes{newline}"
                        f"A2{separator}Tarija{newline}"
                        f"A3{separator}" + "x" * 9000 + newline
                    )
                    with mock.patch.object(Path, "open", return_value=_BoundedReader(source)):
                        rows = read_csv(Path("virtual.csv"), delimiter=None, strict=True)
                    validate_csv_structure(rows)
                    self.assertEqual(rows.fieldnames, ("id", "buyer"))
                    self.assertEqual(len(rows), 3)
                    self.assertEqual(rows[2]["buyer"], "x" * 9000)
                    self.assertEqual(rows.source_lines, (2, 3, 4))

    def test_strict_auto_stdin_handles_the_same_partial_record(self) -> None:
        source = "id;buyer\nA1;Andes\nA2;Tarija\nA3;" + "x" * 9000 + "\n"
        rows = read_csv(Path("-"), delimiter=None, stdin=io.StringIO(source), strict=True)
        validate_csv_structure(rows)
        self.assertEqual(rows.fieldnames, ("id", "buyer"))
        self.assertEqual(rows[2]["buyer"], "x" * 9000)

    def test_long_quoted_field_retries_complete_sniff_and_preserves_first_extra_byte(self) -> None:
        value = "x" * 9000
        source = 'id,buyer\nA1,"' + value + '"\n'
        with mock.patch.object(Path, "open", return_value=io.StringIO(source)):
            rows = read_csv(Path("quoted.csv"), delimiter=None, strict=True)
        self.assertEqual(rows, [{"id": "A1", "buyer": value}])

    def test_exactly_sniff_window_size_does_not_discard_a_final_row(self) -> None:
        header = "id,buyer\n"
        row = "A1," + "x" * (8192 - len(header) - 3)
        source = header + row
        self.assertEqual(len(source), 8192)
        with mock.patch.object(Path, "open", return_value=_BoundedReader(source)):
            rows = read_csv(Path("exact.csv"), delimiter=None, strict=True)
        self.assertEqual(rows[0]["buyer"], "x" * (8192 - len(header) - 3))

    def test_malformed_quoted_row_after_sniff_window_remains_a_strict_error(self) -> None:
        source = 'id,buyer\nA1,Andes\nA2,Tarija\nA3,"' + "x" * 9000
        with mock.patch.object(Path, "open", return_value=_BoundedReader(source)):
            with self.assertRaises(csv.Error):
                read_csv(Path("broken.csv"), delimiter=None, strict=True)

    def test_ambiguous_delimiters_still_fail_closed(self) -> None:
        source = "id,buyer;city\nA1,Ana;Tarija\nA2,Luis;Salta\nA3," + "x" * 9000 + ";Jujuy\n"
        with mock.patch.object(Path, "open", return_value=io.StringIO(source)):
            with self.assertRaisesRegex(ValueError, "could not detect delimiter"):
                read_csv(Path("ambiguous.csv"), delimiter=None, strict=True)

    def test_cli_strict_auto_long_unquoted_field_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exports.csv"
            path.write_text(
                "id;buyer\nA1;Andes\nA2;Tarija\nA3;" + "x" * 9000 + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable, "-m", "ops_field_brief", str(path),
                    "--required", "id,buyer", "--delimiter", "auto",
                    "--strict-csv", "--json",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["rows"], 3)
        self.assertEqual(report["fields"][1]["filled"], 3)


if __name__ == "__main__":
    unittest.main()
