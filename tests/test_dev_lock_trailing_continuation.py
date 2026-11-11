"""Regression coverage for truncated hashed development locks."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_dev_lock import read_hashed_versions


class TrailingLockContinuationTests(unittest.TestCase):
    def test_dangling_hash_continuation_fails(self) -> None:
        slash = chr(92)
        digest = "a" * 64
        for trailing in ("", "\n", "    # generated lock metadata\n"):
            with self.subTest(trailing=trailing), tempfile.TemporaryDirectory() as directory:
                lock = Path(directory) / "requirements-dev.lock"
                lock.write_text(
                    f"ruff==0.17.3 {slash}\n    --hash=sha256:{digest} {slash}\n" + trailing,
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "dangling line continuation"):
                    read_hashed_versions(lock)

    def test_complete_hashed_lock_passes(self) -> None:
        slash = chr(92)
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "requirements-dev.lock"
            lock.write_text(
                f"ruff==0.17.3 {slash}\n    --hash=sha256:{digest}\n",
                encoding="utf-8",
            )
            self.assertEqual(read_hashed_versions(lock), {"ruff": "0.17.3"})


if __name__ == "__main__":
    unittest.main()
