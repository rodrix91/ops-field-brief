"""Regression coverage for truncated hashed development locks."""

from pathlib import Path

import pytest

from scripts.check_dev_lock import read_hashed_versions


@pytest.mark.parametrize("trailing", ["", "\n", "    # generated lock metadata\n"])
def test_dangling_hash_continuation_fails(
    tmp_path: Path, trailing: str
) -> None:
    lock = tmp_path / "requirements-dev.lock"
    slash = chr(92)
    digest = "a" * 64
    lock.write_text(
        f"ruff==0.17.3 {slash}\n"
        f"    --hash=sha256:{digest} {slash}\n"
        + trailing,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="dangling line continuation"):
        read_hashed_versions(lock)


def test_complete_hashed_lock_passes(tmp_path: Path) -> None:
    lock = tmp_path / "requirements-dev.lock"
    slash = chr(92)
    digest = "a" * 64
    lock.write_text(
        f"ruff==0.17.3 {slash}\n"
        f"    --hash=sha256:{digest}\n",
        encoding="utf-8",
    )
    assert read_hashed_versions(lock) == {"ruff": "0.17.3"}
