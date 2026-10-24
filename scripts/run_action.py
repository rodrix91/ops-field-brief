"""GitHub Action runner for ops-field-brief."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _append_output(name: str, value: str) -> None:
    target = os.getenv("GITHUB_OUTPUT")
    if not target:
        return
    with Path(target).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _write_summary(text: str, *, is_json: bool) -> None:
    if os.getenv("OPS_FIELD_BRIEF_INPUT_SUMMARY", "true").lower() != "true":
        return
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if not target or not text:
        return
    with Path(target).open("a", encoding="utf-8") as handle:
        handle.write("## ops-field-brief\n\n")
        if is_json:
            handle.write("```json\n")
            handle.write(text.rstrip())
            handle.write("\n```\n")
        else:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")


def main() -> int:
    csv_path = os.getenv("OPS_FIELD_BRIEF_INPUT_PATH", "")
    if not csv_path:
        print("Action input path is required.", file=sys.stderr)
        _append_output("exit-code", "2")
        _append_output("passed", "false")
        return 2

    raw_args = os.getenv("OPS_FIELD_BRIEF_INPUT_ARGS", "")
    try:
        extra_args = shlex.split(raw_args)
    except ValueError as exc:
        print(f"Invalid action args: {exc}", file=sys.stderr)
        _append_output("exit-code", "2")
        _append_output("passed", "false")
        return 2

    action_path = Path(os.environ["OPS_FIELD_BRIEF_ACTION_PATH"]).resolve()
    env = dict(os.environ)
    src = str(action_path / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not existing else os.pathsep.join((src, existing))

    command = [sys.executable, "-m", "ops_field_brief", csv_path, *extra_args]
    completed = subprocess.run(
        command,
        cwd=os.getenv("GITHUB_WORKSPACE") or None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)

    _append_output("exit-code", str(completed.returncode))
    _append_output("passed", "true" if completed.returncode == 0 else "false")
    _write_summary(completed.stdout, is_json="--json" in extra_args)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
