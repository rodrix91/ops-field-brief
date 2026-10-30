import io
import json
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts import autonomous_agent as agent


class AutonomousAgentTests(unittest.TestCase):
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

    def test_api_key_alone_keeps_audit_local_only(self):
        audit = {"source_files": ["brief.py"], "test_files": ["test_brief.py"]}
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api") as query,
            patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}, clear=True),
        ):
            self.assertEqual(agent.main([]), 0)
        query.assert_not_called()

    def test_external_flag_without_key_keeps_audit_local_only(self):
        audit = {"source_files": ["brief.py"], "test_files": ["test_brief.py"]}
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api") as query,
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)
        query.assert_not_called()

    def test_external_api_requires_flag_and_key(self):
        audit = {"source_files": ["brief.py"], "test_files": ["test_brief.py"]}
        with (
            patch.object(agent, "run_tests", return_value=(True, "OK")),
            patch.object(agent, "audit_repository", return_value=audit),
            patch.object(agent, "query_gemini_api", return_value="assessment") as query,
            patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}, clear=True),
        ):
            self.assertEqual(agent.main(["--allow-external-api"]), 0)
        query.assert_called_once()
