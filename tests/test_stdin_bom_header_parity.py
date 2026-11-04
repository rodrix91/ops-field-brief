"""UTF-8 BOM handling must agree across stdin, plain files, and gzip exports."""

from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv

ROOT = Path(__file__).resolve().parents[1]


class StdinBomHeaderParityTests(unittest.TestCase):
    def _cli(
        self, path: str, payload: bytes | None, delimiter: str
    ) -> subprocess.CompletedProcess[bytes]:
        command = [
            sys.executable,
            "-m",
            "ops_field_brief",
            path,
            "--required",
            "shipment,buyer",
            "--strict-csv",
            "--json",
        ]
        if delimiter == "auto":
            command.extend(("--delimiter", "auto"))
        return subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            input=payload,
            capture_output=True,
            check=False,
            timeout=15,
        )

    def test_library_preserves_only_the_first_leading_bom_across_sources(self) -> None:
        for count in (0, 1, 2):
            for delimiter in (",", None):
                with (
                    self.subTest(boms=count, delimiter=delimiter),
                    tempfile.TemporaryDirectory() as root,
                ):
                    text = "\ufeff" * count + "shipment,buyer\nS1,Peñaflor\n"
                    raw = text.encode("utf-8")
                    plain = Path(root) / "orders.csv"
                    archive = Path(root) / "orders.csv.gz"
                    plain.write_bytes(raw)
                    archive.write_bytes(gzip.compress(raw))
                    local = read_csv(plain, delimiter=delimiter, strict=True)
                    zipped = read_csv(archive, delimiter=delimiter, strict=True)
                    piped = read_csv(
                        Path("-"), delimiter=delimiter, strict=True, stdin=io.StringIO(text)
                    )
                    expected_header = ("\ufeff" * max(0, count - 1) + "shipment", "buyer")
                    self.assertEqual(local.fieldnames, expected_header)
                    self.assertEqual(zipped.fieldnames, expected_header)
                    self.assertEqual(piped.fieldnames, expected_header)
                    self.assertEqual(local, zipped)
                    self.assertEqual(local, piped)
                    self.assertEqual(local[0]["buyer"], "Peñaflor")

    def test_cli_file_and_binary_stdin_agree_for_one_or_two_boms(self) -> None:
        for count in (1, 2):
            for delimiter in ("comma", "auto"):
                with (
                    self.subTest(boms=count, delimiter=delimiter),
                    tempfile.TemporaryDirectory() as root,
                ):
                    data = ("\ufeff" * count + "shipment,buyer\nS1,Andes\n").encode("utf-8")
                    source = Path(root) / "orders.csv"
                    source.write_bytes(data)
                    file_result = self._cli(str(source), None, delimiter)
                    stdin_result = self._cli("-", data, delimiter)
                    self.assertEqual(stdin_result.returncode, file_result.returncode)
                    self.assertEqual(stdin_result.stdout, file_result.stdout)
                    self.assertEqual(file_result.returncode, 0 if count == 1 else 2)
                    if count == 1:
                        report = json.loads(stdin_result.stdout)
                        self.assertEqual(report["rows"], 1)
                        self.assertEqual(report["fields"][0]["filled"], 1)
                    else:
                        self.assertEqual(stdin_result.stdout, b"")
                        self.assertIn(b"shipment", stdin_result.stderr)
                        self.assertNotIn(b"Traceback", stdin_result.stderr)

    def test_excel_separator_hint_is_not_unwrapped_by_multiple_boms(self) -> None:
        payload = "sep=;\nshipment;buyer\nS1;Andes\n"
        for count in (1, 2):
            with self.subTest(boms=count), tempfile.TemporaryDirectory() as root:
                data = ("\ufeff" * count + payload).encode("utf-8")
                source = Path(root) / "orders.csv"
                source.write_bytes(data)
                file_result = self._cli(str(source), None, "auto")
                stdin_result = self._cli("-", data, "auto")
                self.assertEqual(stdin_result.returncode, file_result.returncode)
                self.assertEqual(stdin_result.stdout, file_result.stdout)
                self.assertEqual(file_result.returncode, 0 if count == 1 else 2)


if __name__ == "__main__":
    unittest.main()
