"""Smoke-test the built wheel and installed command on the host platform.

Run from the checkout with: python scripts/check_wheel_smoke.py
The package is installed in a fresh virtual environment, then exercised from
outside the source directory with PYTHONPATH removed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    example = root / "examples" / "shipments.csv"
    with tempfile.TemporaryDirectory(prefix="ops-field-brief-wheel-") as temporary:
        work = Path(temporary)
        wheel_dir = work / "dist"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--disable-pip-version-check",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
                str(root),
            ],
            check=True,
        )
        wheels = list(wheel_dir.glob("ops_field_brief-*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"expected exactly one built wheel; got {wheels}")

        environment = work / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        binary_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary_dir / ("python.exe" if os.name == "nt" else "python")
        executable = binary_dir / ("ops-field-brief.exe" if os.name == "nt" else "ops-field-brief")
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                str(wheels[0]),
            ],
            check=True,
        )

        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        installed_version = subprocess.run(
            [
                str(python),
                "-c",
                (
                    "from importlib.metadata import version; "
                    "import ops_field_brief; "
                    "assert version('ops-field-brief') == ops_field_brief.__version__; "
                    "print(ops_field_brief.__version__)"
                ),
            ],
            cwd=work,
            env=clean_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        version_output = subprocess.run(
            [str(executable), "--version"],
            cwd=work,
            env=clean_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if version_output != f"ops-field-brief {installed_version}":
            raise AssertionError(f"installed executable reported {version_output!r}")

        completed = subprocess.run(
            [
                str(executable),
                str(example),
                "--required",
                "shipment",
                "--key",
                "shipment",
                "--max-duplicates",
                "1",
                "--json",
            ],
            cwd=work,
            env=clean_env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        if payload["rows"] < 1 or payload["key"] != "shipment" or payload["failed_fields"]:
            raise AssertionError("installed command returned an invalid operational report")

    print(f"Installed wheel and console entry point: OK ({installed_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
