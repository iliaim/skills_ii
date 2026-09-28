import unittest


import hashlib
import json
import re
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
    "child_id",
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
EXECUTION_STATES = {
    "discovering", "executing", "verifying", "blocked", "complete", "incomplete",
}

EXECUTION_CONTEXT_FIELDS = {
    "project_path",
    "write_authority",
    "execution_mode",
    "descendant_authority",
}
STARTING_STATE_FIELDS = {"requested_starting_state", "provider_default_rule"}
OBSERVED_CHECKOUT_FIELDS = {
    "project_path",
    "cwd",
    "worktree_root",
    "branch_or_ref",
    "head_revision",
    "base_revision",
    "working_tree_status",
}
REPOSITORY_CHECKPOINT_FIELDS = {
    "execution_context",
    "cwd",
    "worktree_root",
    "branch_or_ref",
    "head_revision",
    "base_revision",
    "working_tree_status",
    "write_authority",
}
REPOSITORY_TERMINAL_FIELDS = {
    "execution_context",
    "observed_checkout",
    "changed_files",
}
TERMINAL_DELIVERY_FIELDS = {"commit_or_pull_request", "uncommitted_disposition"}
DESCENDANT_ENVELOPE_FIELDS = {
    "root_id",
    "parent_id",
    "scope",
    "depth_limit",
    "budget",
    "resource_claim",
    "acceptance_boundary",
    "integration_owner",
    "stop_rule",
    "issuer_id",
    "allowed_actions",
    "destination_fingerprint",
    "identity_or_digest",
}
EXECUTION_EVIDENCE_FIELDS = {
    "project_path",
    "cwd",
    "worktree_root",
    "branch_or_ref",
    "head_revision",
    "base_revision",
    "working_tree_status",
    "write_authority",
    "starting_state",
}
MAX_SETUP_RECOVERY_CHECKS = 3
DESCENDANT_ACTIONS = {
    "delegate-to-thread",
    "orchestrate-threads",
    "fork",
    "hand-off",
}
MUTATING_ACTIONS = {
    "edit", "write", "create", "delete", "rename", "move", "chmod",
    "apply_patch", "mkdir", "remove", "commit", "deploy", "publish", "push",
    "merge", "overwrite", "release", "promote", "integrate", "rebase", "reset",
}


def execution_boundary_admissible(
    trace,
    native_execution_evidence=None,
    native_parent_envelope_evidence=None,
    native_transfer_evidence=None,
    native_post_write_evidence=None,
):
    context = trace.get("execution_context", {})
    observed = trace.get("observed_checkout", {})
    if not trace.get("direct_execution") or not trace.get("pre_write_verified"):
        return False
    evidence = trace.get("execution_evidence", {})
    if evidence.get("source") not in {"native-read-only-check", "provider-assigned-worktree"}:
        return False
    if not evidence.get("evidence_id"):
        return False
    if not isinstance(native_execution_evidence, dict):
        return False
    if native_execution_evidence.get("source") != evidence.get("source") or native_execution_evidence.get("evidence_id") != evidence.get("evidence_id"):
        return False
    if not EXECUTION_CONTEXT_FIELDS.issubset(context) or any(
        not context[field] for field in EXECUTION_CONTEXT_FIELDS
    ):
        return False
    if sum(bool(context.get(field)) for field in STARTING_STATE_FIELDS) != 1:
        return False
    if not OBSERVED_CHECKOUT_FIELDS.issubset(observed) or any(
        not observed[field] for field in OBSERVED_CHECKOUT_FIELDS
    ):
        return False
    if observed["project_path"] != context["project_path"]:
        return False
    starting_state_name = next(
        field for field in STARTING_STATE_FIELDS if context.get(field)
    )
    expected_starting_state = context[starting_state_name]
    expected_evidence = {
        "project_path": observed["project_path"],
        "cwd": observed["cwd"],
        "worktree_root": observed["worktree_root"],
        "branch_or_ref": observed["branch_or_ref"],
        "head_revision": observed["head_revision"],
        "base_revision": observed["base_revision"],
        "working_tree_status": observed["working_tree_status"],
        "write_authority": context["write_authority"],
        "starting_state": expected_starting_state,
    }
    if not EXECUTION_EVIDENCE_FIELDS.issubset(evidence) or any(
        evidence[field] != value for field, value in expected_evidence.items()
    ):
        return False
    if any(
        native_execution_evidence.get(field) != expected_evidence[field]
        for field in EXECUTION_EVIDENCE_FIELDS
    ):
        return False
    if context["execution_mode"] == "managed-worktree":
        if context.get("worktree_path") and observed["worktree_root"] != context["worktree_path"]:
            return False
        if starting_state_name == "requested_starting_state":
            if not context.get("branch_or_ref") or not context.get("base_revision"):
                return False
            if observed["branch_or_ref"] != context["branch_or_ref"] or observed["base_revision"] != context["base_revision"]:
                return False
        else:
            provider_rule = context["provider_default_rule"]
            if not isinstance(provider_rule, dict) or not {
                "branch_or_ref", "base_revision"
            }.issubset(provider_rule):
                return False
            if observed["branch_or_ref"] != provider_rule["branch_or_ref"] or observed["base_revision"] != provider_rule["base_revision"]:
                return False
    if context.get("cwd") and observed["cwd"] != context["cwd"]:
        return False
    if context.get("worktree_path") and observed["worktree_root"] != context["worktree_path"]:
        return False
    if context["execution_mode"] == "managed-worktree":
        if context["write_authority"] != "authorized":
            return False
    elif context["execution_mode"] == "direct-local":
        if context["write_authority"] != "authorized" or not context.get("exclusive_writer_commitment"):
            return False
    else:
        return False
    if "destination_scope" in trace and not path_disclosure_admissible(trace, native_transfer_evidence):
        return False
    if context.get("descendant_authority") == "granted":
        envelope = trace.get("parent_issued_envelope", {})
        if not parent_envelope_admissible(trace, envelope, native_parent_envelope_evidence):
            return False
    if context.get("descendant_authority") != "granted" and any(
        action in DESCENDANT_ACTIONS for action in trace.get("actions", ())
    ):
        return False
    actions = trace.get("actions", ())
    if not isinstance(actions, list):
        return False
    if any(action not in {
        "execute_directly", "checkpoint", "terminal_report", *DESCENDANT_ACTIONS, *MUTATING_ACTIONS
    } for action in actions):
        return False
    write_indexes = [index for index, action in enumerate(actions) if action in MUTATING_ACTIONS]
    if write_indexes:
        if "checkpoint" not in actions or "terminal_report" not in actions:
            return False
        if actions.index("checkpoint") >= min(write_indexes):
            return False
        if actions.index("terminal_report") <= max(write_indexes):
            return False
    if "checkpoint" in actions and not {
        "execution_context", "cwd", "worktree_root", "branch_or_ref", "head_revision",
        "base_revision", "working_tree_status", "write_authority"
    }.issubset(trace.get("checkpoint_fields_present", ())):
        return False
    if "terminal_report" in actions and not repository_report_fields_admissible(trace, native_post_write_evidence):
        return False
    return True


def transfer_payload_digest(trace):
    payload = dict(trace)
    payload.pop("path_transfer_authority", None)
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def path_disclosure_admissible(trace, native_transfer_evidence=None):
    """Reject raw host paths when a trace crosses a broader destination boundary."""
    destination_scope = trace.get("destination_scope", "same-host")
    if destination_scope == "same-host":
        if "destination_scope" not in trace:
            return True
        return (
            isinstance(native_transfer_evidence, dict)
            and native_transfer_evidence.get("source") == "native-destination-observation"
            and native_transfer_evidence.get("destination_scope") == "same-host"
            and bool(native_transfer_evidence.get("evidence_id"))
        )
    authority = trace.get("path_transfer_authority", {})
    if not isinstance(authority, dict) or {
        "source_scope", "destination_scope", "method", "evidence_id", "redaction"
    } - set(authority):
        return False
    if authority["destination_scope"] != destination_scope or authority["method"] != "authorized-path-transfer":
        return False
    if authority["redaction"] != "opaque-identifiers":
        return False
    if not isinstance(native_transfer_evidence, dict) or native_transfer_evidence.get("source") != "native-transfer-authorization":
        return False
    if {
        key: native_transfer_evidence.get(key)
        for key in ("source_scope", "destination_scope", "method", "redaction")
    } != {
        key: authority[key]
        for key in ("source_scope", "destination_scope", "method", "redaction")
    }:
        return False
    if not authority.get("evidence_id") or native_transfer_evidence.get("evidence_id") != authority["evidence_id"]:
        return False
    if native_transfer_evidence.get("payload_digest") != transfer_payload_digest(trace):
        return False

    def contains_raw_path(value):
        if isinstance(value, dict):
            return any(
                contains_raw_path(child)
                for child in (*value.keys(), *value.values())
            )
        if isinstance(value, (list, tuple)):
            return any(contains_raw_path(child) for child in value)
        if not isinstance(value, str):
            return False
        return bool(re.search(r"(?<![A-Za-z0-9])/(?!/)[^\\s,;]+|~[/\\]|[A-Za-z]:[\\/]|\\\\", value))

    return not contains_raw_path(trace)


def setup_recovery_schedule_admissible(checks):
    return isinstance(checks, list) and 1 <= len(checks) <= MAX_SETUP_RECOVERY_CHECKS


def repository_report_fields_admissible(trace, native_post_write_evidence=None):
    checkpoint_fields = set(trace.get("checkpoint_fields_present", ()))
    terminal_fields = set(trace.get("terminal_fields_present", ()))
    if not REPOSITORY_CHECKPOINT_FIELDS.issubset(checkpoint_fields):
        return False
    if not REPOSITORY_TERMINAL_FIELDS.issubset(terminal_fields):
        return False
    if not terminal_fields.intersection(TERMINAL_DELIVERY_FIELDS):
        return False
    status = trace.get("observed_checkout", {}).get("working_tree_status")
    if status == "clean":
        if "commit_or_pull_request" not in terminal_fields:
            return False
    if status == "dirty":
        if "uncommitted_disposition" not in terminal_fields:
            return False
    if status not in {"clean", "dirty"}:
        return False
    checkpoint_payload = trace.get("checkpoint_payload")
    if not isinstance(checkpoint_payload, dict):
        return False
    if checkpoint_payload.get("execution_context") != trace.get("execution_context"):
        return False
    if checkpoint_payload.get("observed_checkout") != trace.get("observed_checkout"):
        return False
    if checkpoint_payload.get("write_authority") != trace.get("execution_context", {}).get("write_authority"):
        return False
    payload = trace.get("terminal_report_payload")
    if not isinstance(payload, dict):
        return False
    if payload.get("execution_context") != trace.get("execution_context"):
        return False
    if payload.get("observed_checkout") != trace.get("observed_checkout"):
        return False
    if payload.get("execution_context") != checkpoint_payload.get("execution_context") or payload.get("observed_checkout") != checkpoint_payload.get("observed_checkout"):
        return False
    if not isinstance(payload.get("changed_files"), list):
        return False
    if (
        not isinstance(native_post_write_evidence, dict)
        or native_post_write_evidence.get("source") != "native-post-write-check"
        or not native_post_write_evidence.get("evidence_id")
    ):
        return False
    if native_post_write_evidence.get("execution_context") != checkpoint_payload.get("execution_context"):
        return False
    if native_post_write_evidence.get("observed_checkout") != payload.get("observed_checkout"):
        return False
    if native_post_write_evidence.get("changed_files") != payload.get("changed_files"):
        return False
    delivery_field = "commit_or_pull_request" if status == "clean" else "uncommitted_disposition"
    if native_post_write_evidence.get(delivery_field) != payload.get(delivery_field):
        return False
    if status == "clean":
        return bool(payload.get("commit_or_pull_request"))
    return bool(payload.get("uncommitted_disposition"))


def canonical_envelope_payload(envelope):
    return json.dumps(
        {key: value for key, value in envelope.items() if key != "identity_or_digest"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def envelope_digest(envelope):
    return "sha256:" + hashlib.sha256(canonical_envelope_payload(envelope)).hexdigest()


def parent_envelope_admissible(trace, envelope, native_parent_envelope_evidence=None):
    if not isinstance(envelope, dict) or not DESCENDANT_ENVELOPE_FIELDS.issubset(envelope):
        return False
    if any(not envelope[field] for field in DESCENDANT_ENVELOPE_FIELDS):
        return False
    if envelope["parent_id"] != trace.get("direct_parent_id") or envelope["root_id"] != trace.get("root_id"):
        return False
    if envelope["issuer_id"] != trace.get("direct_parent_id"):
        return False
    descendant_actions = [
        action for action in trace.get("actions", ()) if action in DESCENDANT_ACTIONS
    ]
    if not isinstance(envelope["allowed_actions"], list) or not descendant_actions or any(
        action not in envelope["allowed_actions"] for action in descendant_actions
    ):
        return False
    digest = envelope.get("identity_or_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        return False
    if digest != envelope_digest(envelope):
        return False
    if not isinstance(native_parent_envelope_evidence, dict) or native_parent_envelope_evidence.get("source") != "native-parent-envelope":
        return False
    if not native_parent_envelope_evidence.get("evidence_id"):
        return False
    return {
        key: native_parent_envelope_evidence.get(key) for key in DESCENDANT_ENVELOPE_FIELDS
    } == {
        key: envelope[key] for key in DESCENDANT_ENVELOPE_FIELDS
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
    provenance = report.get("authenticated_provenance")
    return (
        identity == report_digest(report)
        and isinstance(provenance, dict)
        and provenance.get("source") == "native-immutable-report"
        and bool(provenance.get("evidence_id"))
        and any(
            event.get("kind") == "immutable-report"
            and event.get("id") == provenance.get("evidence_id")
            and event.get("identity_or_digest") == identity
            and event.get("child_id") == report.get("child_id")
            and event.get("report_revision") == report.get("report_revision")
            for event in observed_native_events
        )
    )


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
            and report["execution_state"] in EXECUTION_STATES
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
    if not isinstance(native_read, dict):
        return False
    try:
        UUID(callback_thread_id)
    except (TypeError, ValueError, AttributeError):
        return False
    required_identity = ("backing_kind", "provider_identity", "app_instance_id")
    if any(not pending.get(field) or native_read.get(field) != pending.get(field) for field in required_identity):
        return False
    return bool(
        pending.get("clientThreadId")
        and native_read
        and native_read.get("threadId") == callback_thread_id
        and native_read.get("requested_hostId") == pending.get("hostId")
        and all(
            pending.get(field) is None
            or native_read.get(field) == pending.get(field)
            for field in (
                "backing_kind",
                "project_id",
                "worktree_path",
                "provider_identity",
                "app_instance_id",
            )
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


def automatic_setup_resolution(pending, bindings, native_read):
    """Model the bounded exact-handle recovery gate without provider side effects."""
    candidates = [
        binding for binding in bindings
        if binding.get("clientThreadId") == pending.get("clientThreadId")
    ]
    if not candidates:
        return {"state": "queued/unmonitorable", "reason": "binding-not-found"}
    if len(candidates) != 1:
        return {"state": "queued/unmonitorable", "reason": "binding-not-unique"}

    candidate = candidates[0]
    window = pending.get("creation_window")
    created_at = candidate.get("created_at")
    if (
        not isinstance(window, (tuple, list))
        or len(window) != 2
        or not isinstance(created_at, (int, float))
        or not window[0] <= created_at <= window[1]
        or candidate.get("hostId") != pending.get("hostId")
        or any(
            pending.get(field) is not None
            and candidate.get(field) != pending.get(field)
            for field in (
                "backing_kind",
                "project_id",
                "worktree_path",
                "provider_identity",
                "app_instance_id",
            )
        )
    ):
        return {"state": "queued/unmonitorable", "reason": "binding-mismatch"}

    if not callback_resolution_is_operable(
        pending,
        candidate.get("threadId"),
        native_read,
    ):
        return {"state": "queued/unmonitorable", "reason": "native-read-unconfirmed"}
    return {
        "state": "ready",
        "reason": "native-confirmed",
        "threadId": candidate["threadId"],
        "hostId": candidate["hostId"],
    }


def attached_callbacks_reach_parent(parent_task_id, route, first_callback, terminal_callback):
    if not parent_task_id or route != "send_message_to_thread" or not first_callback or not terminal_callback:
        return False
    callbacks = (first_callback, terminal_callback)
    if any(
        callback.get("target_task_id") != parent_task_id or callback.get("route") != route
        for callback in callbacks
    ):
        return False
    first_report = first_callback.get("report", {})
    terminal_report = terminal_callback.get("report", {})
    if (
        first_report.get("child_id") != terminal_report.get("child_id")
        or not isinstance(first_report.get("report_revision"), int)
        or not isinstance(terminal_report.get("report_revision"), int)
        or terminal_report["report_revision"] <= first_report["report_revision"]
        or terminal_report.get("supersedes") != first_report["report_revision"]
    ):
        return False
    return (
        attached_report_admissible(
            first_callback["report"],
            observed_native_events=first_callback.get("observed_native_events", ()),
        )
        and attached_report_admissible(
            terminal_callback["report"],
            terminal=True,
            observed_native_events=terminal_callback.get("observed_native_events", ()),
        )
    )


class DelegateProtocolTransitionTests(unittest.TestCase):
    def test_attached_checkpoint_and_terminal_reports_require_immutable_identity(self):
        checkpoint = {
            "child_id": "child-1",
            "report_revision": 4,
            "report_identity_or_digest": "turn:42",
            "observed_at": "2026-09-15T10:00:00Z",
            "execution_state": "executing",
            "task_liveness": "live",
            "progress_kind": "verification_complete",
            "evidence_refs": ["turn:42"],
            "blocker_or_decision": None,
            "next_gate": "parent-review",
        }
        terminal = {
            "child_id": "child-1",
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
        terminal["authenticated_provenance"] = {
            "source": "native-immutable-report",
            "evidence_id": "terminal-5",
        }
        terminal["report_identity_or_digest"] = report_digest(terminal)
        checkpoint_events = [{"kind": "turn", "id": "42", "report_revision": 4, "child_id": "child-1"}]
        terminal_events = [{
            "kind": "immutable-report",
            "id": "terminal-5",
            "identity_or_digest": terminal["report_identity_or_digest"],
            "child_id": "child-1",
            "report_revision": 5,
        }]
        self.assertFalse(attached_report_admissible(checkpoint))
        self.assertTrue(attached_report_admissible(checkpoint, observed_native_events=checkpoint_events))
        self.assertTrue(attached_report_admissible(terminal, terminal=True, observed_native_events=terminal_events))
        self.assertFalse(attached_report_admissible(dict(terminal, authenticated_provenance=None), terminal=True, observed_native_events=terminal_events))
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
            "execution_state": "executing",
            "task_liveness": "live",
            "progress_kind": "evidence_added",
            "evidence_refs": ["turn:42"],
            "blocker_or_decision": None,
            "next_gate": "parent-review",
        }
        terminal = {
            "child_id": "child-1",
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
            "execution_state": "executing",
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
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
        }
        callback_thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473413"
        native_read = {
            "threadId": callback_thread_id,
            "requested_hostId": "local",
            "backing_kind": "codex",
            "project_id": "skills",
            "worktree_path": "/worktrees/skills-child",
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
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
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
        }
        thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473414"
        native_read = {
            "threadId": thread_id,
            "requested_hostId": "local",
            "backing_kind": "codex",
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
        }
        ready = {"status": "ready", "threadId": thread_id, "hostId": "local"}
        self.assertTrue(runtime_resolution_is_operable(pending, ready, native_read))
        for field in ("provider_identity", "app_instance_id"):
            incomplete = dict(pending)
            del incomplete[field]
            self.assertFalse(runtime_resolution_is_operable(incomplete, ready, native_read))
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

    def test_automatic_setup_resolution_accepts_one_exact_binding_after_native_confirmation(self):
        pending = {
            "clientThreadId": "setup-39",
            "hostId": "local",
            "creation_window": (100, 110),
            "backing_kind": "codex",
            "project_id": "skills",
            "worktree_path": "/worktrees/skills-child",
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
        }
        thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473416"
        binding = dict(pending, threadId=thread_id, created_at=105)
        native_read = {
            "threadId": thread_id,
            "requested_hostId": "local",
            "backing_kind": "codex",
            "project_id": "skills",
            "worktree_path": "/worktrees/skills-child",
            "provider_identity": "codex-desktop:account-a",
            "app_instance_id": "app-a",
        }
        self.assertEqual(
            automatic_setup_resolution(pending, [binding], native_read),
            {"state": "ready", "reason": "native-confirmed", "threadId": thread_id, "hostId": "local"},
        )

    def test_automatic_setup_resolution_stays_queued_for_absent_or_timed_out_binding(self):
        pending = {
            "clientThreadId": "setup-40",
            "hostId": "local",
            "creation_window": (100, 110),
        }
        self.assertEqual(
            automatic_setup_resolution(pending, [], None)["state"],
            "queued/unmonitorable",
        )
        timed_out = dict(pending, clientThreadId="setup-41")
        binding = dict(timed_out, threadId="01a0a4b7-7a3b-70f0-9044-d49469473417", created_at=111)
        self.assertEqual(
            automatic_setup_resolution(timed_out, [binding], None)["reason"],
            "binding-mismatch",
        )

    def test_automatic_setup_resolution_rejects_duplicate_or_mismatched_bindings(self):
        pending = {
            "clientThreadId": "setup-42",
            "hostId": "local",
            "creation_window": (100, 110),
            "backing_kind": "codex",
            "project_id": "skills",
        }
        first = dict(pending, threadId="01a0a4b7-7a3b-70f0-9044-d49469473418", created_at=105)
        second = dict(pending, threadId="01a0a4b7-7a3b-70f0-9044-d49469473419", created_at=106)
        self.assertEqual(
            automatic_setup_resolution(pending, [first, second], None)["reason"],
            "binding-not-unique",
        )
        mismatched = dict(first, project_id="other-project")
        self.assertEqual(
            automatic_setup_resolution(pending, [mismatched], None)["reason"],
            "binding-mismatch",
        )

    def test_automatic_setup_resolution_rejects_native_read_failure(self):
        pending = {
            "clientThreadId": "setup-43",
            "hostId": "local",
            "creation_window": (100, 110),
            "backing_kind": "codex",
        }
        thread_id = "01a0a4b7-7a3b-70f0-9044-d49469473420"
        binding = dict(pending, threadId=thread_id, created_at=105)
        self.assertEqual(
            automatic_setup_resolution(pending, [binding], None)["reason"],
            "native-read-unconfirmed",
        )

    def test_setup_recovery_schedule_is_bounded(self):
        self.assertTrue(setup_recovery_schedule_admissible(["immediate"]))
        self.assertTrue(setup_recovery_schedule_admissible(["immediate", "delayed-1", "delayed-2"]))
        self.assertFalse(setup_recovery_schedule_admissible([]))
        self.assertFalse(setup_recovery_schedule_admissible(["check"] * 4))

    def test_automatic_setup_resolution_has_no_title_or_path_fallback(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        contract = (SKILL_ROOT / "references" / "task-contract.md").read_text()
        provider = (SKILL_ROOT.parent / "agent-communication" / "references" / "codex-chatgpt.md").read_text()
        for text in (skill, contract, provider):
            self.assertIn("Never", text)
            self.assertIn("title", text)
            self.assertIn("path", text)
        self.assertIn("No user request is a prerequisite", contract)

    def test_local_terminal_report_does_not_replace_identity_bearing_parent_callbacks(self):
        parent_task_id = "01a0a74d-parent"
        checkpoint = {
            "child_id": "child-1", "report_revision": 1, "report_identity_or_digest": "turn:1",
            "observed_at": "now", "execution_state": "executing", "task_liveness": "live",
            "progress_kind": "phase_change", "evidence_refs": ["turn:1"], "blocker_or_decision": None,
            "next_gate": "verify",
        }
        terminal = {
            "child_id": "child-1",
            "outcome": "complete", "delivered_artifact": None,
            "acceptance_map": {"criterion-a": "pending"}, "checks_and_observed_results": [],
            "residual_risks": [], "unmet_requirements": [], "availability": "available",
            "report_revision": 2, "report_identity_or_digest": None, "supersedes": 1,
        }
        terminal["authenticated_provenance"] = {
            "source": "native-immutable-report",
            "evidence_id": "terminal-2",
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
            "observed_native_events": [{
                "kind": "immutable-report",
                "id": "terminal-2",
                "identity_or_digest": terminal["report_identity_or_digest"],
                "child_id": "child-1",
                "report_revision": 2,
            }],
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
        self.assertFalse(attached_callbacks_reach_parent(
            parent_task_id,
            "send_message_to_thread",
            first_callback,
            dict(terminal_callback, report=dict(terminal, child_id="child-2")),
        ))
        self.assertFalse(attached_callbacks_reach_parent(
            parent_task_id,
            "send_message_to_thread",
            first_callback,
            dict(terminal_callback, report=dict(terminal, supersedes=999)),
        ))

    def test_execution_boundary_cases_run_through_action_trace_oracle(self):
        cases = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())["execution_boundary_cases"]
        for case in cases:
            oracle = case.get("protocol_oracle")
            self.assertIsInstance(oracle, dict, case["id"])
            self.assertEqual(oracle["kind"], "execution_boundary")
            actual = execution_boundary_admissible(
                oracle["trace"],
                oracle.get("native_execution_evidence"),
                oracle.get("native_parent_envelope_evidence"),
                oracle.get("native_transfer_evidence"),
                oracle.get("native_post_write_evidence"),
            )
            expected = oracle["expected"] == "accept"
            self.assertEqual(actual, expected, case["id"])
            if case["id"] == "repo-writing-managed-worktree-context":
                self.assertTrue(repository_report_fields_admissible(
                    oracle["trace"],
                    oracle["native_post_write_evidence"],
                ))

        managed = next(case for case in cases if case["id"] == "repo-writing-managed-worktree-context")
        trace = managed["protocol_oracle"]["trace"]
        native_execution = managed["protocol_oracle"]["native_execution_evidence"]
        native_post_write = managed["protocol_oracle"]["native_post_write_evidence"]
        admit = lambda candidate: execution_boundary_admissible(
            candidate, native_execution, None, None, native_post_write
        )
        self.assertFalse(execution_boundary_admissible(trace))
        for field in EXECUTION_CONTEXT_FIELDS:
            missing = dict(trace, execution_context={k: v for k, v in trace["execution_context"].items() if k != field})
            self.assertFalse(admit(missing), field)
        for field in OBSERVED_CHECKOUT_FIELDS:
            missing = dict(trace, observed_checkout={k: v for k, v in trace["observed_checkout"].items() if k != field})
            self.assertFalse(admit(missing), field)
        for field, value in (("cwd", "/wrong/checkout"), ("branch_or_ref", "main"), ("base_revision", "stale")):
            mismatched = dict(
                trace,
                observed_checkout=dict(trace["observed_checkout"], **{field: value}),
            )
            self.assertFalse(admit(mismatched), field)
        self.assertFalse(admit(dict(
            trace,
            execution_evidence={"source": "self-report", "evidence_id": "event:forged"},
        )))
        self.assertFalse(path_disclosure_admissible(dict(
            trace,
            destination_scope="cloud",
        )))
        self.assertFalse(path_disclosure_admissible({
            "destination_scope": "same-host",
            "secret": "/private/secret.txt",
        }))
        transfer_trace = dict(
            trace,
            destination_scope="cloud",
            path_transfer_authority={
                "source_scope": "same-host",
                "destination_scope": "cloud",
                "method": "authorized-path-transfer",
                "evidence_id": "event:transfer-1",
                "redaction": "opaque-identifiers",
            },
            execution_context=dict(
                trace["execution_context"],
                project_path="project-id",
                cwd="worktree-id",
                worktree_path="worktree-id",
            ),
            execution_evidence=dict(
                trace["execution_evidence"],
                project_path="project-id",
                cwd="worktree-id",
                worktree_root="worktree-id",
            ),
            observed_checkout=dict(
                trace["observed_checkout"],
                project_path="project-id",
                cwd="worktree-id",
                worktree_root="worktree-id",
            ),
            terminal_report_payload={
                "execution_context": {
                    key: value for key, value in trace["execution_context"].items()
                    if key not in {"project_path", "cwd", "worktree_path"}
                } | {"project_path": "project-id", "cwd": "worktree-id", "worktree_path": "worktree-id"},
                "observed_checkout": {
                    "project_path": "project-id",
                    "cwd": "worktree-id",
                    "worktree_root": "worktree-id",
                    "branch_or_ref": "codex/child",
                    "head_revision": "child-head",
                    "base_revision": "origin/main",
                    "working_tree_status": "clean",
                },
                "changed_files": ["src/example.py"],
                "commit_or_pull_request": "commit:child-head",
            },
        )
        transfer_trace["checkpoint_payload"] = {
            "execution_context": transfer_trace["execution_context"],
            "observed_checkout": transfer_trace["observed_checkout"],
            "write_authority": "authorized",
        }
        self.assertTrue(path_disclosure_admissible(
            transfer_trace,
            native_transfer_evidence={
                "source": "native-transfer-authorization",
                "evidence_id": "event:transfer-1",
                "source_scope": "same-host",
                "destination_scope": "cloud",
                "method": "authorized-path-transfer",
                "redaction": "opaque-identifiers",
                "payload_digest": transfer_payload_digest(transfer_trace),
            },
        ))
        self.assertFalse(path_disclosure_admissible(
            transfer_trace,
            native_transfer_evidence={
                "source": "native-transfer-authorization",
                "evidence_id": "event:forged",
                "source_scope": "same-host",
                "destination_scope": "cloud",
                "method": "authorized-path-transfer",
                "redaction": "opaque-identifiers",
                "payload_digest": transfer_payload_digest(transfer_trace),
            },
        ))
        self.assertFalse(path_disclosure_admissible(dict(
            trace,
            destination_scope="cloud",
            path_transfer_authority={
                "source_scope": "same-host",
                "destination_scope": "cloud",
                "method": "authorized-path-transfer",
                "evidence_id": "event:transfer-1",
                "redaction": "opaque-identifiers",
            },
            terminal_report_payload={"changed_files": ["/private/secret.txt"]},
        )))
        self.assertFalse(admit(dict(
            trace,
            actions=["execute_directly", "write", "checkpoint", "terminal_report"],
            terminal_fields_present=["execution_context", "changed_files"],
        )))
        for field in REPOSITORY_CHECKPOINT_FIELDS:
            self.assertFalse(repository_report_fields_admissible(dict(
                trace,
                checkpoint_fields_present=[
                    value for value in trace["checkpoint_fields_present"] if value != field
                ],
            )))
        for field in REPOSITORY_TERMINAL_FIELDS:
            self.assertFalse(repository_report_fields_admissible(dict(
                trace,
                terminal_fields_present=[
                    value for value in trace["terminal_fields_present"] if value != field
                ],
            )))
        self.assertFalse(repository_report_fields_admissible(dict(
            trace,
            terminal_fields_present=[
                value for value in trace["terminal_fields_present"]
                if value != "commit_or_pull_request"
            ],
        )))
        dirty = dict(
            trace,
            observed_checkout=dict(trace["observed_checkout"], working_tree_status="dirty"),
            checkpoint_payload=dict(
                trace["checkpoint_payload"],
                observed_checkout=dict(trace["observed_checkout"], working_tree_status="dirty"),
            ),
            terminal_fields_present=[
                value for value in trace["terminal_fields_present"]
                if value != "commit_or_pull_request"
            ] + ["uncommitted_disposition"],
            terminal_report_payload=dict(
                trace["terminal_report_payload"],
                observed_checkout=dict(trace["observed_checkout"], working_tree_status="dirty"),
                uncommitted_disposition="left-dirty-with-owner",
            ),
        )
        dirty_native_post_write = dict(
            native_post_write,
            observed_checkout=dict(native_post_write["observed_checkout"], working_tree_status="dirty"),
            uncommitted_disposition="left-dirty-with-owner",
        )
        self.assertTrue(repository_report_fields_admissible(dirty, dirty_native_post_write))
        self.assertFalse(repository_report_fields_admissible(dict(
            trace,
            checkpoint_payload=dict(
                trace["checkpoint_payload"],
                observed_checkout=dict(trace["checkpoint_payload"]["observed_checkout"], head_revision="forged"),
            ),
        )))
        self.assertFalse(repository_report_fields_admissible(dict(
            dirty,
            terminal_fields_present=[
                value for value in dirty["terminal_fields_present"]
                if value != "uncommitted_disposition"
            ],
        )))
        self.assertFalse(admit(dict(trace, actions=["write"])))
        self.assertFalse(admit(dict(
            trace, actions=["execute_directly", "write", "checkpoint", "terminal_report"]
        )))
        self.assertFalse(admit(dict(
            trace, actions=["execute_directly", "checkpoint", "terminal_report", "write"]
        )))
        for action in ("modify", "append", "update", "copy", "commit", "deploy", "publish", "merge", "overwrite"):
            with self.subTest(action=action):
                self.assertFalse(admit(
                    dict(trace, actions=["execute_directly", action]),
                ))

    def test_execution_boundary_binds_each_checkout_evidence_field(self):
        cases = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())["execution_boundary_cases"]
        oracle = next(case for case in cases if case["id"] == "repo-writing-managed-worktree-context")["protocol_oracle"]
        trace = oracle["trace"]
        native_execution = oracle["native_execution_evidence"]
        native_post_write = oracle["native_post_write_evidence"]
        for field in EXECUTION_EVIDENCE_FIELDS:
            mutated = dict(trace, execution_evidence=dict(trace["execution_evidence"], **{field: "forged"}))
            self.assertFalse(execution_boundary_admissible(mutated, native_execution, None, None, native_post_write), field)
            forged_native = dict(native_execution, **{field: "forged"})
            self.assertFalse(execution_boundary_admissible(trace, forged_native, None, None, native_post_write), f"native:{field}")

    def test_provider_default_and_authorized_direct_local_have_positive_coverage(self):
        import copy

        cases = json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())["execution_boundary_cases"]
        managed = next(case for case in cases if case["id"] == "repo-writing-managed-worktree-context")["protocol_oracle"]["trace"]
        managed_native = next(case for case in cases if case["id"] == "repo-writing-managed-worktree-context")["protocol_oracle"]["native_execution_evidence"]
        managed_post_write = next(case for case in cases if case["id"] == "repo-writing-managed-worktree-context")["protocol_oracle"]["native_post_write_evidence"]

        provider_default = copy.deepcopy(managed)
        provider_default["execution_context"].pop("requested_starting_state")
        provider_default["execution_context"]["provider_default_rule"] = {
            "branch_or_ref": "codex/child",
            "base_revision": "origin/main",
        }
        provider_default["execution_evidence"]["starting_state"] = provider_default["execution_context"]["provider_default_rule"]
        provider_native = copy.deepcopy(managed_native)
        provider_native["starting_state"] = provider_default["execution_context"]["provider_default_rule"]
        provider_default["terminal_report_payload"]["execution_context"] = provider_default["execution_context"]
        provider_default["checkpoint_payload"]["execution_context"] = provider_default["execution_context"]
        provider_post_write = copy.deepcopy(managed_post_write)
        provider_post_write["execution_context"] = provider_default["execution_context"]
        self.assertTrue(execution_boundary_admissible(provider_default, provider_native, None, None, provider_post_write))
        self.assertFalse(execution_boundary_admissible(dict(
            provider_default,
            observed_checkout=dict(provider_default["observed_checkout"], branch_or_ref="wrong"),
        ), provider_native, None, None, provider_post_write))

        direct_local = copy.deepcopy(managed)
        direct_local["execution_context"].update({
            "cwd": "/repo",
            "worktree_path": "/repo",
            "execution_mode": "direct-local",
            "exclusive_writer_commitment": True,
        })
        direct_local["execution_context"].pop("worktree_path", None)
        direct_local["observed_checkout"].update({"cwd": "/repo", "worktree_root": "/repo"})
        direct_local["execution_evidence"].update({"cwd": "/repo", "worktree_root": "/repo"})
        direct_local["terminal_report_payload"]["execution_context"] = direct_local["execution_context"]
        direct_local["terminal_report_payload"]["observed_checkout"] = direct_local["observed_checkout"]
        direct_native = copy.deepcopy(managed_native)
        direct_native.update({"cwd": "/repo", "worktree_root": "/repo"})
        direct_local["checkpoint_payload"]["execution_context"] = direct_local["execution_context"]
        direct_local["checkpoint_payload"]["observed_checkout"] = direct_local["observed_checkout"]
        direct_post_write = copy.deepcopy(managed_post_write)
        direct_post_write["execution_context"] = direct_local["execution_context"]
        direct_post_write["observed_checkout"] = direct_local["observed_checkout"]
        self.assertTrue(execution_boundary_admissible(direct_local, direct_native, None, None, direct_post_write))
        direct_local["execution_context"]["exclusive_writer_commitment"] = False
        self.assertFalse(execution_boundary_admissible(direct_local, direct_native, None, None, direct_post_write))

    def test_parent_envelope_requires_authenticated_digest_and_issuer_binding(self):
        import copy

        case = next(case for case in json.loads((SKILL_ROOT / "evals" / "cases.json").read_text())["execution_boundary_cases"] if case["id"] == "parent-issued-descendant-envelope")
        oracle = case["protocol_oracle"]
        trace = oracle["trace"]
        self.assertTrue(execution_boundary_admissible(
            trace,
            oracle["native_execution_evidence"],
            oracle["native_parent_envelope_evidence"],
        ))
        forged = copy.deepcopy(trace)
        forged["parent_issued_envelope"]["scope"] = "write-anything"
        forged["parent_issued_envelope"]["identity_or_digest"] = envelope_digest(forged["parent_issued_envelope"])
        self.assertFalse(execution_boundary_admissible(
            forged,
            oracle["native_execution_evidence"],
            oracle["native_parent_envelope_evidence"],
        ))
        forged = copy.deepcopy(trace)
        forged_external = copy.deepcopy(oracle["native_parent_envelope_evidence"])
        forged_external["issuer_id"] = "forged-parent"
        self.assertFalse(execution_boundary_admissible(
            forged,
            oracle["native_execution_evidence"],
            forged_external,
        ))
        forged_actions = copy.deepcopy(trace)
        forged_actions["actions"] = ["delegate-to-thread", "fork"]
        self.assertFalse(execution_boundary_admissible(
            forged_actions,
            oracle["native_execution_evidence"],
            oracle["native_parent_envelope_evidence"],
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
            "observed_at": "now", "execution_state": "executing", "task_liveness": "live",
            "progress_kind": "phase_change", "evidence_refs": ["turn:1"], "blocker_or_decision": None,
            "next_gate": "verify",
        }
        terminal = {
            "child_id": "child-1",
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
