"""GitHub Action runner for ops-field-brief."""

from __future__ import annotations

import json
import math
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


def _has_valid_markdown_report(text: str, exit_code: int) -> bool:
    """Accept a measured Markdown brief, not an arbitrary successful message."""
    lines = text.splitlines()
    if not text.endswith("\n") or len(lines) < 11 or lines[:2] != ["# Operational field brief", ""]:
        return False
    rows_match = re.fullmatch(r"- Rows: (0|[1-9][0-9]*)", lines[2])
    if rows_match is None:
        return False
    rows = int(rows_match.group(1))
    try:
        section = lines.index("## Required fields")
    except ValueError:
        return False
    if lines[section + 1 : section + 4] != [
        "",
        "| Field | Filled | Missing | Missing rate |",
        "|---|---:|---:|---:|",
    ]:
        return False
    measured = 0
    for line in lines[section + 4 :]:
        if not line:
            break
        field = re.fullmatch(r"\| .+ \| (\d+) \| (\d+) \| (\d+(?:\.\d+)?)% \|", line)
        if field is None or int(field.group(1)) + int(field.group(2)) != rows:
            return False
        measured += 1
    if not measured:
        return False
    has_failure_section = any(line.startswith("## Failed ") for line in lines)
    return has_failure_section == (exit_code == 1)


def _has_valid_report(text: str, *, is_json: bool, exit_code: int = 0) -> bool:
    """Reject missing, malformed and self-contradictory action reports."""
    if not text.strip():
        return False
    if is_json:
        try:
            report = json.loads(text)
        except ValueError:
            return False
        if not isinstance(report, dict):
            return False
        rows = report.get("rows")
        fields = report.get("fields")
        failed_fields = report.get("failed_fields")
        if (
            type(rows) is not int
            or rows < 0
            or not isinstance(fields, list)
            or not fields
            or not isinstance(failed_fields, list)
            or not all(isinstance(name, str) for name in failed_fields)
        ):
            return False
        if not all(
            isinstance(field, dict)
            and isinstance(field.get("name"), str)
            and bool(field["name"].strip())
            and type(field.get("filled")) is int
            and type(field.get("missing")) is int
            and field["filled"] >= 0
            and field["missing"] >= 0
            and field["filled"] + field["missing"] == rows
            and type(field.get("missing_rate")) in (int, float)
            and math.isfinite(field["missing_rate"])
            and 0 <= field["missing_rate"] <= 1
            and field["missing_rate"] == (round(field["missing"] / rows, 4) if rows else 0)
            for field in fields
        ):
            return False
        field_names = [field["name"] for field in fields]
        if (
            len(field_names) != len(set(field_names))
            or len(failed_fields) != len(set(failed_fields))
            or not set(failed_fields).issubset(field_names)
        ):
            return False
        failure_flags = [
            value
            for name, value in report.items()
            if name.startswith("failed_") and name != "failed_fields"
        ]
        if not failure_flags or not all(isinstance(flag, bool) for flag in failure_flags):
            return False
        has_failures = bool(failed_fields) or any(failure_flags)
        return has_failures == (exit_code == 1)
    return _has_valid_markdown_report(text, exit_code)


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
        completed.stdout, is_json=is_json, exit_code=exit_code
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
