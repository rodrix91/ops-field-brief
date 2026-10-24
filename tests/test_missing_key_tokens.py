"""Missing-value tokens must not be mistaken for valid business keys."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ops_field_brief.brief import build_brief

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("token", ["NA", "N/A", "null", "none", "s/d", "N.D.", "-"])
def test_single_business_key_missing_tokens_are_incomplete(token: str) -> None:
    rows = [{"order": token}, {"order": token}, {"order": "O-1"}]
    brief = build_brief(
        rows, ["order"], key="order", max_missing=0, max_incomplete_keys=1,
        max_duplicates=0,
    )
    assert brief.incomplete_key_rows == 2
    assert brief.duplicate_keys == 0
    assert brief.failed_incomplete_keys
    assert not brief.failed_duplicates
    assert brief.failed_fields == ("order",)
    payload = brief.to_dict()
    assert payload["incomplete_key_rows"] == 2
    assert payload["duplicate_keys"] == 0


def test_composite_key_uses_same_missing_rules_as_required_fields() -> None:
    rows = [
        {"order": "O-1", "line": "1"},
        {"order": "O-1", "line": "1"},
        {"order": "O-2", "line": " NA "},
        {"order": "O-2", "line": "n/a"},
        {"order": "O-3", "line": "2"},
    ]
    brief = build_brief(
        rows, ["line"], key_fields=["order", "line"],
        max_incomplete_keys=0, max_duplicates=0,
    )
    assert brief.duplicate_keys == 1
    assert brief.incomplete_key_rows == 2
    assert brief.failed_incomplete_keys
    assert brief.failed_duplicates
    assert brief.failed_fields == ("line",)


def test_missing_token_cli_quality_gate_exits_one_and_preserves_json(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("order\nN/A\nNA\nO-1\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [
        sys.executable, "-m", "ops_field_brief", str(source),
        "--required", "order", "--key", "order",
        "--max-incomplete-keys", "0", "--json",
    ]
    run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert run.returncode == 1, run.stderr
    payload = json.loads(run.stdout)
    assert payload["incomplete_key_rows"] == 2
    assert payload["failed_incomplete_keys"] is True
    assert payload["duplicate_keys"] == 0
    assert payload["fields"][0]["missing"] == 2
