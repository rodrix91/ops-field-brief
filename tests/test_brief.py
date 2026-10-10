import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief.brief import build_brief, render

ROOT = Path(__file__).resolve().parents[1]


class BriefTests(unittest.TestCase):
    def test_fill_duplicates_and_groups(self):
        rows = [
            {"shipment": "S1", "buyer": "Andes", "eta": "2026-10-01"},
            {"shipment": "S1", "buyer": "Andes", "eta": ""},
            {"shipment": "S2", "buyer": "N/A", "eta": "s/d"},
        ]
        brief = build_brief(rows, ["shipment", "buyer", "eta"], key="shipment", group="buyer")
        self.assertEqual(brief.rows, 3)
        self.assertEqual(brief.duplicate_keys, 1)
        eta = brief.fields[2]
        self.assertEqual(eta.filled, 1)
        self.assertEqual(eta.missing, 2)
        self.assertEqual(brief.failed_fields, ("buyer", "eta"))
        self.assertEqual(brief.top[0], ("Andes", 2))
        text = render(brief, as_json=False)
        self.assertIn("Extra rows from a repeated key: 1", text)
        payload = json.loads(render(brief, as_json=True))
        self.assertEqual(payload["duplicate_keys"], 1)

    def test_unknown_column_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            build_brief([{"shipment": "S1"}], ["invoice"])
        self.assertIn("invoice", str(caught.exception))

    def test_cli_passes_when_required_fields_are_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ok.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,Paz\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [sys.executable, "-m", "ops_field_brief", str(path), "--required", "shipment,buyer"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 2", completed.stdout)

    def test_cli_fails_fill_check_and_rejects_a_missing_file(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        example = ROOT / "examples" / "shipments.csv"
        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(example),
                "--required",
                "shipment,buyer,eta",
                "--key",
                "shipment",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn("Failed fill check", failed.stdout)
        missing = subprocess.run(
            [sys.executable, "-m", "ops_field_brief", "missing.csv", "--required", "shipment"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
