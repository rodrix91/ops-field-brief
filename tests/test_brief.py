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

    def test_semicolon_delimiter(self):
        path = ROOT / "examples" / "shipments-semicolon.csv"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "envio,comprador,eta",
                "--delimiter",
                "semicolon",
                "--key",
                "envio",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("Rows: 2", completed.stdout)
        self.assertIn("envio", completed.stdout)

    def test_cp1252_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "excel.csv"
            path.write_bytes("comprador,eta\nPeñaflor,2026-10-01\n".encode("cp1252"))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "comprador,eta",
                    "--encoding",
                    "cp1252",
                    "--group",
                    "comprador",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Peñaflor", completed.stdout)

    def test_unknown_encoding_exits_2(self):
        path = ROOT / "examples" / "shipments.csv"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment",
                "--encoding",
                "not-a-codec",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("not-a-codec", completed.stderr)

    def test_max_missing_allows_a_share(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            allowed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--max-missing",
                    "0.5",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            strict = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(strict.returncode, 1, strict.stderr)

    def test_max_missing_out_of_range_exits_2(self):
        path = ROOT / "examples" / "shipments.csv"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment",
                "--max-missing",
                "1.5",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("max_missing", completed.stderr)

    def test_empty_required_exits_2(self):
        path = ROOT / "examples" / "shipments.csv"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                " , ",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("at least one required field", completed.stderr)

    def test_pipe_delimiter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipe.csv"
            path.write_text("shipment|buyer\nS1|Andes\nS2|Paz\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--delimiter",
                    "pipe",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 2", completed.stdout)

    def test_tab_delimiter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tab.csv"
            path.write_text("shipment\tbuyer\nS1\tAndes\nS2\tPaz\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--delimiter",
                    "tab",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 2", completed.stdout)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ok.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS2,Paz\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["rows"], 2)
        self.assertEqual(payload["failed_fields"], [])

    def test_unknown_key_exits_2(self):
        path = ROOT / "examples" / "shipments.csv"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                str(path),
                "--required",
                "shipment",
                "--key",
                "invoice",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invoice", completed.stderr)

    def test_blank_group_is_named(self):
        rows = [
            {"shipment": "S1", "buyer": "Andes"},
            {"shipment": "S2", "buyer": " "},
        ]
        brief = build_brief(rows, ["shipment", "buyer"], group="buyer")
        self.assertEqual(brief.top, (("Andes", 1), ("(blank)", 1)))


if __name__ == "__main__":
    unittest.main()
