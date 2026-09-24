from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmark.demo import run_reference
from benchmark.environment import BenchmarkError, SalesLeadEnvironment
from benchmark.judge import RUBRIC, validate_response


class BenchmarkMVPTests(unittest.TestCase):
    def test_reference_run_scores_all_deterministic_points(self):
        with TemporaryDirectory() as directory:
            report = run_reference(Path(directory))
        self.assertEqual(report["deterministic_score"], 9.0)
        self.assertEqual(report["status"], "awaiting_llm_judge")

    def test_reset_restores_initial_state(self):
        env = SalesLeadEnvironment()
        env.state["crm"]["leads"][0]["status"] = "Changed"
        env.reset()
        self.assertEqual(env.state["crm"]["leads"][0]["status"], "New")
        self.assertEqual(env.events, [])

    def test_researcher_cannot_update_crm(self):
        env = SalesLeadEnvironment()
        with self.assertRaises(BenchmarkError) as caught:
            env.update_lead("research_specialist", "LEAD-1007", {"status": "Qualified"})
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")

    def test_customer_reply_is_gated(self):
        env = SalesLeadEnvironment()
        with self.assertRaises(BenchmarkError) as caught:
            env.receive_customer_reply("sales_coordinator", "THREAD-2001")
        self.assertEqual(caught.exception.code, "REPLY_NOT_AVAILABLE")

    def test_llm_judge_response_is_bounded_to_one_point(self):
        response = {name: maximum for name, maximum in RUBRIC.items()}
        response.update(strengths=[], problems=[])
        self.assertEqual(validate_response(response), 1.0)


if __name__ == "__main__":
    unittest.main()
