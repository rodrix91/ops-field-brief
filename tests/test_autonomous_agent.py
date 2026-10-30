import io
import json
import os
import unittest
from contextlib import redirect_stderr
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
