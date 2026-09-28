import json
import copy
import re
import unittest
from pathlib import Path

from test_protocol_transitions import automatic_setup_resolution


SKILL_ROOT = Path(__file__).resolve().parents[1]


_REASON_CRITERION = {
    "child-slice-cannot-complete-parent": "R10-parent-authority",
    "client-id-not-operable": "R7-create-result",
    "cloud-bound-not-resolved-before-create": "R8-coordination",
    "cloud-observation-bound-exceeded": "R8-coordination",
    "cloud-observer-support-missing": "R8-coordination",
    "codex-wait-not-chat-observer": "R8-coordination",
    "commitment-duration-missing": "R5-destination-safety",
    "consent-not-access": "R6-cloud-sources",
    "continuation-not-creation": "R1-route",
    "create-only-unsolicited-observation": "R8-coordination",
    "delegation-default-provenance-missing": "R8-coordination",
    "dry-run-explicitly-forbids-creation": "R1-route",
    "error-without-native-guarantee-not-retryable": "R7-create-result",
    "exclusive-interval-wrong-destination": "R5-destination-safety",
    "explicit-create-only-override-ignored": "R8-coordination",
    "explicit-create-only-provenance-missing": "R8-coordination",
    "explicit-delegation-default-not-coordinated": "R8-coordination",
    "explicit-no-create-provenance-missing": "R1-route",
    "explicit-no-create-veto-ignored": "R1-route",
    "fork-not-clean-create": "R1-route",
    "git-default-isolation-lost": "R5-destination-safety",
    "human-notification-not-agent-wakeup": "R8-coordination",
    "indeterminate-not-retryable": "R7-create-result",
    "internal-not-sidebar": "R1-route",
    "invented-project": "R3-live-discovery",
    "known-writer-conflict": "R5-destination-safety",
    "lifecycle-authority-not-delegated": "R10-parent-authority",
    "material-target-ambiguity": "R3-live-discovery",
    "meta-reference-not-creation-authority": "R1-route",
    "needs-attention-is-not-terminal-success": "R9-progress",
    "needs-attention-must-surface-before-continuing": "R9-progress",
    "needs-attention-signal-missing": "R9-progress",
    "no-native-parent-auto-resume": "R8-coordination",
    "nonterminal-cloud-snapshot": "R9-progress",
    "nonterminal-snapshot-not-complete": "R9-progress",
    "off-target-read-not-permitted": "R8-coordination",
    "one-logical-delegation-exceeded": "R7-create-result",
    "pagination-cursor-not-forward-observer": "R8-coordination",
    "parent-acceptance-unmapped": "R10-parent-authority",
    "project-id-not-source-access": "R6-cloud-sources",
    "queued-coordination-not-fulfilled": "R8-coordination",
    "risk-waiver-not-exclusivity": "R5-destination-safety",
    "scheduled-heartbeat-not-event-callback": "R8-coordination",
    "snapshot-absence-not-lease": "R5-destination-safety",
    "stale-destination-metadata": "R3-live-discovery",
    "target-error-not-completion": "R9-progress",
    "target-error-not-needs-attention": "R9-progress",
    "technical-support-not-authority": "R6-cloud-sources",
    "terminal-coordination-unsupported": "R8-coordination",
    "title-not-stable-identity": "R7-create-result",
    "unchanged-snapshot-not-progress": "R9-progress",
    "unchanged-wait-cursor-not-preserved": "R9-progress",
    "uncommitted-authority-missing": "R5-destination-safety",
    "user-input-must-be-processed-before-wait": "R9-progress",
    "user-input-not-child-event": "R9-progress",
    "visible-message-not-callback": "R8-coordination",
    "wait-cursor-not-reused": "R8-coordination",
}


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


def _required_assertion(case, assertion_id, catalog=None):
    for assertion in case.get("task_operation_assertions", {}).get("required", []):
        if assertion["id"] == assertion_id:
            return assertion
    if catalog and case.get("base_case_id"):
        base_case = catalog[case["base_case_id"]]
        return _required_assertion(base_case, assertion_id, catalog)
    return None


def _baseline_trace(case, catalog=None):
    """Materialize the expected operation trace as a detached oracle input."""
    trace = []
    required = case.get("task_operation_assertions", {}).get("required", [])
    if catalog and case.get("base_case_id"):
        base_case = catalog[case["base_case_id"]]
        inherited = []
        for assertion in base_case.get("task_operation_assertions", {}).get("required", []):
            inherited.append(assertion)
            if assertion["id"] == case.get("inherit_until"):
                break
        required = [*inherited, *required]
    for assertion in required:
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


def _mutated_trace(case, control, catalog=None):
    mutation = control["mutation"]
    target = mutation["target"]
    self_assertion = target["namespace"] == "candidate_trace"
    trace = _baseline_trace(case, catalog)
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
    assertion = _required_assertion(case, target["id"], catalog)
    if assertion is None:
        raise AssertionError(f"unknown required call: {control['id']}")
    mutated_assertion = apply_catalog_mutation(assertion, mutation)
    trace[call_index]["args"] = copy.deepcopy(
        mutated_assertion.get("args_match", {}).get("value", {})
    )
    return trace


def _matching_calls(trace, assertion):
    args_match = assertion.get("args_match", {})
    expected = args_match.get("value", {})
    mode = args_match.get("mode", "subset")
    matcher = (lambda actual: actual == expected) if mode == "exact" else (
        lambda actual: _subset_match(actual, expected)
    )
    return [
        call for call in trace
        if call["tool"] == assertion["tool"] and matcher(call["args"])
    ]


def _operation_assertion_passes(kind, assertion, trace):
    occurrence = assertion.get("occurrence")
    if occurrence is not None:
        operation_calls = [call for call in trace if call["tool"] == assertion["tool"]]
        if occurrence < 1 or occurrence > len(operation_calls):
            return False
        expected = assertion.get("args_match", {}).get("value", {})
        mode = assertion.get("args_match", {}).get("mode", "subset")
        actual = operation_calls[occurrence - 1]["args"]
        return actual == expected if mode == "exact" else _subset_match(actual, expected)
    count = len(_matching_calls(trace, assertion))
    if kind == "forbidden":
        return count == 0
    return assertion.get("min", 0) <= count <= assertion.get("max", float("inf"))


def _partial_order_passes(case, trace, catalog=None):
    edges = list(case.get("task_operation_assertions", {}).get("partial_order", []))
    if catalog and case.get("base_case_id"):
        edges = [
            *catalog[case["base_case_id"]].get("task_operation_assertions", {}).get("partial_order", []),
            *edges,
        ]
    positions = {call["assertion_id"]: index for index, call in enumerate(trace)}
    if catalog and case.get("base_case_id") and case.get("inherit_until"):
        base_ids = [
            call["assertion_id"]
            for call in _baseline_trace(catalog[case["base_case_id"]])
        ]
        inherited_ids = base_ids[: base_ids.index(case["inherit_until"]) + 1]
        local_ids = {
            assertion["id"]
            for assertion in case.get("task_operation_assertions", {}).get("required", [])
        }
        inherited_positions = [positions[identifier] for identifier in inherited_ids if identifier in positions]
        if inherited_positions:
            boundary = max(inherited_positions)
            if any(positions[identifier] <= boundary for identifier in local_ids if identifier in positions):
                return False
    return all(
        positions[edge["before"]] < positions[edge["after"]]
        for edge in edges
        if edge["before"] in positions and edge["after"] in positions
    )


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


def _normalise_result_path(path):
    return path.removeprefix("/raw_result") or "/"


def _fixture_provenance_valid(case, records, premise):
    """Require a fixture to be causally released by its documented operation."""
    record = records.get(premise.get("fixture_id"))
    if record is None:
        return False
    kind = record.get("kind")
    if kind not in {"tool_result", "transport_or_tool_failure"}:
        return kind in {"host_user_event", "contract_snapshot"}
    release = record.get("release_after")
    if not isinstance(release, dict) or not release.get("operation"):
        return False
    args_match = release.get("args_match")
    if not isinstance(args_match, dict) or args_match.get("mode") not in {"subset", "exact"}:
        return False
    operation = release["operation"]
    operation_assertions = [
        assertion
        for _, assertion in _operation_assertions(case)
        if assertion.get("tool") == operation
    ]
    occurrence = release.get("occurrence")
    if occurrence is not None:
        operation_assertions = [
            assertion
            for assertion in operation_assertions
            if assertion.get("occurrence", 1) == occurrence
        ]
    expected_args = args_match.get("value", {})
    if not operation_assertions or not any(
        (
            assertion.get("args_match", {}).get("value", {}) == expected_args
            if args_match.get("mode") == "exact"
            else _subset_match(assertion.get("args_match", {}).get("value", {}), expected_args)
        )
        for assertion in operation_assertions
    ):
        return False
    documented = record.get("documented_decision_paths")
    path = premise.get("path", "")
    if kind == "transport_or_tool_failure":
        return path.startswith("/failure/")
    if not isinstance(documented, list) or not documented:
        return False
    normalised_path = _normalise_result_path(path)
    for item in documented:
        if item.get("path") != normalised_path:
            continue
        contract_ref = item.get("contract_ref")
        contract = records.get(contract_ref.get("fixture_id")) if isinstance(contract_ref, dict) else None
        result_paths = contract.get("snapshot", {}).get("result_paths", []) if contract else []
        if isinstance(contract_ref, dict) and contract_ref.get("path") == "/snapshot/result_paths":
            return normalised_path in result_paths
    return False


def _derived_evidence_value(operator, values, expected):
    if operator == "equal":
        return bool(values) and values[0] == expected
    if operator in {"all", "present"}:
        return bool(values) and all(values)
    if operator == "same_destination_exclusive_interval":
        return bool(values) and len(values) >= 2 and all(values) and values[0] == values[1]
    if operator == "contract_default_when_false":
        return bool(values) and values[0] is False
    if operator == "not_supported_by_contract":
        return False
    if operator == "selected-path-matches-refreshed-project":
        return len(values) == 3 and values[0] == values[1] and bool(values[2])
    if operator == "backing-kind-capability-difference":
        return (
            len(values) == 3
            and values[0] == "chatgpt"
            and "attention" in str(values[2]).lower()
            and "attention" not in str(values[1]).lower()
        )
    if operator == "clause_absent":
        # The evidence predicate is "the guarantee is present"; the
        # catalog operator names the negative test that proves it absent.
        return bool(values) and str(expected).lower() in str(values[0]).lower()
    if operator == "pairwise-identical-snapshot":
        return bool(values) and len(values) % 2 == 0 and values[: len(values) // 2] == values[len(values) // 2 :]
    return None


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


def _evidence_predicate_valid(case, records, evidence):
    permitted_roots = {
        "host_user_event": "/event/",
        "tool_result": "/raw_result/",
        "contract_snapshot": "/snapshot/",
        "transport_or_tool_failure": "/failure/",
    }
    values = []
    for premise in evidence.get("premises", []):
        record = records.get(premise.get("fixture_id"))
        if record is None:
            return False
        path = premise.get("path", "")
        root = permitted_roots.get(record.get("kind"))
        if not root or not path.startswith(root) or path.endswith("/request"):
            return False
        if not _fixture_provenance_valid(case, records, premise):
            return False
        value, present = _resolve_pointer(record, path)
        if not present:
            return False
        values.append(value)
    operator = evidence.get("derivation", {}).get("operator")
    expected = evidence.get("derivation", {}).get("expected")
    derived = _derived_evidence_value(operator, values, expected)
    if derived is None:
        return False
    return derived == evidence.get("value")


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
        return (
            len(records[target["id"]].get("premises", [])) < len(baseline.get("premises", []))
            and not _evidence_predicate_valid(case, records, records[target["id"]])
        )
    if not dependent:
        return False
    for evidence in dependent:
        if not _evidence_predicate_valid(case, records, records[evidence["id"]]):
            return True
    return False


def _operation_admission_passes(case, assertion_id, records, catalog=None):
    kind, assertion = _assertion_by_id(case, assertion_id)
    if assertion is None:
        return False
    trace = _baseline_trace(case, catalog)
    if not _operation_assertion_passes(kind, assertion, trace):
        return False
    return all(
        _evidence_predicate_valid(case, records, records[evidence["id"]])
        for evidence in case.get("capability_evidence", [])
    )


def _terminal_required_signals(reason):
    return {
        "queued-coordination-not-fulfilled": ("queued", "suspended"),
        "nonterminal-snapshot-not-complete": ("slice", "incomplete", "ac-2"),
        "explicit-delegation-default-not-coordinated": ("slice", "incomplete"),
        "child-slice-cannot-complete-parent": ("slice", "incomplete"),
        "scheduled-heartbeat-not-event-callback": ("slice", "complete"),
        "human-notification-not-agent-wakeup": ("slice", "complete"),
        "no-native-parent-auto-resume": ("slice", "complete"),
        "nonterminal-cloud-snapshot": ("ac-c", "before"),
        "parent-acceptance-unmapped": ("ac-c", "map"),
        "title-not-stable-identity": ("not", "title"),
        "needs-attention-is-not-terminal-success": ("blocker", "do not claim"),
        "meta-reference-not-creation-authority": ("without", "creating"),
        "internal-not-sidebar": ("parent", "evidence"),
        "user-input-not-child-event": ("parent", "reassess", "not"),
        "target-error-not-completion": ("incomplete", "error"),
        "target-error-not-needs-attention": ("incomplete", "error"),
        "unchanged-snapshot-not-progress": ("suppress", "identical", "preserve"),
        "unchanged-wait-cursor-not-preserved": ("preserve", "cursor"),
    }.get(reason, ())


def _terminal_claim_passes(case, assertion_id, reason):
    statement = _record_groups(case)[assertion_id].get("statement", "").lower()
    signals = _terminal_required_signals(reason)
    return bool(signals) and all(signal in statement for signal in signals)


def _terminal_claim_failure_reason(case, statement):
    statement = statement.lower()
    if "coordinated completion fulfilled" in statement:
        return "queued-coordination-not-fulfilled"
    if "complete after" in statement:
        return (
            "nonterminal-cloud-snapshot"
            if case.get("id") == "bounded-ready-cloud-supported"
            else "nonterminal-snapshot-not-complete"
        )
    if "return ownership immediately" in statement:
        return "explicit-delegation-default-not-coordinated"
    if "broader release-readiness objective is complete" in statement:
        return "child-slice-cannot-complete-parent"
    if _asserted_phrase(statement, "heartbeat") or _asserted_phrase(statement, "pulse"):
        return "scheduled-heartbeat-not-event-callback"
    if "desktop notification" in statement:
        return "human-notification-not-agent-wakeup"
    if "automatically resume" in statement:
        return "no-native-parent-auto-resume"
    if "child reports complete" in statement:
        return "parent-acceptance-unmapped"
    if _asserted_phrase(statement, "matching its title") or _asserted_phrase(
        statement, "select the possible task by title"
    ):
        return "title-not-stable-identity"
    if "claim parent completion from the needs-attention" in statement:
        return "needs-attention-is-not-terminal-success"
    if "create a new task" in statement:
        return "meta-reference-not-creation-authority"
    if "sidebar task" in statement:
        return "internal-not-sidebar"
    if "child completion event" in statement:
        return "user-input-not-child-event"
    if "claim parent completion and omit the target error" in statement:
        return "target-error-not-completion"
    if "child needs-attention event" in statement:
        return "target-error-not-needs-attention"
    if "new child progress" in statement:
        return "unchanged-snapshot-not-progress"
    if "discard the cur-1 cursor" in statement:
        return "unchanged-wait-cursor-not-preserved"
    return None


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
    if _terminal_claim_failure_reason(case, statement) != reason:
        return False
    if reason == "title-not-stable-identity":
        return any(
            _asserted_phrase(statement, phrase)
            for phrase in ("matching its title", "by matching the title", "select the possible task by title")
        )
    signals = _terminal_required_signals(reason)
    return bool(signals) and not all(signal in statement for signal in signals)


def _positive_phrase(prompt, phrase):
    start = 0
    while True:
        index = prompt.find(phrase, start)
        if index < 0:
            return False
        prefix = prompt[:index].rsplit(".", 1)[-1]
        if not any(
            marker in prefix
            for marker in ("do not", "don't", "avoid", "refrain", "without", "never", "omit")
        ):
            return True
        start = index + len(phrase)


def _asserted_phrase(text, phrase):
    start = 0
    while True:
        index = text.find(phrase, start)
        if index < 0:
            return False
        clause_start = max(
            text.rfind(".", 0, index),
            text.rfind(";", 0, index),
            text.rfind(",", 0, index),
        ) + 1
        clause_end_candidates = [
            end
            for end in (text.find(".", index), text.find(";", index), text.find(",", index))
            if end >= 0
        ]
        clause_end = min(clause_end_candidates, default=len(text))
        before = text[max(clause_start, index - 80) : index]
        after = text[index + len(phrase) : clause_end]
        if not re.search(r"\b(?:not|never|do not|don't|isn't|avoid|refrain)\b", before) and not re.search(
            r"^\s*(?:is|are|was|were|as|should|must)?\s*(?:not|never|isn't)\b", after
        ):
            return True
        start = index + len(phrase)


def _omits_term(prompt, term):
    if term not in prompt:
        return True
    term_pattern = re.escape(term).replace(r"_", r"[_ -]?")
    omission = re.compile(
        rf"\b(?:omit|skip|exclude|without|missing|leave\s+out)\s+(?:the\s+)?{term_pattern}\b"
    )
    for match in omission.finditer(prompt):
        prefix = prompt[max(0, match.start() - 40) : match.start()]
        if not re.search(r"\b(?:do not|don't|never|avoid|refrain)\b", prefix):
            return True
    return False


def _prompt_contract_failure_reason(prompt):
    prompt = prompt.lower()
    if len(prompt.split()) < 8:
        return "execution-contract-incomplete"
    if "private_sentinel_do_not_transfer" in prompt:
        return "prompt-sensitive-data-leak"
    if "durable_body_sentinel_do_not_copy" in prompt:
        return "prompt-duplicates-durable-artifact"
    if any(
        _positive_phrase(prompt, phrase)
        for phrase in ("goal registry", "status file", "phase gates", "cursor ledger")
    ):
        return "one-shot-contract-overbuilt"
    if "without re-reading" in prompt:
        return "mutable-fact-revalidation-missing"
    if re.search(r"\bacceptance[_ -]?(?:map|mapping)\b", prompt) and _omits_term(
        prompt, "acceptance_map"
    ):
        return "canonical-terminal-report-incomplete"
    if "acknowledged" in prompt or "without reporting" in prompt:
        return "attention-acknowledgement-missing"
    if "do not send" in prompt or "only in this local" in prompt:
        return "attached-parent-callback-route-missing"
    if "do not declare" in prompt or "resource claim" in prompt and "integration owner" not in prompt:
        return "writable-resource-claim-missing"
    if "parent" not in prompt:
        return "child-slice-parent-relationship-missing"
    if any(
        _positive_phrase(prompt, phrase)
        for phrase in ("record useful checkpoints", "status=ready", "wait_threads")
    ):
        return "parent-observer-mechanics-in-child-prompt"
    if not all(phrase in prompt for phrase in ("checkpoint", "report", "acceptance")):
        return "attached-reporting-contract-missing"
    if not all(phrase in prompt for phrase in ("resource claim", "integration owner")):
        return "writable-resource-claim-missing"
    return None


def _prompt_contract_fails(prompt, reason):
    return _prompt_contract_failure_reason(prompt) == reason


class DelegateContractCaseTests(unittest.TestCase):
    def test_semantic_negative_oracles_reject_compliant_lexical_decoys(self):
        self.assertFalse(
            _prompt_contract_fails(
                "Audit the source and do not create a goal registry, status file, phase gates, or cursor ledger.",
                "one-shot-contract-overbuilt",
            )
        )
        self.assertFalse(
            _prompt_contract_fails(
                "Audit the source, avoid creating a goal registry, and deliver a one-shot memo.",
                "one-shot-contract-overbuilt",
            )
        )
        self.assertFalse(
            _prompt_contract_fails(
                "At completion, do not omit acceptance_map; include it in the terminal report.",
                "canonical-terminal-report-incomplete",
            )
        )
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        case = next(case for case in payload["cases"] if case["id"] == "indeterminate-create-outcome")
        control = next(control for control in case["negative_controls"] if control["id"] == "nc-title-match")
        decoy = copy.deepcopy(control)
        decoy["mutation"]["value"] = "Never select the possible task by matching its title; use exact native identity."
        self.assertFalse(_terminal_claim_fails(case, decoy))
        heartbeat_case = next(case for case in payload["cases"] if case["id"] == "coordinated-ready-codex")
        heartbeat_control = next(
            control for control in heartbeat_case["negative_controls"] if control["id"] == "nc-heartbeat-callback"
        )
        heartbeat_decoy = copy.deepcopy(heartbeat_control)
        heartbeat_decoy["mutation"]["value"] = (
            "A scheduled heartbeat is not a child-completion callback; wait for the observed child result."
        )
        self.assertFalse(_terminal_claim_fails(heartbeat_case, heartbeat_decoy))
        heartbeat_decoy["mutation"]["value"] = (
            "A scheduled pulse isn't a child-completion callback; wait for the observed child result."
        )
        self.assertFalse(_terminal_claim_fails(heartbeat_case, heartbeat_decoy))
        heartbeat_decoy["mutation"]["value"] = (
            "Schedule a heartbeat as the completion callback instead of waiting for the observed child result."
        )
        self.assertTrue(_terminal_claim_fails(heartbeat_case, heartbeat_decoy))
        self.assertTrue(
            _prompt_contract_fails(
                "Complete the objective, leave out the acceptance map, and deliver the report.",
                "canonical-terminal-report-incomplete",
            )
        )
        self.assertTrue(
            _prompt_contract_fails(
                "Complete the objective, exclude the acceptance mapping, and deliver the report.",
                "canonical-terminal-report-incomplete",
            )
        )
        self.assertTrue(
            _prompt_contract_fails(
                "Complete the objective, skip acceptance_map, and deliver the report.",
                "canonical-terminal-report-incomplete",
            )
        )
        evidence_case = next(case for case in payload["cases"] if case["id"] == "explicit-uncommitted-state")
        evidence = next(item for item in evidence_case["capability_evidence"] if item["id"] == "ce-state-authority")
        records = _record_groups(evidence_case)
        forged = copy.deepcopy(evidence)
        forged["premises"][0]["path"] = "/event/payload/request"
        self.assertFalse(_evidence_predicate_valid(evidence_case, records, forged))
        unsupported = copy.deepcopy(evidence)
        unsupported["derivation"]["operator"] = "unknown-operator"
        self.assertFalse(_evidence_predicate_valid(evidence_case, records, unsupported))
        observation_case = next(
            case for case in payload["observation_variants"] if case["id"] == "wait-interrupted-by-new-user-input"
        )
        inherited_trace = _baseline_trace(observation_case, {
            **{item["id"]: item for item in payload["cases"]},
            **{item["id"]: item for item in payload["observation_variants"]},
        })
        reversed_trace = [inherited_trace[-1], *inherited_trace[:-1]]
        self.assertFalse(
            _partial_order_passes(
                observation_case,
                reversed_trace,
                {
                    **{item["id"]: item for item in payload["cases"]},
                    **{item["id"]: item for item in payload["observation_variants"]},
                },
            )
        )

    def test_negative_controls_are_complete_executable_mutation_records(self):
        payload = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())
        operations = {"replace", "replace_call_arg", "insert_call", "remove", "replace_terminal_claim"}
        catalog_sections = ("cases", "observation_variants", "prompt_contract_variants")
        cases_by_id = {case["id"]: case for case in payload["cases"]}
        cases_by_id.update({case["id"]: case for case in payload["observation_variants"]})
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
                    self.assertEqual(
                        _REASON_CRITERION.get(expected_failure["reason_code"]),
                        expected_failure["criterion_id"],
                        control.get("id"),
                    )
                    baseline = known_records[target["id"]]
                    mutated = apply_catalog_mutation(baseline, mutation)
                    self.assertNotEqual(mutated, baseline, control.get("id"))
                    if target["namespace"] == "candidate_trace":
                        kind, named_assertion = _assertion_by_id(case, expected_failure["assertion_id"])
                        self.assertIsNotNone(named_assertion, control.get("id"))
                        baseline_trace = _baseline_trace(case, cases_by_id)
                        self.assertTrue(
                            _operation_assertion_passes(kind, named_assertion, baseline_trace),
                            f"baseline does not satisfy {expected_failure['assertion_id']}: {control['id']}",
                        )
                        self.assertTrue(_partial_order_passes(case, baseline_trace, cases_by_id), control.get("id"))
                        mutated_trace = _mutated_trace(case, control, cases_by_id)
                        self.assertFalse(
                            _operation_assertion_passes(kind, named_assertion, mutated_trace),
                            control.get("id"),
                        )
                        self.assertTrue(_partial_order_passes(case, mutated_trace, cases_by_id), control.get("id"))
                    elif target["namespace"] in {"fixture", "capability_evidence"}:
                        named_id = expected_failure["assertion_id"]
                        named_evidence = next(
                            (evidence for evidence in case.get("capability_evidence", []) if evidence["id"] == named_id),
                            None,
                        )
                        if named_evidence is not None:
                            baseline_records = _record_groups(case)
                            mutated_records = _mutated_records(case, control)
                            self.assertTrue(
                                _evidence_predicate_valid(case, baseline_records, named_evidence),
                                control.get("id"),
                            )
                            self.assertFalse(
                                _evidence_predicate_valid(case, mutated_records, mutated_records[named_id]),
                                control.get("id"),
                            )
                        else:
                            kind, named_assertion = _assertion_by_id(case, named_id)
                            self.assertIsNotNone(named_assertion, control.get("id"))
                            baseline_trace = _baseline_trace(case, cases_by_id)
                            self.assertTrue(
                                _operation_assertion_passes(kind, named_assertion, baseline_trace),
                                control.get("id"),
                            )
                            baseline_records = _record_groups(case)
                            mutated_records = _mutated_records(case, control)
                            self.assertTrue(
                                _operation_admission_passes(
                                    case, named_id, baseline_records, cases_by_id
                                ),
                                control.get("id"),
                            )
                            self.assertFalse(
                                _operation_admission_passes(
                                    case, named_id, mutated_records, cases_by_id
                                ),
                                control.get("id"),
                            )
                        self.assertTrue(_dependent_evidence_fails(case, control), control.get("id"))
                    elif target["namespace"] == "candidate_terminal":
                        self.assertEqual(
                            target["id"], expected_failure["assertion_id"], control.get("id")
                        )
                        self.assertTrue(
                            _terminal_claim_passes(case, target["id"], expected_failure["reason_code"]),
                            control.get("id"),
                        )
                        self.assertTrue(_terminal_claim_fails(case, control), control.get("id"))
                    else:
                        self.fail(f"unhandled mutation namespace: {target['namespace']}")
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
            self.assertEqual(case["criterion_id"], expected_failure["criterion_id"], case["id"])
            self.assertEqual(
                semantic_assertions[expected_failure["assertion_id"]]["criterion_id"],
                expected_failure["criterion_id"],
                case["id"],
            )
            self.assertTrue(expected_failure.get("reason_code"), case["id"])
            prompt = mutation["value"].get("prompt", "")
            base_case = cases_by_id[case["base_case_id"]]
            base_create = _required_assertion(base_case, target["id"], cases_by_id)
            self.assertIsNotNone(base_create, case["id"])
            candidate_call = {
                "tool": "create_thread",
                "args": copy.deepcopy(mutation["value"]),
            }
            self.assertEqual(candidate_call["args"].get("target"), base_create["args_match"]["value"].get("target"), case["id"])
            self.assertEqual(candidate_call["args"].get("prompt"), prompt, case["id"])
            baseline_prompt = case.get("baseline_prompt", "")
            self.assertTrue(baseline_prompt.strip(), case["id"])
            self.assertIsNone(_prompt_contract_failure_reason(baseline_prompt), case["id"])
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
