"""GitHub Action runner for ops-field-brief."""

from __future__ import annotations

import json
import os
import re
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
            # CSV labels may contain Markdown fence delimiters. Always choose
            # a fence longer than any backtick run in the JSON payload so a
            # value cannot prematurely close the GitHub job-summary block.
            longest = max((len(m.group()) for m in re.finditer(r"`+", text)), default=0)
            fence = "`" * max(3, longest + 1)
            handle.write(f"{fence}json\n")
            handle.write(text.rstrip())
            handle.write(f"\n{fence}\n")
        else:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")


def _reject_input_controls(raw: str, label: str) -> None:
    """Prevent untrusted Action inputs from altering workflow logs."""
    if any(character in raw for character in ("\r", "\n", "\x00")):
        raise ValueError(f"Action {label} must not contain line breaks or NUL characters.")
    # C0, DEL and C1 controls can manipulate terminal/log rendering.
    # A tab is only meaningful as a shlex delimiter in args, never in paths.
    if any(
        (ord(character) < 32 and (character != "\t" or label != "args"))
        or 127 <= ord(character) <= 159
        for character in raw
    ):
        raise ValueError(f"Action {label} must not contain terminal control characters.")


def _validated_csv_path(raw: str, workspace: str | None) -> Path:
    """Fail closed on paths that could read outside the caller's workspace."""
    if not workspace:
        raise ValueError("GITHUB_WORKSPACE is required for the Action.")
    _reject_input_controls(raw, "path")
    if raw == "-":
        raise ValueError("Action input path must name a CSV file inside GITHUB_WORKSPACE.")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError("Action input path must be relative to GITHUB_WORKSPACE.")
    root = Path(workspace).resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Action input path must stay within GITHUB_WORKSPACE.") from exc
    return resolved


def _reject_nonexecuting_flags(args: list[str]) -> None:
    """The reusable Action must not report success without examining a CSV."""
    for token in args:
        if token == "-h" or (
            token.startswith("--")
            and len(token) > 2
            and any(option.startswith(token) for option in ("--help", "--version"))
        ):
            raise ValueError(
                "Action args must not contain --help or --version; "
                "run these informational options using the standalone CLI."
            )


def _requests_json(args: list[str]) -> bool:
    """Detect accepted argparse prefixes of --json for safe job-summary fencing."""
    return any(option in {"--j", "--js", "--jso", "--json"} for option in args)


def _has_valid_report(text: str, *, is_json: bool) -> bool:
    """Never mark a quality check successful without an actual report."""
    if not text.strip():
        return False
    if is_json:
        try:
            return isinstance(json.loads(text), dict)
        except ValueError:
            return False
    return True


def main() -> int:
    csv_path = os.getenv("OPS_FIELD_BRIEF_INPUT_PATH", "")
    if not csv_path:
        print("Action input path is required.", file=sys.stderr)
        _append_output("exit-code", "2")
        _append_output("passed", "false")
        return 2

    raw_args = os.getenv("OPS_FIELD_BRIEF_INPUT_ARGS", "")
    try:
        _reject_input_controls(raw_args, "args")
        extra_args = shlex.split(raw_args)
        _reject_nonexecuting_flags(extra_args)
    except ValueError as exc:
        print(f"Invalid action args: {exc}", file=sys.stderr)
        _append_output("exit-code", "2")
        _append_output("passed", "false")
        return 2

    try:
        csv_path = str(_validated_csv_path(csv_path, os.getenv("GITHUB_WORKSPACE")))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
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

    exit_code = completed.returncode
    is_json = _requests_json(extra_args)
    invalid_report = exit_code in (0, 1) and not _has_valid_report(
        completed.stdout, is_json=is_json
    )
    if invalid_report:
        # An exit code alone is not evidence that any CSV was evaluated.
        # Reject empty stdout and malformed/non-object JSON, but preserve
        # the original nonzero CLI errors without replacing their meaning.
        print("Action analysis produced no valid report.", file=sys.stderr)
        exit_code = 3

    _append_output("exit-code", str(exit_code))
    _append_output("passed", "true" if exit_code == 0 else "false")
    if not invalid_report:
        _write_summary(completed.stdout, is_json=is_json)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
