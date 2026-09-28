import json
import copy
import unittest
from pathlib import Path

from test_protocol_transitions import automatic_setup_resolution


SKILL_ROOT = Path(__file__).resolve().parents[1]


def apply_catalog_mutation(target_record, mutation):
    """Apply one catalog mutation to a detached assertion/fixture record."""
    operation = mutation["operation"]
    path = mutation["target"]["path"]
    if operation == "insert_call":
        if path not in {"/before", "/after"}:
            raise AssertionError(f"unsupported insertion anchor: {path}")
        return dict(target_record, **{path.lstrip("/"): copy.deepcopy(mutation["value"])})
    path_parts = path.strip("/").split("/")
    mutated = copy.deepcopy(target_record)
    cursor = mutated
    for path_part in path_parts[:-1]:
        if isinstance(cursor, dict) and path_part in cursor:
            cursor = cursor[path_part]
        elif isinstance(cursor, list) and path_part.isdigit() and int(path_part) < len(cursor):
            cursor = cursor[int(path_part)]
        else:
            raise AssertionError(f"unresolvable mutation path: {path}")
    leaf = path_parts[-1]
    if isinstance(cursor, dict) and leaf in cursor:
        current = cursor[leaf]
    elif isinstance(cursor, list) and leaf.isdigit() and int(leaf) < len(cursor):
        current = cursor[int(leaf)]
    else:
        raise AssertionError(f"unresolvable mutation path: {path}")
    if operation == "remove":
        if isinstance(cursor, dict):
            del cursor[leaf]
        else:
            del cursor[int(leaf)]
    elif operation in {"replace", "replace_call_arg", "replace_terminal_claim"}:
        if isinstance(cursor, dict):
            cursor[leaf] = copy.deepcopy(mutation["value"])
        else:
            cursor[int(leaf)] = copy.deepcopy(mutation["value"])
    else:
        raise AssertionError(f"unsupported mutation operation: {operation}")
    return mutated


def _subset_match(actual, expected):
    """Match the catalog's subset arguments without weakening nested values."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _subset_match(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _subset_match(actual_value, expected_value)
            for actual_value, expected_value in zip(actual, expected)
        )
    return actual == expected


def _operation_assertions(case):
    assertions = []
    operation_assertions = case.get("task_operation_assertions", {})
    for kind in ("required", "forbidden", "counts"):
        assertions.extend(
            (kind, assertion)
            for assertion in operation_assertions.get(kind, [])
        )
    return assertions


def _assertion_by_id(case, assertion_id):
    for kind, assertion in _operation_assertions(case):
        if assertion.get("id") == assertion_id:
            return kind, assertion
    return None, None


def _baseline_trace(case):
    """Materialize the expected operation trace as a detached oracle input."""
    trace = []
    for assertion in case.get("task_operation_assertions", {}).get("required", []):
        args_match = assertion.get("args_match", {})
        trace.append({
            "assertion_id": assertion["id"],
            "tool": assertion["tool"],
            "args": copy.deepcopy(args_match.get("value", {})),
        })
    return trace


def _insert_index(trace, target_id, before):
    for index, call in enumerate(trace):
        if call["assertion_id"] == target_id:
            return index if before else index + 1
    return 0


def _mutated_trace(case, control):
    mutation = control["mutation"]
    target = mutation["target"]
    self_assertion = target["namespace"] == "candidate_trace"
    trace = _baseline_trace(case)
    if not self_assertion:
        return trace
    operation = mutation["operation"]
    if operation == "insert_call":
        index = _insert_index(trace, target["id"], target["path"] == "/before")
        value = mutation["value"]
        trace.insert(index, {
            "assertion_id": f"mutation:{control['id']}",
            "tool": value["tool"],
            "args": copy.deepcopy(value.get("args", {})),
        })
        return trace
    call_index = next(
        (index for index, call in enumerate(trace) if call["assertion_id"] == target["id"]),
        None,
    )
    if call_index is None:
        raise AssertionError(f"mutation target is not a required call: {control['id']}")
    assertion = next(
        assertion for assertion in case["task_operation_assertions"]["required"]
        if assertion["id"] == target["id"]
    )
    mutated_assertion = apply_catalog_mutation(assertion, mutation)
    trace[call_index]["args"] = copy.deepcopy(
        mutated_assertion.get("args_match", {}).get("value", {})
    )
    return trace


def _matching_calls(trace, assertion):
    expected = assertion.get("args_match", {}).get("value", {})
    return [
        call for call in trace
        if call["tool"] == assertion["tool"] and _subset_match(call["args"], expected)
    ]


def _operation_assertion_passes(kind, assertion, trace):
    count = len(_matching_calls(trace, assertion))
    if kind == "forbidden":
        return count == 0
    return assertion.get("min", 0) <= count <= assertion.get("max", float("inf"))


def _resolve_pointer(record, path):
    cursor = record
    for part in path.strip("/").split("/"):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        elif isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
            cursor = cursor[int(part)]
        else:
            return None, False
    return cursor, True


def _record_groups(case):
    groups = {}
    operation_assertions = case.get("task_operation_assertions", {})
    for group_name in ("required", "forbidden", "counts"):
        for record in operation_assertions.get(group_name, []):
            groups[record["id"]] = record
    for group_name in ("terminal_assertions", "capability_evidence", "fixtures"):
        for record in case.get(group_name, []):
            groups[record["id"]] = record
    return groups


def _mutated_records(case, control):
    records = copy.deepcopy(_record_groups(case))
    mutation = control["mutation"]
    target = mutation["target"]
    if target["id"] not in records:
        raise AssertionError(f"unknown mutation record: {control['id']}")
    records[target["id"]] = apply_catalog_mutation(records[target["id"]], mutation)
    return records


def _dependent_evidence_fails(case, control):
    """Recompute evidence predicates after a fixture/evidence mutation."""
    target = control["mutation"]["target"]
    records = _mutated_records(case, control)
    dependent = [
        evidence for evidence in case.get("capability_evidence", [])
        if any(premise.get("fixture_id") == target["id"] for premise in evidence.get("premises", []))
    ]
    if target["namespace"] == "capability_evidence":
        baseline = _record_groups(case)[target["id"]]
        return len(records[target["id"]].get("premises", [])) < len(baseline.get("premises", []))
    if not dependent:
        return False
    for evidence in dependent:
        values = []
        for premise in evidence.get("premises", []):
            record = records.get(premise.get("fixture_id"))
            if record is None:
                values.append(None)
                continue
            value, present = _resolve_pointer(record, premise.get("path", ""))
            values.append(value if present else None)
        operator = evidence.get("derivation", {}).get("operator")
        expected = evidence.get("derivation", {}).get("expected")
        if any(value is None for value in values):
            return True
        if operator == "equal" and values and values[0] != expected:
            return True
        if operator in {"all", "present"} and not all(values):
            return True
        if operator == "same_destination_exclusive_interval":
            if not all(values) or len(values) < 2 or values[0] != values[1]:
                return True
        if operator == "contract_default_when_false" and values[0] is not False:
            return True
        if operator == "not_supported_by_contract":
            return True
    return False


def _terminal_claim_fails(case, control):
    target = control["mutation"]["target"]
    baseline = _record_groups(case)[target["id"]]
    mutated = _mutated_records(case, control)[target["id"]]
    # Terminal claims are semantic assertions, so this oracle requires the
    # mutation to alter the claim and checks that the altered claim no longer
    # carries the minimum semantic signals of the original claim.
    baseline_statement = baseline.get("statement", "").lower()
    statement = mutated.get("statement", "").lower()
    if statement == baseline_statement:
        return False
    reason = control["expected_failure"]["reason_code"]
    required_valid_signals = {
        "queued-coordination-not-fulfilled": ("queued", "suspended"),
        "nonterminal-snapshot-not-complete": ("slice", "incomplete", "ac-2"),
        "explicit-delegation-default-not-coordinated": ("slice", "incomplete"),
        "child-slice-cannot-complete-parent": ("slice", "incomplete"),
        "scheduled-heartbeat-not-event-callback": ("slice", "parent"),
        "human-notification-not-agent-wakeup": ("slice", "parent"),
        "no-native-parent-auto-resume": ("slice", "parent"),
        "nonterminal-cloud-snapshot": ("ac-c", "before"),
        "parent-acceptance-unmapped": ("ac-c", "map"),
        "title-not-stable-identity": ("not", "title"),
        "needs-attention-is-not-terminal-success": ("incomplete", "blocker"),
        "meta-reference-not-creation-authority": ("without", "creating"),
        "internal-not-sidebar": ("parent", "evidence"),
        "user-input-not-child-event": ("parent", "reassess", "not"),
        "target-error-not-completion": ("incomplete", "error"),
        "target-error-not-needs-attention": ("incomplete", "error"),
        "unchanged-snapshot-not-progress": ("suppress", "identical", "preserve"),
        "unchanged-wait-cursor-not-preserved": ("preserve", "cursor"),
    }
    signals = required_valid_signals.get(reason, ())
    return bool(signals) and not all(signal in statement for signal in signals)


def _prompt_contract_fails(prompt, reason):
    prompt = prompt.lower()
    rules = {
        "execution-contract-incomplete": lambda: len(prompt.split()) < 8,
        "prompt-sensitive-data-leak": lambda: "private_sentinel_do_not_transfer" in prompt,
        "prompt-duplicates-durable-artifact": lambda: "durable_body_sentinel_do_not_copy" in prompt,
        "one-shot-contract-overbuilt": lambda: any(
            phrase in prompt for phrase in ("goal registry", "status file", "phase gates", "cursor ledger")
        ),
        "mutable-fact-revalidation-missing": lambda: "without re-reading" in prompt,
        "parent-observer-mechanics-in-child-prompt": lambda: any(
            phrase in prompt for phrase in ("record useful checkpoints", "status=ready", "wait_threads")
        ),
        "child-slice-parent-relationship-missing": lambda: "parent" not in prompt,
        "attached-reporting-contract-missing": lambda: not all(
            phrase in prompt for phrase in ("checkpoint", "report", "acceptance")
        ),
        "canonical-terminal-report-incomplete": lambda: (
            "acceptance_map" not in prompt or "omit acceptance_map" in prompt
        ),
        "attention-acknowledgement-missing": lambda: (
            "acknowledged" not in prompt or "without reporting" in prompt
        ),
        "attached-parent-callback-route-missing": lambda: "do not send" in prompt or "only in this local" in prompt,
        "writable-resource-claim-missing": lambda: not all(
            phrase in prompt for phrase in ("resource claim", "integration owner")
        ) or "do not declare" in prompt,
    }
    rule = rules.get(reason)
    return bool(rule and rule())


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
                known_records = {
                    assertion.get("id"): assertion
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
                    baseline = known_records[target["id"]]
                    mutated = apply_catalog_mutation(baseline, mutation)
                    self.assertNotEqual(mutated, baseline, control.get("id"))
                    if target["namespace"] == "candidate_trace":
                        kind, named_assertion = _assertion_by_id(case, expected_failure["assertion_id"])
                        self.assertIsNotNone(named_assertion, control.get("id"))
                        mutated_trace = _mutated_trace(case, control)
                        self.assertFalse(
                            _operation_assertion_passes(kind, named_assertion, mutated_trace),
                            control.get("id"),
                        )
                    elif target["namespace"] in {"fixture", "capability_evidence"}:
                        self.assertTrue(_dependent_evidence_fails(case, control), control.get("id"))
                    elif target["namespace"] == "candidate_terminal":
                        self.assertTrue(_terminal_claim_fails(case, control), control.get("id"))
                    else:
                        self.fail(f"unhandled mutation namespace: {target['namespace']}")
        cases_by_id = {case["id"]: case for case in payload["cases"]}
        semantic_assertions = {assertion["id"]: assertion for assertion in payload["semantic_assertions"]}
        expected_visited = sum(
            len(case.get("negative_controls", []))
            for section in catalog_sections
            for case in payload[section]
        )
        for case in payload["prompt_contract_variants"]:
            mutation = case.get("mutation", {})
            target = mutation.get("target", {})
            expected_failure = case.get("expected_failure", {})
            base_case = cases_by_id.get(case.get("base_case_id"))
            self.assertIsNotNone(base_case, case["id"])
            base_ids = {
                assertion.get("id")
                for assertion_group in (
                    base_case.get("task_operation_assertions", {}).get("required", []),
                    base_case.get("task_operation_assertions", {}).get("forbidden", []),
                    base_case.get("task_operation_assertions", {}).get("counts", []),
                    base_case.get("terminal_assertions", []),
                    base_case.get("capability_evidence", []),
                    base_case.get("fixtures", []),
                )
                for assertion in assertion_group
            }
            self.assertIn(mutation.get("operation"), operations, case["id"])
            self.assertTrue(target.get("namespace"), case["id"])
            self.assertIn(target.get("id"), base_ids, case["id"])
            self.assertTrue(target.get("path", "").startswith("/"), case["id"])
            if mutation["operation"] in {"replace", "replace_call_arg", "insert_call", "replace_terminal_claim"}:
                self.assertIn("value", mutation, case["id"])
            if mutation["operation"] == "replace_call_arg":
                value = mutation["value"]
                self.assertIsInstance(value, dict, case["id"])
                self.assertIsInstance(value.get("target"), dict, case["id"])
                self.assertTrue(value["target"].get("type"), case["id"])
                self.assertIsInstance(value.get("prompt"), str, case["id"])
                self.assertTrue(value["prompt"].strip(), case["id"])
                target_assertion = next(
                    assertion
                    for assertion in base_case["task_operation_assertions"]["required"]
                    if assertion["id"] == target["id"]
                )
                mutated_assertion = apply_catalog_mutation(target_assertion, mutation)
                self.assertNotEqual(mutated_assertion, target_assertion, case["id"])
                self.assertEqual(mutated_assertion["args_match"]["value"], value, case["id"])
            self.assertTrue(expected_failure.get("criterion_id"), case["id"])
            self.assertTrue(expected_failure.get("assertion_id"), case["id"])
            self.assertIn(expected_failure["assertion_id"], (*base_ids, *semantic_assertions), case["id"])
            self.assertIn(expected_failure["criterion_id"], {
                assertion.get("criterion_id") for assertion in semantic_assertions.values()
            }, case["id"])
            self.assertTrue(expected_failure.get("reason_code"), case["id"])
            prompt = mutation["value"].get("prompt", "")
            self.assertTrue(
                _prompt_contract_fails(prompt, expected_failure["reason_code"]),
                case["id"],
            )
        self.assertEqual(visited, expected_visited)
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
