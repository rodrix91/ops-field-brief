"""Unit tests for the reproducible development requirements gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_dev_lock import check_versions, read_versions


class DevelopmentLockTests(unittest.TestCase):
    def test_pins_agree_with_hashed_transitive_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req, lock = root / "requirements-dev.txt", root / "requirements-dev.lock"
            req.write_text("coverage==7.16.2\nruff==0.17.2\n", encoding="utf-8")
            lock.write_text(
                "coverage==7.16.2 \\\n    --hash=sha256:abc\n"
                "ruff==0.17.2 \\\n    --hash=sha256:def\n"
                "typing-extensions==4.15.0 ; python_version < '3.13' \\\n"
                "    --hash=sha256:ghi\n",
                encoding="utf-8",
            )
            self.assertEqual(check_versions(req, lock), [])

    def test_stale_or_missing_pin_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req, lock = root / "requirements-dev.txt", root / "requirements-dev.lock"
            req.write_text("mypy==2.4.0\nruff==0.17.2\n", encoding="utf-8")
            lock.write_text("mypy==2.3.0 \\\n    --hash=sha256:abc\n", encoding="utf-8")
            self.assertEqual(
                check_versions(req, lock),
                [
                    "mypy: requirements-dev.txt specifies 2.4.0, lock has 2.3.0",
                    "ruff: requirements-dev.txt specifies 0.17.2, lock has missing",
                ],
            )

    def test_duplicate_normalized_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            req = Path(directory) / "requirements-dev.txt"
            req.write_text("my_pkg==1.0\nmy-pkg==1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate dependency my-pkg"):
                read_versions(req)

    def test_unpinned_and_empty_inputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            req = Path(directory) / "requirements-dev.txt"
            req.write_text("ruff>=0.17\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported requirement"):
                read_versions(req)
            req.write_text("# only a comment\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no pinned requirements"):
                read_versions(req)


if __name__ == "__main__":
    unittest.main()
