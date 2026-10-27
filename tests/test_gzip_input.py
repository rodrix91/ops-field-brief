"""Gzip-compressed CSV exports must share the normal operational parsing contract."""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv
from ops_field_brief.validation import validate_csv_structure

ROOT = Path(__file__).resolve().parents[1]


class CompressedCsvTests(unittest.TestCase):
    def _cli(self, path: Path, *flags: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment,buyer",
                *flags,
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_gzipped_utf8_bom_and_original_csv_match(self) -> None:
        data = "\ufeffshipment,buyer\nS1,Andes\nS2,Paz\n"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "shipments.csv"
            compressed = Path(directory) / "shipments.CSV.GZ"
            source.write_text(data, encoding="utf-8")
            compressed.write_bytes(gzip.compress(data.encode("utf-8")))
            rows = read_csv(compressed, strict=True)
            validate_csv_structure(rows)
            self.assertEqual(rows.fieldnames, ("shipment", "buyer"))
            self.assertEqual(rows, read_csv(source, strict=True))
            self.assertEqual(rows[0]["shipment"], "S1")

    def test_gzip_autodetects_semicolon_even_with_long_quoted_field(self) -> None:
        text = "shipment;buyer\nS1;\"" + ("x" * 9000) + "\"\nS2;Paz\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long.csv.gz"
            path.write_bytes(gzip.compress(text.encode("utf-8")))
            rows = read_csv(path, delimiter=None, strict=True)
            validate_csv_structure(rows)
            self.assertEqual(rows.fieldnames, ("shipment", "buyer"))
            self.assertEqual(rows[0]["buyer"], "x" * 9000)
            self.assertEqual(rows[1]["buyer"], "Paz")

    def test_gzip_cp1252_and_cli_auto_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "excel.csv.gz"
            path.write_bytes(gzip.compress("shipment;buyer\nS1;Peñaflor\n".encode("cp1252")))
            result = self._cli(
                path, "--delimiter", "auto", "--encoding", "cp1252", "--strict-csv", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["rows"], 1)
            self.assertEqual(report["fields"][1]["filled"], 1)

    def test_gzip_preserves_quality_failure_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv.gz"
            path.write_bytes(gzip.compress(b"shipment,buyer\nS1,Andes\nS2,\n"))
            result = self._cli(path, "--key", "shipment", "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["rows"], 2)
            self.assertEqual(report["failed_fields"], ["buyer"])

    def test_gzip_preserves_strict_csv_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ragged.csv.gz"
            path.write_bytes(gzip.compress(b"shipment,buyer\nS1,Andes,extra\n"))
            result = self._cli(path, "--strict-csv")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("more fields", result.stderr)

    def test_non_gzip_and_truncated_gzip_fail_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "damaged.csv.gz"
            valid = gzip.compress(b"shipment,buyer\nS1,Andes\n")
            for content in (b"not compressed", valid[:-8]):
                with self.subTest(case=content[:12]):
                    path.write_bytes(content)
                    result = self._cli(path, "--delimiter", "auto", "--json")
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
