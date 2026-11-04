"""Direct CSV entry points must reject special files before blocking on open()."""

from __future__ import annotations

import gzip
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import read_csv

ROOT = Path(__file__).resolve().parents[1]


class RegularCsvPathTests(unittest.TestCase):
    def _cli(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "ops_field_brief", str(path), "--required", "shipment"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )

    def test_direct_reader_rejects_directory_including_gzip_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name in ("orders.csv", "orders.csv.gz"):
                with self.subTest(name=name):
                    path = Path(directory) / name
                    path.mkdir()
                    with self.assertRaisesRegex(ValueError, "CSV input must be a regular file"):
                        read_csv(path)
                    result = self._cli(path)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("CSV input must be a regular file", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are unavailable on Windows")
    def test_fifo_without_writer_fails_promptly_for_api_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name in ("orders.csv", "orders.csv.gz"):
                with self.subTest(name=name):
                    path = Path(directory) / name
                    os.mkfifo(path)
                    with self.assertRaisesRegex(ValueError, "CSV input must be a regular file"):
                        read_csv(path)
                    # A blocking FIFO read would time out here if preflight were absent.
                    result = self._cli(path)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("CSV input must be a regular file", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_regular_csv_gzip_and_valid_symlink_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plain = root / "orders.csv"
            plain.write_text("shipment,buyer\nA1,Tarija\n", encoding="utf-8")
            compressed = root / "orders.csv.gz"
            compressed.write_bytes(gzip.compress(plain.read_bytes()))
            for path in (plain, compressed):
                with self.subTest(path=path.name):
                    rows = read_csv(path)
                    self.assertEqual(rows.fieldnames, ("shipment", "buyer"))
                    self.assertEqual(rows, [{"shipment": "A1", "buyer": "Tarija"}])
                    result = self._cli(path)
                    self.assertEqual(result.returncode, 0, result.stderr)

            link = root / "linked.csv"
            try:
                link.symlink_to(plain)
            except (OSError, NotImplementedError):
                pass  # Windows runners may not permit symlink creation.
            else:
                self.assertEqual(read_csv(link), read_csv(plain))
                self.assertEqual(self._cli(link).returncode, 0)

    def test_missing_file_keeps_existing_os_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.csv"
            with self.assertRaises(FileNotFoundError):
                read_csv(missing)
            result = self._cli(missing)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("CSV input must be a regular file", result.stderr)


if __name__ == "__main__":
    unittest.main()
