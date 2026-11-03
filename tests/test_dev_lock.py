"""Unit tests for the reproducible development requirements gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_dev_lock import check_versions, read_hashed_versions, read_versions


class DevelopmentLockTests(unittest.TestCase):
    def test_pins_agree_with_hashed_transitive_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req, lock = root / "requirements-dev.txt", root / "requirements-dev.lock"
            req.write_text("coverage==7.16.2\nruff==0.17.2\n", encoding="utf-8")
            slash = chr(92)
            digest_a, digest_b, digest_c = "a" * 64, "b" * 64, "c" * 64
            hashed = (
                f"coverage==7.16.2 {slash}\n"
                f"    --hash=sha256:{digest_a}\n"
                f"ruff==0.17.2 {slash}\n"
                f"    --hash=sha256:{digest_b}\n"
                f"typing-extensions==4.15.0 ; python_version < '3.13' {slash}\n"
                f"    --hash=sha256:{digest_c}\n"
            )
            lock.write_text(hashed, encoding="utf-8")
            self.assertEqual(check_versions(req, lock), [])

    def test_stale_or_missing_pin_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req, lock = root / "requirements-dev.txt", root / "requirements-dev.lock"
            req.write_text("mypy==2.4.0\nruff==0.17.2\n", encoding="utf-8")
            slash = chr(92)
            digest = "a" * 64
            hashed = f"mypy==2.3.0 {slash}\n    --hash=sha256:{digest}\n"
            lock.write_text(hashed, encoding="utf-8")
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

    def test_matching_versions_without_hashes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements-dev.txt"
            lock = root / "requirements-dev.lock"
            requirements.write_text("ruff==0.17.2\n", encoding="utf-8")
            lock.write_text("ruff==0.17.2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ruff lacks a SHA-256 hash"):
                check_versions(requirements, lock)

    def test_malformed_and_orphaned_hash_options_fail_closed(self) -> None:
        digest = "a" * 64
        bad_cases = (
            ("ruff==0.17.2\n    --hash=sha256:abc\n", "invalid SHA-256 hash option"),
            ("--hash=sha256:" + digest + "\nruff==0.17.2\n", "hash without a package"),
            (
                "ruff==0.17.2\n    --index-url=https://invalid.example\n",
                "invalid SHA-256 hash option",
            ),
            (
                "ruff==0.17.2 " + chr(92) + "\n    --hash=sha256:" + digest + "\nmypy==2.4.0\n",
                "mypy lacks a SHA-256 hash",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "requirements-dev.lock"
            for body, error in bad_cases:
                with self.subTest(expected=error):
                    lock.write_text(body, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, error):
                        read_hashed_versions(lock)

    def test_hash_options_must_have_explicit_line_continuations(self) -> None:
        digest_a, digest_b = "a" * 64, "b" * 64
        slash = chr(92)
        invalid = (
            # A valid hash line without the preceding slash is ignored by pip.
            (f"ruff==0.17.2\n    --hash=sha256:{digest_a}\n", "hash has no line continuation"),
            (
                f"ruff==0.17.2 {slash}\n    --hash=sha256:{digest_a}\n"
                f"    --hash=sha256:{digest_b}\n",
                "hash has no line continuation",
            ),
            (
                f"ruff==0.17.2 {slash}\nmypy==2.4.0 {slash}\n"
                f"    --hash=sha256:{digest_a}\n",
                "expected continued hash option",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "requirements-dev.lock"
            for body, error in invalid:
                with self.subTest(error=error):
                    lock.write_text(body, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, error):
                        read_hashed_versions(lock)

            # Both hashes are genuinely associated with the same package.
            lock.write_text(
                f"ruff==0.17.2 {slash}\n"
                f"    --hash=sha256:{digest_a} {slash}\n"
                f"    --hash=sha256:{digest_b}\n",
                encoding="utf-8",
            )
            self.assertEqual(read_hashed_versions(lock), {"ruff": "0.17.2"})

    def test_valid_marker_bearing_transitive_dependency(self) -> None:
        digest = "b" * 64
        slash = chr(92)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements-dev.txt"
            lock = root / "requirements-dev.lock"
            requirements.write_text("ruff==0.17.2\n", encoding="utf-8")
            lock.write_text(
                f"typing-extensions==4.15.0 ; python_version < '3.13' {slash}\n"
                f"    --hash=sha256:{digest}\n"
                "    # via mypy\n"
                f"ruff==0.17.2 {slash}\n    --hash=sha256:{digest}\n",
                encoding="utf-8",
            )
            self.assertEqual(check_versions(requirements, lock), [])


if __name__ == "__main__":
    unittest.main()
