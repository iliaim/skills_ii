import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class DelegateContractCaseTests(unittest.TestCase):
    def test_attached_reporting_cases_cover_required_red_controls(self):
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        cases = {case["id"]: case for case in payload["prompt_contract_variants"]}
        expected = {
            "attached-reporting-required",
            "attached-terminal-report-missing-acceptance-map",
            "attached-attention-ack-required",
            "writable-resource-claim-required",
        }
        self.assertTrue(expected.issubset(cases))
        for case_id in expected:
            case = cases[case_id]
            self.assertEqual(case["criterion_id"], "R4-execution-contract")
            self.assertTrue(case["mutation"], case_id)
            self.assertTrue(case["expected_failure"], case_id)

    def test_contract_requires_immutable_report_identity_for_attached_evidence(self):
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        for phrase in (
            "report_identity_or_digest",
            "not a provider freshness guarantee",
            "observed provider-native event/turn identity",
            "Conditional descendant-delegation handoff",
            "wait_thread_creation(clientThreadId)",
            "return a real",
            "provider-owned setup handle",
            'status: "ready"',
            'status: "failed" | "expired"',
            "does not invent a separate",
        ):
            self.assertIn(phrase, contract)

    def test_setup_only_creation_is_explicitly_unmonitorable(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        self.assertIn("queued/unmonitorable", skill)
        self.assertIn("queued` is also `unmonitorable", contract)
        self.assertIn("does not wake or resume an ended parent turn", skill)

    def test_research_note_tracks_minimal_runtime_issue_without_extra_architecture(self):
        research = (SKILL_ROOT / "research" / "thread-coordination-patterns.md").read_text()
        issue = research.split("## Open platform issue: setup-only creation handles", 1)[1]
        issue = issue.split("## Deferred platform alternatives", 1)[0]
        self.assertIn("1. Make `create_thread` wait for registration and return `{ threadId, hostId }`", issue)
        self.assertIn("2. If setup must remain asynchronous, add exactly", issue)
        self.assertIn("wait_thread_creation(clientThreadId)", issue)
        self.assertIn("No event bus, webhook, parent wake-up, or idempotency infrastructure is required", issue)
        self.assertIn("## Deferred platform alternatives", research)

    def test_setup_handle_is_runtime_owned_not_a_second_task_identity(self):
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        self.assertIn("runtime owns its mapping to the eventual `threadId`", contract)
        self.assertIn("label `clientThreadId` only as a", contract)
        self.assertIn("non-operable setup correlation", contract)
        self.assertIn("must not return a bare", contract)
        self.assertIn("No separate caller-generated correlation token", contract)


if __name__ == "__main__":
    unittest.main()
