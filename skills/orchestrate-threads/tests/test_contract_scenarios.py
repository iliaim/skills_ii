import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class OrchestrationContractScenarioTests(unittest.TestCase):
    def test_adversarial_scenarios_have_evidence_and_forbidden_operations(self):
        payload = json.loads((SKILL_ROOT / "evals" / "scenarios.json").read_text())
        scenarios = {scenario["id"]: scenario for scenario in payload["scenarios"]}
        expected = {
            "attached-child-missing-terminal-report",
            "live-child-no-progress",
            "attention-response-without-ack",
            "orphaned-create-reconciliation",
            "ambiguous-create-transport-failure",
            "stale-dependency-evidence",
            "overlapping-resource-claims",
            "unowned-matching-path-claim",
            "false-completion-without-verification",
            "authority-revoked-while-running",
            "wrong-artifact-revision-review",
            "compound-live-stale-conflict",
        }
        self.assertTrue(expected.issubset(scenarios))
        for scenario_id in expected:
            scenario = scenarios[scenario_id]
            self.assertTrue(scenario["forbidden_operations"], scenario_id)
            self.assertTrue(scenario["required_evidence"], scenario_id)
            self.assertTrue(scenario["pass_condition"], scenario_id)

    def test_contract_requires_immutable_report_identity_and_descendant_handoff(self):
        contract = (SKILL_ROOT / "references" / "orchestration-contract.md").read_text()
        advanced_modes = (SKILL_ROOT / "references" / "advanced-modes.md").read_text()
        for phrase in (
            "source_report_identity_or_digest",
            "not authoritative freshness evidence",
        ):
            self.assertIn(phrase, contract)
        for phrase in ("bounded descendant-delegation envelope", "cannot mint or widen it"):
            self.assertIn(phrase, advanced_modes)

    def test_queued_creation_is_unmonitorable_and_does_not_wake_parent(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        contract = (SKILL_ROOT / "references" / "orchestration-contract.md").read_text()
        agent_contract = (SKILL_ROOT.parent / "agent-communication" / "references" / "codex-chatgpt.md").read_text()
        self.assertIn("`queued/unmonitorable`", skill)
        self.assertIn("queued/unmonitorable", contract)
        self.assertIn("cannot be observed,", contract)
        self.assertIn("Keep the parent turn", contract)
        self.assertIn("queued/unmonitorable", agent_contract)
        self.assertIn("child message will wake or resume the parent", agent_contract)

    def test_evidence_only_gate_does_not_require_an_artifact(self):
        contract = (SKILL_ROOT / "references" / "orchestration-contract.md").read_text()
        scenarios = json.loads((SKILL_ROOT / "evals" / "scenarios.json").read_text())["scenarios"]
        evidence_only = next(item for item in scenarios if item["id"] == "dependency-accepted-evidence")
        self.assertEqual(evidence_only["expected_state"]["upstream_availability"], "not_required")
        self.assertIn("`not_applicable`", contract)
        self.assertIn("acceptance must not invent an integration requirement", contract)


if __name__ == "__main__":
    unittest.main()
