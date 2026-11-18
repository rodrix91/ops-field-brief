"""Offline contracts for the future tag-driven publishing workflow.

Historical tags execute the workflow stored in their tagged commit. This
suite governs only new releases from the current repository revision.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")


class ReleaseSafetyTests(unittest.TestCase):
    def test_release_is_tag_only_with_scoped_permissions(self) -> None:
        self.assertRegex(RELEASE, r'(?m)^  push:\n    tags:\n      - "v\*\.\*\.\*"')
        self.assertRegex(RELEASE, r"(?m)^permissions:\n  contents: read")
        self.assertRegex(RELEASE, r"(?m)^    permissions:\n      contents: write")
        self.assertNotIn("pull_request:", RELEASE)
        self.assertNotIn("workflow_dispatch:", RELEASE)

    def test_approved_actions_are_immutable_and_do_not_retain_checkout_credentials(
        self,
    ) -> None:
        self.assertNotRegex(RELEASE, r"(?m)^\s+uses: [^\n]+@v\d")
        self.assertRegex(RELEASE, r"uses: actions/checkout@[0-9a-f]{40}")
        self.assertRegex(RELEASE, r"uses: actions/setup-python@[0-9a-f]{40}")
        self.assertRegex(RELEASE, r"uses: actions/attest@[0-9a-f]{40}")
        self.assertIn("persist-credentials: false", RELEASE)

    def test_build_frontend_uses_verified_hashed_lock(self) -> None:
        self.assertIn("python scripts/check_dev_lock.py", RELEASE)
        self.assertIn(
            "python -m pip install --disable-pip-version-check "
            "--require-hashes -r requirements-dev.lock",
            RELEASE,
        )
        self.assertNotRegex(RELEASE, r"pip install[^\n]*build(?:==|\s|$)")

    def test_artifacts_are_verified_before_publication(self) -> None:
        stages = [
            "Verify tag matches package version",
            "Install fully hashed build and test tooling",
            "Build wheel and source distribution",
            "Test the wheel in a clean environment",
            "Test the source distribution",
            "Write SHA-256 checksums",
            "Attest release artifacts",
            "Publish a new GitHub release",
        ]
        positions = [RELEASE.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("sha256sum -c SHA256SUMS", RELEASE)
        self.assertIn("--verify-tag", RELEASE)

    def test_preexisting_published_releases_are_never_overwritten(self) -> None:
        self.assertIn('if gh release view "$TAG" > /dev/null 2>&1; then', RELEASE)
        self.assertIn("refusing to overwrite published files", RELEASE)
        self.assertNotIn("gh release upload", RELEASE)
        self.assertNotIn("--clobber", RELEASE)
        self.assertEqual(RELEASE.count("gh release create "), 1)


if __name__ == "__main__":
    unittest.main()
