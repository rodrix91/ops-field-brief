import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_field_brief import __version__
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

    def test_unknown_group_exits_2(self):
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
                "--group",
                "region",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("region", completed.stderr)

    def test_blank_keys_are_not_duplicates(self):
        rows = [
            {"shipment": " ", "buyer": "Andes"},
            {"shipment": "", "buyer": "Paz"},
            {"shipment": "S1", "buyer": "Andes"},
        ]
        brief = build_brief(rows, ["shipment", "buyer"], key="shipment")
        self.assertEqual(brief.duplicate_keys, 0)

    def test_header_only_exits_0(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "header.csv"
            path.write_text("shipment,buyer\n", encoding="utf-8")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 0", completed.stdout)

    def test_empty_file_reports_zero_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text("", encoding="utf-8")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 0", completed.stdout)

    def test_utf8_bom_is_stripped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.csv"
            path.write_bytes(b"\xef\xbb\xbfshipment,buyer\nS1,Andes\n")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)

    def test_missing_tokens_are_counted(self):
        rows = [
            {"shipment": "S1", "buyer": "N/A"},
            {"shipment": "S2", "buyer": "none"},
            {"shipment": "S3", "buyer": "-"},
            {"shipment": "S4", "buyer": "Andes"},
        ]
        brief = build_brief(rows, ["shipment", "buyer"])
        buyer = brief.fields[1]
        self.assertEqual(buyer.missing, 3)
        self.assertEqual(buyer.filled, 1)

    def test_spanish_nd_is_missing(self):
        rows = [{"shipment": "S1", "buyer": "N/D"}, {"shipment": "S2", "buyer": "Andes"}]
        brief = build_brief(rows, ["shipment", "buyer"])
        buyer = brief.fields[1]
        self.assertEqual(buyer.missing, 1)
        self.assertEqual(buyer.filled, 1)

    def test_dotted_spanish_tokens_are_missing(self):
        rows = [
            {"shipment": "S1", "buyer": "s.d."},
            {"shipment": "S2", "buyer": "N.D."},
            {"shipment": "S3", "buyer": "Andes"},
        ]
        brief = build_brief(rows, ["shipment", "buyer"])
        buyer = brief.fields[1]
        self.assertEqual(buyer.missing, 2)
        self.assertEqual(buyer.filled, 1)

    def test_top_groups_are_limited_to_five(self):
        rows = [{"shipment": "S%d" % i, "buyer": "B%d" % i} for i in range(7)]
        brief = build_brief(rows, ["shipment", "buyer"], group="buyer")
        self.assertEqual(len(brief.top), 5)
        self.assertEqual(brief.rows, 7)

    def test_stdin_reads_a_pipe(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--required",
                "shipment,buyer",
            ],
            cwd=ROOT,
            env=env,
            input="shipment,buyer\nS1,Andes\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)

    def test_top_flag_limits_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.write_text(
                "shipment,buyer\nS1,A\nS2,B\nS3,C\nS4,D\n",
                encoding="utf-8",
            )
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
                    "--group",
                    "buyer",
                    "--top",
                    "2",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("A: 1", completed.stdout)
        self.assertIn("B: 1", completed.stdout)
        self.assertNotIn("C: 1", completed.stdout)

    def test_three_identical_keys_count_as_two_extra_rows(self):
        rows = [
            {"shipment": "S1", "buyer": "Andes"},
            {"shipment": "S1", "buyer": "Andes"},
            {"shipment": "S1", "buyer": "Andes"},
        ]
        brief = build_brief(rows, ["shipment", "buyer"], key="shipment")
        self.assertEqual(brief.duplicate_keys, 2)
        self.assertEqual(brief.rows, 3)

    def test_top_zero_reports_no_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.write_text("shipment,buyer\nS1,A\nS2,B\n", encoding="utf-8")
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
                    "--group",
                    "buyer",
                    "--top",
                    "0",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Top groups", completed.stdout)
        self.assertIn("Rows: 2", completed.stdout)

    def test_two_repeated_keys_sum_their_extra_rows(self):
        rows = [
            {"shipment": "S1", "buyer": "Andes"},
            {"shipment": "S1", "buyer": "Andes"},
            {"shipment": "S2", "buyer": "Paz"},
            {"shipment": "S2", "buyer": "Paz"},
        ]
        brief = build_brief(rows, ["shipment", "buyer"], key="shipment")
        self.assertEqual(brief.duplicate_keys, 2)
        self.assertEqual(brief.rows, 4)

    def test_negative_top_exits_2(self):
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
                "--top",
                "-1",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("top", completed.stderr)

    def test_quoted_field_with_a_comma_stays_one_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quoted.csv"
            path.write_text(
                'shipment,buyer\nS1,"Andes, La Paz"\n',
                encoding="utf-8",
            )
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
                    "--group",
                    "buyer",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Andes, La Paz", completed.stdout)
        self.assertIn("Rows: 1", completed.stdout)

    def test_escaped_quote_stays_in_the_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quoted.csv"
            path.write_text(
                'shipment,buyer\nS1,"Andes ""Norte"""\n',
                encoding="utf-8",
            )
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
                    "--group",
                    "buyer",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('Andes "Norte"', completed.stdout)
        self.assertIn("Rows: 1", completed.stdout)

    def test_multiline_quoted_field_stays_one_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quoted.csv"
            path.write_text(
                'shipment,buyer\nS1,"Andes\nLa Paz"\n',
                encoding="utf-8",
            )
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
                    "--group",
                    "buyer",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)
        self.assertIn("Andes", completed.stdout)
        self.assertIn("La Paz", completed.stdout)

    def test_trailing_comma_does_not_break_the_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trailing.csv"
            path.write_text("shipment,buyer,\nS1,Andes,\n", encoding="utf-8")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)

    def test_whitespace_only_field_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spaces.csv"
            path.write_text("shipment,buyer\nS1,   \n", encoding="utf-8")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("Failed fill check", completed.stdout)
        self.assertIn("buyer", completed.stdout)

    def test_tab_only_field_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tab.csv"
            path.write_text("shipment,buyer\nS1,\t\n", encoding="utf-8")
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
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("Failed fill check", completed.stdout)
        self.assertIn("buyer", completed.stdout)

    def test_invalid_delimiter_exits_2(self):
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
                "--delimiter",
                "slash",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid choice", completed.stderr)

    def test_duplicate_header_uses_the_last_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dup.csv"
            path.write_text("shipment,buyer,shipment\nS1,Andes,S1b\n", encoding="utf-8")
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
                    "--key",
                    "shipment",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)

    def test_help_exits_0(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-m", "ops_field_brief", "--help"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("--required", completed.stdout)
        self.assertIn("--delimiter", completed.stdout)

    def test_utf8_bom_on_stdin_is_stripped(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--required",
                "shipment,buyer",
            ],
            cwd=ROOT,
            env=env,
            input="\ufeffshipment,buyer\nS1,Andes\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 1", completed.stdout)

    def test_cp1252_stdin_uses_requested_encoding(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--required",
                "shipment,buyer",
                "--encoding",
                "cp1252",
            ],
            cwd=ROOT,
            env=env,
            input=b"shipment,buyer\nS1,Caf\xe9\n",
            capture_output=True,
            check=False,
        )
        stdout = completed.stdout.decode("ascii")
        stderr = completed.stderr.decode("ascii", errors="replace")
        self.assertEqual(completed.returncode, 0, stderr)
        self.assertIn("Rows: 1", stdout)

    def test_max_duplicates_allows_under_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dups.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS1,Andes\nS2,Paz\n", encoding="utf-8")
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
                    "--key",
                    "shipment",
                    "--max-duplicates",
                    "1",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Max allowed duplicate extra rows: 1", completed.stdout)

    def test_max_duplicates_fails_when_exceeded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dups.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS1,Andes\nS1,Andes\n", encoding="utf-8")
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
                    "--key",
                    "shipment",
                    "--max-duplicates",
                    "0",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("Failed duplicate check", completed.stdout)
        self.assertIn("exceed the limit (0)", completed.stdout)

    def test_negative_max_duplicates_exits_2(self):
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
                "--max-duplicates",
                "-1",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("max_duplicates", completed.stderr)

    def test_max_duplicates_in_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dups.csv"
            path.write_text("shipment,buyer\nS1,Andes\nS1,Andes\n", encoding="utf-8")
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
                    "--key",
                    "shipment",
                    "--max-duplicates",
                    "0",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["max_duplicates"], 0)
        self.assertTrue(payload["failed_duplicates"])


    def test_auto_delimiter_detects_semicolon_file(self):
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
                "auto",
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

    def test_auto_delimiter_detects_pipe_on_stdin(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ops_field_brief",
                "-",
                "--required",
                "shipment,buyer",
                "--delimiter",
                "auto",
            ],
            cwd=ROOT,
            env=env,
            input="shipment|buyer\nS1|Andes\nS2|Paz\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Rows: 2", completed.stdout)

    def test_auto_delimiter_reports_ambiguous_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "single-column.csv"
            path.write_text("shipment\nS1\nS2\n", encoding="utf-8")
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
                    "--delimiter",
                    "auto",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("could not detect delimiter", completed.stderr)


    def test_version_flag(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-m", "ops_field_brief", "--version"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, f"ops-field-brief {__version__}\n")


    def test_composite_key_counts_only_repeated_complete_pairs(self):
        rows = [
            {"order": "O1", "line": "1"},
            {"order": "O1", "line": "2"},
            {"order": "O1", "line": "1"},
            {"order": "", "line": "1"},
            {"order": "", "line": "1"},
        ]
        brief = build_brief(
            rows,
            ["order", "line"],
            key_fields=["order", "line"],
            max_duplicates=0,
        )
        self.assertEqual(brief.key, "order,line")
        self.assertEqual(brief.key_fields, ("order", "line"))
        self.assertEqual(brief.duplicate_keys, 1)
        self.assertTrue(brief.failed_duplicates)
        self.assertEqual(brief.to_dict()["key_fields"], ["order", "line"])

    def test_cli_composite_key_is_reported_in_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            path.write_text(
                "order,line,buyer\nO1,1,A\nO1,2,A\nO1,1,B\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "order,line",
                    "--key",
                    "order,line",
                    "--max-duplicates",
                    "0",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["key"], "order,line")
        self.assertEqual(payload["key_fields"], ["order", "line"])
        self.assertEqual(payload["duplicate_keys"], 1)

    def test_empty_composite_key_argument_exits_2(self):
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
                " , ",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("at least one key field", completed.stderr)


    def test_header_only_file_keeps_composite_key_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "header-only.csv"
            path.write_text("order,line,buyer\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "order",
                    "--key",
                    "order,line",
                    "--group",
                    "buyer",
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
        self.assertEqual(payload["rows"], 0)
        self.assertEqual(payload["key_fields"], ["order", "line"])


    def test_min_rows_gate_passes_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.csv"
            path.write_text("shipment,buyer\nS1,A\nS2,B\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            passed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--min-rows",
                    "2",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            failed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ops_field_brief",
                    str(path),
                    "--required",
                    "shipment,buyer",
                    "--min-rows",
                    "3",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn("Minimum rows: 2", passed.stdout)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn("Failed row-count check", failed.stdout)
        self.assertIn("Rows (2) are below the minimum (3)", failed.stdout)

    def test_min_rows_is_explicit_in_json_only_when_requested(self):
        rows = [{"shipment": "S1"}]
        plain = build_brief(rows, ["shipment"]).to_dict()
        gated = build_brief(rows, ["shipment"], min_rows=2).to_dict()
        self.assertNotIn("min_rows", plain)
        self.assertNotIn("failed_rows", plain)
        self.assertEqual(gated["min_rows"], 2)
        self.assertTrue(gated["failed_rows"])

    def test_negative_min_rows_exits_2(self):
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
                "--min-rows",
                "-1",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("min_rows must be 0 or greater", completed.stderr)


if __name__ == "__main__":
    unittest.main()
