import os
import unittest
from unittest.mock import patch

from scripts import autonomous_agent as agent


class AutonomousAgentTests(unittest.TestCase):
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
