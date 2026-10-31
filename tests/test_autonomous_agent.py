import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import autonomous_agent as agent


class AutonomousAgentTests(unittest.TestCase):
    @staticmethod
    def healthy_audit():
        return {
            "source_files": ["brief.py"],
            "test_files": ["test_brief.py"],
            "readme_present": True,
            "readme_characters": 200,
            "changelog_present": True,
            "changelog_characters": 40,
        }

    def test_run_tests_rejects_empty_or_missing_unittest_summaries(self):
        outcomes = (
            ("Ran 0 tests in 0.000s\n\nOK\n", "", "no tests"),
            ("OK\n", "", "missing summary"),
            ("OK\n", "Ran 99 tests in 0.001s", "fake stdout summary"),
        )
        for stderr, stdout, label in outcomes:
            with self.subTest(label=label):
                completed = subprocess.CompletedProcess(
                    args=["python", "-m", "unittest"],
                    returncode=0,
                    stdout=stdout,
                    stderr=stderr,
                )
                with patch.object(agent.subprocess, "run", return_value=completed):
                    passed, log = agent.run_tests()
                self.assertFalse(passed)
                self.assertIn("No unittest test cases were executed.", log)

    def test_run_tests_accepts_real_positive_summary_and_checks_exit_code(self):
        summary = "Ran 1 test in 0.001s\n\nOK\n"
        for code, expected in ((0, True), (1, False)):
            with self.subTest(code=code):
                completed = subprocess.CompletedProcess(
                    args=["python", "-m", "unittest"],
                    returncode=code,
                    stdout="Example output",
                    stderr=summary,
                )
                with patch.object(agent.subprocess, "run", return_value=completed) as execute:
                    passed, log = agent.run_tests()
                self.assertEqual(passed, expected)
                self.assertIn("Ran 1 test", log)
                self.assertEqual(execute.call_args.kwargs["check"], False)

    def test_audit_does_not_count_helper_only_test_directory(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            (root / "src" / "ops_field_brief").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src" / "ops_field_brief" / "brief.py").write_text("x = 1\n")
            (root / "tests" / "helper.py").write_text("x = 1\n")
            (root / "tests" / "__init__.py").write_text("")
            (root / "README.md").write_text("README\n")
            (root / "CHANGELOG.md").write_text("Changes\n")
            with patch.object(agent, "ROOT", root):
                self.assertEqual(agent.audit_repository()["test_files"], [])
                (root / "tests" / "test_valid.py").write_text("def test_valid(): pass\n")
                self.assertEqual(agent.audit_repository()["test_files"], ["test_valid.py"])

    def test_gemini_authenticates_in_header_without_exposing_key_in_url(self):
        secret = "example-secret-should-not-appear-in-url"
        body = b'{"candidates":[{"content":{"parts":[{"text":"assessment"}]}}]}'
        with patch.object(agent.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = body
            self.assertEqual(agent.query_gemini_api("Review the audit", secret), "assessment")
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), secret)
        self.assertNotIn(secret, request.full_url)
        self.assertEqual(
            json.loads(request.data),
            {"contents": [{"parts": [{"text": "Review the audit"}]}]},
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    def test_gemini_malformed_response_shapes_are_ignored(self):
        malformed = (
            None,
            [],
            "not an object",
            {},
            {"candidates": {}},
            {"candidates": [None]},
            {"candidates": [{"content": None}]},
            {"candidates": [{"content": {"parts": None}}]},
            {"candidates": [{"content": {"parts": [None, {"text": 3}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "   "}]}}]},
        )
        with patch.object(agent.urllib.request, "urlopen") as urlopen:
            for payload in malformed:
                with self.subTest(payload=payload):
                    urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                        payload
                    ).encode("utf-8")
                    self.assertIsNone(agent.query_gemini_api("Review", "test-key"))

    def test_gemini_selects_first_nonempty_text_from_mixed_parts(self):
        parts = [
            None,
            {"text": ""},
            {"thought": True},
            {"text": "Useful response"},
            {"text": "Later"},
        ]
        payload = {"candidates": [{"content": {"parts": parts}}]}
        with patch.object(agent.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                payload
            ).encode("utf-8")
            self.assertEqual(agent.query_gemini_api("Review", "test-key"), "Useful response")

    def test_gemini_uses_later_candidate_if_earlier_one_is_unusable(self):
        response = {
            "candidates": [
                None,
                {},
                {"content": {"parts": None}},
                {"content": {"parts": [{"text": "  "}, {"text": 42}]}},
                {"content": {"parts": [{"text": "Actual assessment"}]}},
                {"content": {"parts": [{"text": "Later assessment"}]}},
            ]
        }
        with patch.object(agent.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                response
            ).encode("utf-8")
            self.assertEqual(agent.query_gemini_api("Review", "test-key"), "Actual assessment")

    def test_gemini_keeps_first_valid_candidate_and_rejects_all_invalid(self):
        first = {
            "candidates": [
                {"content": {"parts": [{"text": "First"}]}},
                {"content": {"parts": [{"text": "Second"}]}},
            ]
        }
        all_invalid = {"candidates": [None, {}, {"content": {"parts": ["nothing", {"text": 1}]}}]}
        with patch.object(agent.urllib.request, "urlopen") as urlopen:
            for payload, expected in ((first, "First"), (all_invalid, None)):
                with self.subTest(expected=expected):
                    urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                        payload
                    ).encode("utf-8")
                    self.assertEqual(agent.query_gemini_api("Review", "test-key"), expected)

    def test_invalid_gemini_utf8_does_not_interrupt_local_audit(self):
        secret = "test-private-api-key"
        responses = (b"\xff", b'{"candidates": [\xe2\x82]}')
        for body in responses:
            with self.subTest(body=body):
                errors = io.StringIO()
                output = io.StringIO()
                audit = self.healthy_audit()
                with (
                    patch.object(agent.urllib.request, "urlopen") as urlopen,
                    patch.object(agent, "run_tests", return_value=(True, "OK")),
                    patch.object(agent, "audit_repository", return_value=audit),
                    patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True),
                    redirect_stderr(errors),
                    redirect_stdout(output),
                ):
                    urlopen.return_value.__enter__.return_value.read.return_value = body
                    self.assertEqual(agent.main(["--allow-external-api"]), 0)
                self.assertIn("Gemini API request note:", errors.getvalue())
                self.assertIn("without text candidate", output.getvalue())
                self.assertNotIn(secret, errors.getvalue())

    def test_gemini_error_does_not_print_secret(self):
        secret = "credential-do-not-log"
        error = agent.urllib.error.URLError(f"diagnostic contained {secret}")
        output = io.StringIO()
        with (
            patch.object(agent.urllib.request, "urlopen", side_effect=error),
            redirect_stderr(output),
        ):
            self.assertIsNone(agent.query_gemini_api("Review", secret))
        self.assertNotIn(secret, output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())

    def test_external_feedback_is_escaped_redacted_and_bounded_in_ci_logs(self):
        secret = "never-echo-this-api-key"
        feedback = (
            "Useful feedback\n::add-mask::unexpected\n"
            "::warning file=readme.md::untrusted"
            "\r\x1b[31m"
            " \u202e hidden "
            + secret
        )
        output = io.StringIO()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=self.healthy_audit()),
            patch.object(agent, "query_gemini_api", return_value=feedback) as query,
            patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True),
            redirect_stdout(output),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)

        query.assert_called_once()
        log = output.getvalue()
        marker = "Gemini Assessment (escaped, max 4000 characters): "
        self.assertIn(marker, log)
        encoded = log.split(marker, 1)[1].splitlines()[0]
        self.assertEqual(json.loads(encoded), feedback.strip().replace(secret, "[REDACTED]"))
        self.assertNotIn(secret, log)
        self.assertNotIn("\x1b", log)
        self.assertNotIn("\n::add-mask::", log)
        self.assertNotIn("\n::warning", log)
        self.assertEqual(encoded.count('"'), 2)

        long_output = io.StringIO()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=self.healthy_audit()),
            patch.object(agent, "query_gemini_api", return_value="x" * 5000),
            patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True),
            redirect_stdout(long_output),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)
        long_payload = long_output.getvalue().split(marker, 1)[1].splitlines()[0]
        self.assertEqual(json.loads(long_payload), "x" * 4000)

    def test_incomplete_repository_fails_audit_before_external_api(self):
        cases = (
            ("no Python source modules", {"source_files": []}),
            ("no Python test modules", {"test_files": []}),
            ("README.md is absent or empty", {"readme_present": False}),
            ("README.md is absent or empty", {"readme_characters": 0}),
            ("CHANGELOG.md is absent or empty", {"changelog_present": False}),
            ("CHANGELOG.md is absent or empty", {"changelog_characters": 0}),
        )
        for expected, change in cases:
            with self.subTest(expected=expected, change=change):
                audit = self.healthy_audit()
                audit.update(change)
                errors = io.StringIO()
                with (
                    patch.object(agent, "run_tests", return_value=(True, "OK")),
                    patch.object(agent, "audit_repository", return_value=audit),
                    patch.object(agent, "query_gemini_api") as query,
                    patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}, clear=True),
                    redirect_stderr(errors),
                ):
                    self.assertEqual(agent.main(["--allow-external-api"]), 1)
                self.assertIn("Repository audit failed:", errors.getvalue())
                self.assertIn(expected, errors.getvalue())
                query.assert_not_called()

    def test_multiple_missing_components_are_reported_together(self):
        audit = self.healthy_audit()
        audit.update({"source_files": [], "test_files": [], "readme_present": False})
        errors = io.StringIO()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api") as query,
            redirect_stderr(errors),
        ):
            self.assertEqual(agent.main([]), 1)
        self.assertIn("no Python source modules", errors.getvalue())
        self.assertIn("no Python test modules", errors.getvalue())
        self.assertIn("README.md is absent or empty", errors.getvalue())
        query.assert_not_called()

    def test_api_key_alone_keeps_audit_local_only(self):
        audit = self.healthy_audit()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api") as query,
            patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}, clear=True),
        ):
            self.assertEqual(agent.main([]), 0)
        query.assert_not_called()

    def test_external_flag_without_key_keeps_audit_local_only(self):
        audit = self.healthy_audit()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api") as query,
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)
        query.assert_not_called()

    def test_external_api_requires_flag_and_key(self):
        audit = self.healthy_audit()
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api", return_value="assessment") as query,
            patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}, clear=True),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)
        query.assert_called_once()
