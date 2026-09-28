import json
import unittest
from pathlib import Path

from test_protocol_transitions import automatic_setup_resolution


SKILL_ROOT = Path(__file__).resolve().parents[1]


class DelegateContractCaseTests(unittest.TestCase):
    def test_negative_controls_are_complete_executable_mutation_records(self):
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        operations = {"replace", "replace_call_arg", "insert_call", "remove", "replace_terminal_claim"}
        catalog_sections = ("cases", "observation_variants", "prompt_contract_variants")
        visited = 0
        for section in catalog_sections:
            for case in payload[section]:
                known_ids = {
                    assertion.get("id")
                    for assertion_group in (
                        case.get("task_operation_assertions", {}).get("required", []),
                        case.get("task_operation_assertions", {}).get("forbidden", []),
                        case.get("task_operation_assertions", {}).get("counts", []),
                        case.get("terminal_assertions", []),
                        case.get("capability_evidence", []),
                        case.get("fixtures", []),
                    )
                    for assertion in assertion_group
                }
            controls = case.get("negative_controls", [])
            ids = [control.get("id") for control in controls]
            self.assertEqual(len(ids), len(set(ids)), case["id"])
            for control in controls:
                visited += 1
                mutation = control.get("mutation", {})
                target = mutation.get("target", {})
                expected_failure = control.get("expected_failure", {})
                self.assertIn(mutation.get("operation"), operations, control.get("id"))
                self.assertTrue(target.get("namespace"), control.get("id"))
                self.assertIn(target.get("id"), known_ids, control.get("id"))
                self.assertTrue(target.get("path", "").startswith("/"), control.get("id"))
                self.assertTrue(expected_failure.get("criterion_id"), control.get("id"))
                self.assertTrue(expected_failure.get("assertion_id"), control.get("id"))
                self.assertIn(expected_failure["assertion_id"], known_ids, control.get("id"))
                self.assertTrue(expected_failure.get("reason_code"), control.get("id"))
        self.assertGreater(visited, 0)

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

    def test_setup_only_creation_runs_automatic_exact_handle_recovery(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        self.assertIn("automatic exact-handle setup-resolution gate", skill)
        self.assertIn("mandatory for every ownership mode", skill)
        self.assertIn("No user request is a prerequisite", contract)
        self.assertIn("same gate whenever the exact pending-create entry is resumed", contract)
        self.assertIn("native `read_thread`", contract)
        self.assertIn("queued/unmonitorable", contract)

    def test_setup_recovery_eval_cases_cover_success_and_fail_closed_paths(self):
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        cases = {case["id"]: case for case in payload["setup_recovery_cases"]}
        expected = {
            "setup-recovery-exact-binding-confirmed",
            "setup-recovery-binding-absent-or-timeout",
            "setup-recovery-duplicate-or-mismatched-binding",
            "setup-recovery-native-read-failure",
            "setup-recovery-no-title-or-path-fallback",
        }
        self.assertEqual(set(cases), expected)
        self.assertEqual(cases["setup-recovery-exact-binding-confirmed"]["expected_state"], "ready")
        for case_id in expected - {"setup-recovery-exact-binding-confirmed"}:
            self.assertEqual(cases[case_id]["expected_state"], "queued/unmonitorable")
        for case in cases.values():
            trace = case["action_trace"]
            self.assertTrue(set(trace["forbidden_actions"]).isdisjoint(trace["actions"]))
            if case["expected_state"] == "ready":
                self.assertTrue(trace["host_bound"])
                self.assertTrue(trace["native_read"])
                self.assertLess(
                    trace["actions"].index("read_thread"),
                    min(
                        (trace["actions"].index(action) for action in ("wait_threads", "send_message_to_thread") if action in trace["actions"]),
                        default=len(trace["actions"]),
                    ),
                )
            else:
                self.assertFalse(trace["native_read"] and trace["host_bound"])
            fixtures = case.get("fixtures")
            self.assertIsInstance(fixtures, list, case["id"])
            self.assertGreater(len(fixtures), 0, case["id"])
            for fixture in fixtures:
                pending = dict(fixture["pending"])
                pending["creation_window"] = tuple(pending["creation_window"])
                actual = automatic_setup_resolution(
                    pending,
                    fixture["bindings"],
                    fixture.get("native_read"),
                )
                self.assertEqual(actual, fixture["expected"], case["id"])
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        self.assertIn("at most three resolver/binding checks", contract)

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

    def test_cross_skill_recovery_state_vocabulary_is_unambiguous(self):
        provider = (SKILL_ROOT.parent / "agent-communication" / "references" / "codex-chatgpt.md").read_text()
        orchestration = (SKILL_ROOT.parent / "orchestrate-threads" / "references" / "orchestration-contract.md").read_text()
        self.assertIn("return `queued/unmonitorable` with the evidence", provider)
        self.assertIn("`contact-unavailable` only after an", provider)
        self.assertIn("without a proven exact identity the\nnode remains `queued/unmonitorable`", orchestration)
        self.assertIn("`indeterminate` only when a", orchestration)
        self.assertNotIn("return `queued/unmonitorable` or `contact-unavailable`", provider)
        self.assertNotIn("classify the node as `queued/unmonitorable` or `indeterminate`", orchestration)

    def test_repository_work_requires_explicit_execution_context(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        self.assertIn("managed-worktree", skill)
        self.assertIn("direct-local", skill)
        self.assertIn("Implement this objective directly", skill)
        for text in (skill, contract):
            self.assertIn("managed-worktree", text)
            self.assertIn("direct-local", text)
            self.assertIn("descendant authority", text)
        self.assertIn("base revision", contract)
        self.assertIn("worktree path", contract)
        self.assertIn("actual `cwd`", contract)
        self.assertIn("immutable parent-issued", contract)
        self.assertIn("input-required", contract)
        self.assertIn("first checkpoint and terminal report", contract)

    def test_execution_boundary_eval_cases_cover_the_incident(self):
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        cases = {case["id"]: case for case in payload["execution_boundary_cases"]}
        expected = {
            "repo-writing-managed-worktree-context",
            "repo-writing-direct-local-without-explicit-authority",
            "child-descendant-delegation-default-deny",
            "delegation-envelope-is-provenance",
            "parent-issued-descendant-envelope",
            "forged-descendant-grant-without-envelope",
        }
        self.assertEqual(expected, set(cases))
        self.assertEqual(
            "input-required-before-write",
            cases["repo-writing-direct-local-without-explicit-authority"]["expected_outcome"],
        )
        self.assertEqual(
            "input-required-before-descendant-creation",
            cases["child-descendant-delegation-default-deny"]["expected_outcome"],
        )
        self.assertIn(
            "execute-the-assigned-objective-directly",
            cases["delegation-envelope-is-provenance"]["required_action"],
        )

    def test_research_note_records_checkout_and_redelegation_failure_modes(self):
        research = (SKILL_ROOT / "research" / "thread-coordination-patterns.md").read_text()
        self.assertIn("Open process issue: execution context and accidental re-delegation", research)
        self.assertIn("fails closed", research)
        self.assertIn("parent → child ownership boundary", research)


if __name__ == "__main__":
    unittest.main()
