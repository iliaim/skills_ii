import importlib.util
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = SKILL_ROOT / "scripts" / "run_behavioral_evals.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_behavioral_evals", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def grade(eval_id, facts, *, decision="inspect", planned_calls=None):
    runner = load_runner()
    scenario = runner.scenario_by_id(
        runner.load_scenarios(SKILL_ROOT / "evals" / "scenarios.json"), eval_id
    )
    return runner.grade_result(
        scenario,
        {
            "eval_id": eval_id,
            "decision": decision,
            "planned_calls": planned_calls or [],
            "facts": facts,
            "explanation": "Message disposition evidence was classified for the matching action revision.",
        },
    )


def test_message_ack_scenarios_are_cataloged_and_use_the_contract_reference():
    runner = load_runner()
    catalog = runner.load_catalog(SKILL_ROOT / "evals" / "evals.json")
    scenarios = runner.load_scenarios(SKILL_ROOT / "evals" / "scenarios.json")
    new_ids = {45, 46, 47, 48, 49, 50}

    assert new_ids <= {entry["id"] for entry in catalog}
    for eval_id in new_ids:
        scenario = runner.scenario_by_id(scenarios, eval_id)
        assert "references/message-contract.md" in scenario["references"]


def test_observed_label_without_receiver_disposition_stays_pending():
    correct = grade(45, {"acceptance_state": "pending", "progress_changed": False, "routeability": "available", "lifecycle_mutation_authorized": False})
    wrong_replay_and_claim = grade(
        45,
        {"acceptance_state": "accepted", "progress_changed": True, "routeability": "available", "lifecycle_mutation_authorized": False},
        planned_calls=[{"tool": "codex_queue", "arguments": {"threadId": "task-45", "prompt": "replay"}}],
    )

    assert correct["passed"], correct["failures"]
    assert not wrong_replay_and_claim["passed"]
    assert any("acceptance_state" in failure or "progress_changed" in failure for failure in wrong_replay_and_claim["failures"])
    assert any("codex_queue" in failure for failure in wrong_replay_and_claim["failures"])


def test_held_action_preserves_pending_acceptance_and_blocks_transfer_or_retry():
    correct = grade(46, {"acceptance_state": "pending", "progress_changed": False, "lifecycle_mutation_authorized": False})
    wrong_transfer = grade(
        46,
        {"acceptance_state": "accepted", "progress_changed": True, "lifecycle_mutation_authorized": True},
        planned_calls=[{"tool": "handoff_thread", "arguments": {"threadId": "task-46"}}],
    )

    assert correct["passed"], correct["failures"]
    assert not wrong_transfer["passed"]
    assert any("acceptance_state" in failure for failure in wrong_transfer["failures"])
    assert any("handoff_thread" in failure for failure in wrong_transfer["failures"])


def test_refusal_rejects_commitment_without_erasing_routeability_or_retrying():
    correct = grade(47, {"acceptance_state": "rejected", "routeability": "available", "lifecycle_mutation_authorized": False})
    wrong_retry = grade(
        47,
        {"acceptance_state": "pending", "routeability": "unavailable", "lifecycle_mutation_authorized": False},
        decision="contact-unavailable",
        planned_calls=[{"tool": "send_message_to_thread", "arguments": {"threadId": "task-47", "prompt": "retry"}}],
    )

    assert correct["passed"], correct["failures"]
    assert not wrong_retry["passed"]
    assert any("acceptance_state" in failure or "routeability" in failure for failure in wrong_retry["failures"])
    assert any("send_message_to_thread" in failure for failure in wrong_retry["failures"])


def test_generic_acknowledgement_and_unrelated_turn_are_not_action_progress():
    correct = grade(48, {"acceptance_state": "pending", "progress_changed": False, "lifecycle_mutation_authorized": False})
    wrong_ack = grade(48, {"acceptance_state": "accepted", "progress_changed": True, "lifecycle_mutation_authorized": False})

    assert correct["passed"], correct["failures"]
    assert not wrong_ack["passed"]
    assert any("acceptance_state" in failure or "progress_changed" in failure for failure in wrong_ack["failures"])


def test_action_bound_operation_supports_execution_progress_but_not_completion():
    correct = grade(
        49,
        {"acceptance_state": "accepted", "progress_changed": True, "progress_kind": "evidence_added", "evidence_revision_bound": True, "completion_verified": False, "routeability": "available", "lifecycle_mutation_authorized": False},
    )
    wrong_stale_evidence = grade(
        49,
        {"acceptance_state": "accepted", "progress_changed": False, "progress_kind": "no_change", "evidence_revision_bound": False, "completion_verified": False, "routeability": "available", "lifecycle_mutation_authorized": False},
    )
    wrong_completion_claim = grade(
        49,
        {"acceptance_state": "accepted", "progress_changed": True, "progress_kind": "evidence_added", "evidence_revision_bound": True, "completion_verified": True, "routeability": "available", "lifecycle_mutation_authorized": False},
    )
    missing_completion_fact = grade(
        49,
        {"acceptance_state": "accepted", "progress_changed": True, "progress_kind": "evidence_added", "evidence_revision_bound": True, "routeability": "available", "lifecycle_mutation_authorized": False},
    )

    assert correct["passed"], correct["failures"]
    assert not wrong_stale_evidence["passed"]
    assert any("progress_changed" in failure or "evidence_revision_bound" in failure for failure in wrong_stale_evidence["failures"])
    assert not wrong_completion_claim["passed"]
    assert any("completion_verified" in failure for failure in wrong_completion_claim["failures"])
    assert not missing_completion_fact["passed"]
    assert any("completion_verified" in failure for failure in missing_completion_fact["failures"])


def test_superseded_result_cannot_acknowledge_or_verify_current_revision():
    correct = grade(50, {"acceptance_state": "pending", "progress_changed": False, "evidence_revision_bound": False, "lifecycle_mutation_authorized": False})
    wrong_revision = grade(50, {"acceptance_state": "accepted", "progress_changed": True, "evidence_revision_bound": True, "lifecycle_mutation_authorized": False})
    assert correct["passed"], correct["failures"]
    assert not wrong_revision["passed"]
    assert any("evidence_revision_bound" in failure for failure in wrong_revision["failures"])


def test_endpoint_cases_reject_role_only_wrong_host_fabrication_and_duplicate_sends():
    runner = load_runner()
    scenarios = runner.load_scenarios(SKILL_ROOT / "evals" / "scenarios.json")
    for eval_id in (51, 52, 53):
        scenario = runner.scenario_by_id(scenarios, eval_id)
        fixture = scenario["fixture"]
        recipient = fixture["recipient_native_context"]
        calls = [
            {"tool": "send_message_to_thread", "arguments": {
                "threadId": recipient["task_id"], "hostId": recipient["host_id"],
                "prompt": fixture["approved_handoff_message"],
            }},
            {"tool": "read_thread", "arguments": {
                "threadId": recipient["task_id"], "hostId": recipient["host_id"],
            }},
        ]
        facts = scenario["checks"]["fact_equals"]
        correct = grade(eval_id, facts, decision="contact", planned_calls=calls)
        assert correct["passed"], correct["failures"]

        # Same target and body intent cannot compensate for an ambiguous sender.
        ambiguous = [dict(call, arguments=dict(call["arguments"])) for call in calls]
        ambiguous[0]["arguments"]["prompt"] = fixture["legacy_draft"]
        assert not grade(eval_id, facts, decision="contact", planned_calls=ambiguous)["passed"]
        assert not grade(eval_id, facts, decision="contact", planned_calls=calls + calls[:1])["passed"]

        if eval_id == 52:
            wrong_host = [dict(call, arguments=dict(call["arguments"])) for call in calls]
            wrong_host[0]["arguments"]["hostId"] = "host-a"
            assert not grade(eval_id, facts, decision="contact", planned_calls=wrong_host)["passed"]
        if eval_id == 53:
            invented = [dict(call, arguments=dict(call["arguments"])) for call in calls]
            invented[0]["arguments"]["prompt"] = fixture["approved_handoff_message"].replace(
                "task ID unavailable (native context does not expose it)",
                "task ID 10000000-0000-4000-8000-000000000053",
            )
            assert not grade(eval_id, facts, decision="contact", planned_calls=invented)["passed"]


def test_reply_observation_reads_recipient_record_not_sender_return_address():
    recipient_id = "20000000-0000-4000-8000-000000000054"
    sender_id = "10000000-0000-4000-8000-000000000054"
    facts = {"identity_correlated": True, "routeability": "available", "lifecycle_mutation_authorized": False}
    correct_call = {"tool": "read_thread", "arguments": {"threadId": recipient_id, "hostId": "host-b"}}
    correct = grade(54, facts, planned_calls=[correct_call])
    assert correct["passed"], correct["failures"]

    for task_id, host_id in [(sender_id, "host-a"), (sender_id, "host-b"), (recipient_id, "host-a"), (recipient_id, "host-b (recipient)")]:
        wrong = grade(54, facts, planned_calls=[
            {"tool": "read_thread", "arguments": {"threadId": task_id, "hostId": host_id}},
        ])
        assert not wrong["passed"]
        assert any("required call read_thread" in failure for failure in wrong["failures"])

    callback = {"tool": "send_message_to_thread", "arguments": {"threadId": sender_id, "hostId": "host-a", "prompt": "reply"}}
    assert not grade(54, facts, planned_calls=[correct_call, callback])["passed"]

    for tool in ("set_thread_archived", "clean", "delete", "reset", "fork_thread"):
        mutation = {"tool": tool, "arguments": {"threadId": recipient_id}}
        result = grade(54, facts, planned_calls=[correct_call, mutation])
        assert not result["passed"], tool
        assert any(tool in failure for failure in result["failures"])
