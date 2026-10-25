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
        {"acceptance_state": "accepted", "progress_changed": True, "progress_kind": "evidence_added", "evidence_revision_bound": True, "routeability": "available", "lifecycle_mutation_authorized": False},
    )
    wrong_stale_evidence = grade(
        49,
        {"acceptance_state": "accepted", "progress_changed": False, "progress_kind": "no_change", "evidence_revision_bound": False, "routeability": "available", "lifecycle_mutation_authorized": False},
    )

    assert correct["passed"], correct["failures"]
    assert not wrong_stale_evidence["passed"]
    assert any("progress_changed" in failure or "evidence_revision_bound" in failure for failure in wrong_stale_evidence["failures"])


def test_superseded_result_cannot_acknowledge_or_verify_current_revision():
    correct = grade(50, {"acceptance_state": "pending", "progress_changed": False, "evidence_revision_bound": False, "lifecycle_mutation_authorized": False})
    wrong_revision = grade(50, {"acceptance_state": "accepted", "progress_changed": True, "evidence_revision_bound": True, "lifecycle_mutation_authorized": False})
    assert correct["passed"], correct["failures"]
    assert not wrong_revision["passed"]
    assert any("evidence_revision_bound" in failure for failure in wrong_revision["failures"])
