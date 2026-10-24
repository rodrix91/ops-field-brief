#!/usr/bin/env python3
"""
Autonomous Engineering Agent for ops-field-brief.
Runs daily automated audits, verifies test suites, and interfaces with the Gemini API
for continuous optimization and code quality assessment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_tests() -> tuple[bool, str]:
    """Runs the full unit test suite using standard library unittest."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + "\n" + result.stderr
    return (result.returncode == 0, output.strip())


def audit_repository() -> dict:
    """Audits repository files, README completeness, and source files."""
    src_dir = ROOT / "src" / "ops_field_brief"
    tests_dir = ROOT / "tests"
    readme_path = ROOT / "README.md"
    changelog_path = ROOT / "CHANGELOG.md"

    py_sources = list(src_dir.glob("*.py"))
    test_files = list(tests_dir.glob("*.py"))

    has_readme = readme_path.is_file()
    has_changelog = changelog_path.is_file()

    readme_len = len(readme_path.read_text(encoding="utf-8")) if has_readme else 0
    changelog_len = len(changelog_path.read_text(encoding="utf-8")) if has_changelog else 0

    return {
        "repository": "ops-field-brief",
        "source_files": [f.name for f in py_sources],
        "test_files": [f.name for f in test_files],
        "readme_present": has_readme,
        "readme_characters": readme_len,
        "changelog_present": has_changelog,
        "changelog_characters": changelog_len,
    }


def query_gemini_api(prompt: str, api_key: str) -> str | None:
    """Queries Google Gemini API using only the Python standard library."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as err:
        sys.stderr.write(f"Gemini API request note: {err}\n")
        return None
    return None


def main() -> int:
    print("=== Starting Autonomous Daily Cycle for ops-field-brief ===")

    # 1. Run local test suite
    print("1. Running unit test suite...")
    passed, test_log = run_tests()
    if not passed:
        sys.stderr.write(f"Test suite failed:\n{test_log}\n")
        return 1
    print(f"Test suite PASSED successfully:\n{test_log.splitlines()[-1]}")

    # 2. Audit codebase
    print("2. Auditing repository files...")
    audit = audit_repository()
    print(
        f"Repository status: {len(audit['source_files'])} sources, "
        f"{len(audit['test_files'])} test modules."
    )

    # 3. Query Gemini API if configured
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print("3. Querying Gemini API for architectural assessment...")
        prompt = (
            "Analyze the following repository status for ops-field-brief:\n"
            f"{json.dumps(audit, indent=2)}\n"
            "Provide a concise 3-bullet assessment of code quality and operational test readiness."
        )
        feedback = query_gemini_api(prompt, api_key)
        if feedback:
            print(f"Gemini Assessment:\n{feedback.strip()}\n")
        else:
            print("Gemini API call completed without text candidate.")
    else:
        print(
            "3. Note: GEMINI_API_KEY not found in environment; "
            "running standard rule-based verification."
        )

    print("=== Autonomous Daily Cycle Completed Successfully ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
