import unittest


import hashlib
import json
from pathlib import Path
from uuid import UUID


SKILL_ROOT = Path(__file__).resolve().parents[1]


CHECKPOINT_FIELDS = {
    "child_id",
    "report_revision",
    "report_identity_or_digest",
    "observed_at",
    "execution_state",
    "task_liveness",
    "progress_kind",
    "evidence_refs",
    "blocker_or_decision",
    "next_gate",
}
TERMINAL_FIELDS = {
    "outcome",
    "delivered_artifact",
    "acceptance_map",
    "checks_and_observed_results",
    "residual_risks",
    "unmet_requirements",
    "availability",
    "report_revision",
    "report_identity_or_digest",
    "supersedes",
}
ALLOWED_PROGRESS_KINDS = {
    "phase_change", "evidence_added", "blocker_opened", "blocker_cleared",
    "attention_acknowledged", "verification_complete", "no_change",
}


def canonical_report_payload(report):
    return json.dumps(
        {key: value for key, value in report.items() if key != "report_identity_or_digest"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def report_digest(report):
    return "sha256:" + hashlib.sha256(canonical_report_payload(report)).hexdigest()


def report_identity_is_backed(report, observed_native_events=()):
    identity = report.get("report_identity_or_digest")
    if not isinstance(identity, str):
        return False
    if identity.startswith(("turn:", "event:")):
        kind, _, event_id = identity.partition(":")
        return bool(event_id) and any(
            event.get("kind") == kind
            and event.get("id") == event_id
            and event.get("report_revision") == report.get("report_revision")
            and event.get("child_id") == report.get("child_id")
            for event in observed_native_events
        )
    return identity == report_digest(report)


def attached_report_admissible(report, terminal=False, observed_native_events=()):
    required = TERMINAL_FIELDS if terminal else CHECKPOINT_FIELDS
    return (
        required.issubset(report)
        and isinstance(report["report_revision"], int)
        and report_identity_is_backed(report, observed_native_events)
        and (terminal or bool(report["child_id"]))
        and (terminal or (isinstance(report["evidence_refs"], list) and bool(report["evidence_refs"])))
        and (
            terminal
            or all(bool(report[field]) for field in (
                "observed_at", "execution_state", "task_liveness", "progress_kind", "next_gate"
            ))
            and report["progress_kind"] in ALLOWED_PROGRESS_KINDS
        )
        and (
            not terminal
            or (
                bool(report["outcome"])
                and isinstance(report["acceptance_map"], dict)
                and isinstance(report["checks_and_observed_results"], list)
                and isinstance(report["residual_risks"], list)
                and isinstance(report["unmet_requirements"], list)
                and bool(report["availability"])
            )
        )
    )


def callback_resolution_is_operable(pending, callback_thread_id, native_read):
    try:
        UUID(callback_thread_id)
    except (TypeError, ValueError, AttributeError):
        return False
    return bool(
        pending.get("clientThreadId")
        and native_read
        and native_read.get("threadId") == callback_thread_id
        and native_read.get("requested_hostId") == pending.get("hostId")
        and all(
            pending.get(field) is None
            or native_read.get(field) is None
            or native_read.get(field) == pending.get(field)
            for field in ("backing_kind", "project_id", "worktree_path")
        )
    )


def runtime_resolution_is_operable(pending, resolution, native_read):
    if not isinstance(resolution, dict) or resolution.get("status") != "ready":
        return False
    return bool(
        resolution.get("hostId") == pending.get("hostId")
        and callback_resolution_is_operable(
            pending,
            resolution.get("threadId"),
            native_read,
        )
    )


def attached_callbacks_reach_parent(parent_task_id, route, first_callback, terminal_callback):
    if not parent_task_id or route != "send_message_to_thread" or not first_callback or not terminal_callback:
        return False
    callbacks = (first_callback, terminal_callback)
    if any(
        callback.get("target_task_id") != parent_task_id or callback.get("route") != route
        for callback in callbacks
    ):
        return False
    return (
        attached_report_admissible(
            first_callback["report"],
            observed_native_events=first_callback.get("observed_native_events", ()),
        )
        and attached_report_admissible(terminal_callback["report"], terminal=True)
    )


class DelegateProtocolTransitionTests(unittest.TestCase):
    def test_attached_checkpoint_and_terminal_reports_require_immutable_identity(self):
        checkpoint = {
            "child_id": "child-1",
            "report_revision": 4,
            "report_identity_or_digest": "turn:42",
            "observed_at": "2026-09-15T10:00:00Z",
            "execution_state": "running",
            "task_liveness": "live",
            "progress_kind": "verification_complete",
            "evidence_refs": ["turn:42"],
            "blocker_or_decision": None,
            "next_gate": "parent-review",
        }
        terminal = {
            "outcome": "complete",
            "delivered_artifact": {"path": "report.md", "revision": "git:post-image"},
            "acceptance_map": {"criterion-a": "accepted"},
            "checks_and_observed_results": ["test-a: pass"],
            "residual_risks": [],
            "unmet_requirements": [],
            "availability": "available",
            "report_revision": 5,
            "report_identity_or_digest": None,
            "supersedes": 4,
        }
        terminal["report_identity_or_digest"] = report_digest(terminal)
        checkpoint_events = [{"kind": "turn", "id": "42", "report_revision": 4, "child_id": "child-1"}]
        self.assertFalse(attached_report_admissible(checkpoint))
        self.assertTrue(attached_report_admissible(checkpoint, observed_native_events=checkpoint_events))
        self.assertTrue(attached_report_admissible(terminal, terminal=True))
        self.assertFalse(attached_report_admissible(dict(checkpoint, report_identity_or_digest=None)))
        self.assertFalse(attached_report_admissible(dict(checkpoint, report_identity_or_digest="reported-complete")))
        self.assertFalse(attached_report_admissible(dict(
            checkpoint,
            report_identity_or_digest="sha256:" + "a" * 64,
        ), observed_native_events=checkpoint_events))
        self.assertFalse(attached_report_admissible(dict(
            checkpoint,
            report_identity_or_digest="turn:unobserved",
        ), observed_native_events=checkpoint_events))
        self.assertFalse(attached_report_admissible(dict(checkpoint, progress_kind=None)))
        self.assertFalse(attached_report_admissible(dict(terminal, acceptance_map=None), terminal=True))

    def test_each_normative_report_field_is_required_by_the_oracle(self):
        checkpoint = {
            "child_id": "child-1",
            "report_revision": 4,
            "report_identity_or_digest": "turn:42",
            "observed_at": "2026-09-15T10:00:00Z",
            "execution_state": "running",
            "task_liveness": "live",
            "progress_kind": "evidence_added",
            "evidence_refs": ["turn:42"],
            "blocker_or_decision": None,
            "next_gate": "parent-review",
        }
        terminal = {
            "outcome": "complete",
            "delivered_artifact": None,
            "acceptance_map": {},
            "checks_and_observed_results": [],
            "residual_risks": [],
            "unmet_requirements": [],
            "availability": "not_available",
            "report_revision": 5,
            "report_identity_or_digest": "turn:43",
            "supersedes": 4,
        }
        for field in CHECKPOINT_FIELDS:
            with self.subTest(report="checkpoint", field=field):
                self.assertFalse(attached_report_admissible({k: v for k, v in checkpoint.items() if k != field}))
        for field in TERMINAL_FIELDS:
            with self.subTest(report="terminal", field=field):
                self.assertFalse(attached_report_admissible({k: v for k, v in terminal.items() if k != field}, terminal=True))

    def test_logical_revision_reuse_cannot_replace_report_identity(self):
        report = {
            "child_id": "child-1",
            "report_revision": 4,
            "report_identity_or_digest": None,
            "observed_at": "2026-09-15T10:00:00Z",
            "execution_state": "running",
            "task_liveness": "live",
            "progress_kind": "evidence_added",
            "evidence_refs": ["turn:old"],
            "blocker_or_decision": None,
            "next_gate": "parent-review",
        }
        self.assertFalse(attached_report_admissible(report))

    def test_independent_create_only_task_does_not_require_attached_reporting(self):
        create_only = {"mode": "independent-create-only", "creation_owner": "delegate-to-thread"}
        self.assertEqual(create_only["creation_owner"], "delegate-to-thread")
        self.assertNotIn("report_revision", create_only)

    def test_callback_real_id_is_confirmed_directly_without_listing_or_retry(self):
        pending = {
            "clientThreadId": "setup-37",
            "hostId": "local",
            "backing_kind": "codex",
            "project_id": "skills",
            "worktree_path": "/worktrees/skills-child",
        }
        callback_thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473413"
        native_read = {
            "threadId": callback_thread_id,
            "requested_hostId": "local",
            "backing_kind": "codex",
        }
        self.assertTrue(callback_resolution_is_operable(pending, callback_thread_id, native_read))
        self.assertFalse(callback_resolution_is_operable(pending, "setup-37", native_read))
        self.assertFalse(callback_resolution_is_operable(pending, callback_thread_id, None))
        self.assertFalse(callback_resolution_is_operable(
            pending,
            callback_thread_id,
            dict(native_read, backing_kind="chatgpt"),
        ))
        self.assertFalse(callback_resolution_is_operable(
            pending,
            callback_thread_id,
            dict(native_read, project_id="other-project"),
        ))

    def test_runtime_resolution_requires_ready_status_host_and_native_confirmation(self):
        pending = {
            "clientThreadId": "setup-38",
            "hostId": "local",
            "backing_kind": "codex",
        }
        thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473414"
        native_read = {
            "threadId": thread_id,
            "requested_hostId": "local",
            "backing_kind": "codex",
        }
        ready = {"status": "ready", "threadId": thread_id, "hostId": "local"}
        self.assertTrue(runtime_resolution_is_operable(pending, ready, native_read))
        for status in ("pending", "failed", "expired"):
            self.assertFalse(runtime_resolution_is_operable(
                pending,
                {"status": status, "code": "setup-state"},
                native_read,
            ))
        self.assertFalse(runtime_resolution_is_operable(
            pending,
            dict(ready, hostId="remote"),
            native_read,
        ))
        self.assertFalse(runtime_resolution_is_operable(
            pending,
            ready,
            dict(native_read, threadId="01a0a4b7-7a3b-70f0-9044-d49469473415"),
        ))

    def test_local_terminal_report_does_not_replace_identity_bearing_parent_callbacks(self):
        parent_task_id = "01a0a74d-parent"
        checkpoint = {
            "child_id": "child-1", "report_revision": 1, "report_identity_or_digest": "turn:1",
            "observed_at": "now", "execution_state": "executing", "task_liveness": "live",
            "progress_kind": "phase_change", "evidence_refs": ["turn:1"], "blocker_or_decision": None,
            "next_gate": "verify",
        }
        terminal = {
            "outcome": "complete", "delivered_artifact": None,
            "acceptance_map": {"criterion-a": "pending"}, "checks_and_observed_results": [],
            "residual_risks": [], "unmet_requirements": [], "availability": "available",
            "report_revision": 2, "report_identity_or_digest": None, "supersedes": 1,
        }
        terminal["report_identity_or_digest"] = report_digest(terminal)
        first_callback = {
            "target_task_id": parent_task_id,
            "route": "send_message_to_thread",
            "report": checkpoint,
            "observed_native_events": [{"kind": "turn", "id": "1", "report_revision": 1, "child_id": "child-1"}],
        }
        terminal_callback = {
            "target_task_id": parent_task_id,
            "route": "send_message_to_thread",
            "report": terminal,
        }
        self.assertTrue(attached_callbacks_reach_parent(
            parent_task_id,
            "send_message_to_thread",
            first_callback,
            terminal_callback,
        ))
        self.assertFalse(attached_callbacks_reach_parent(
            parent_task_id,
            "send_message_to_thread",
            first_callback,
            None,
        ))
        self.assertFalse(attached_callbacks_reach_parent(
            parent_task_id,
            "send_message_to_thread",
            dict(first_callback, target_task_id="other-parent"),
            terminal_callback,
        ))

    def test_adversarial_catalog_cases_execute_against_protocol_oracles(self):
        cases = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())["prompt_contract_variants"]
        adversarial = {
            "attached-reporting-required",
            "attached-terminal-report-missing-acceptance-map",
            "attached-attention-ack-required",
            "attached-local-terminal-without-parent-callback",
            "writable-resource-claim-required",
        }
        catalog_ids = {case["id"] for case in cases if case["id"] in adversarial}
        self.assertEqual(catalog_ids, adversarial)
        by_id = {case["id"]: case for case in cases if case["id"] in adversarial}
        checkpoint = {
            "child_id": "child-1", "report_revision": 1, "report_identity_or_digest": "turn:1",
            "observed_at": "now", "execution_state": "running", "task_liveness": "live",
            "progress_kind": "phase_change", "evidence_refs": ["turn:1"], "blocker_or_decision": None,
            "next_gate": "verify",
        }
        terminal = {
            "outcome": "complete", "delivered_artifact": None, "acceptance_map": {"criterion-a": "pending"},
            "checks_and_observed_results": [], "residual_risks": [], "unmet_requirements": [],
            "availability": "available", "report_revision": 2, "report_identity_or_digest": "turn:2", "supersedes": 1,
        }
        for case_id, case in by_id.items():
            oracle = case.get("protocol_oracle")
            self.assertIsInstance(oracle, dict, case_id)
            if oracle["kind"] == "checkpoint_required":
                self.assertEqual(set(oracle["required_fields"]), CHECKPOINT_FIELDS)
                observed = [{"kind": "turn", "id": "1", "report_revision": 1, "child_id": "child-1"}]
                self.assertTrue(attached_report_admissible(checkpoint, observed_native_events=observed))
            elif oracle["kind"] == "terminal_field_required":
                missing = {k: v for k, v in terminal.items() if k != oracle["missing_field"]}
                self.assertFalse(attached_report_admissible(missing, terminal=True))
            elif oracle["kind"] == "attention_ack_required":
                self.assertFalse(oracle["acknowledged"])
            elif oracle["kind"] == "parent_callback_required":
                self.assertFalse(oracle["terminal_callback_sent"])
                self.assertTrue(oracle["first_checkpoint_identity_bearing"])
            elif oracle["kind"] == "resource_claim_required":
                self.assertEqual(set(oracle["missing_fields"]), {
                    "resource_id", "destination_fingerprint", "paths_or_scope", "access_mode", "owner",
                    "base_revision", "claim_interval", "conflict_policy", "integration_owner",
                })
            else:
                self.fail(f"unhandled protocol oracle kind: {oracle['kind']}")


if __name__ == "__main__":
    unittest.main()
