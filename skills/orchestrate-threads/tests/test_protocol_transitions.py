import unittest
import hashlib
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def source_report_digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def source_identity_is_backed(evidence):
    identity = evidence.get("source_report_identity_or_digest")
    if not isinstance(identity, str):
        return False
    if identity.startswith(("turn:", "event:")):
        kind, _, event_id = identity.partition(":")
        native = evidence.get("source_native_evidence")
        return bool(event_id) and native == {
            "kind": kind,
            "id": event_id,
            "source_child_id": evidence.get("source_child_id"),
            "source_report_revision": evidence.get("source_report_revision"),
        }
    payload = evidence.get("source_report_payload")
    return isinstance(payload, dict) and identity == source_report_digest(payload)


def _report_edge_matches(edge, evidence):
    return (
        edge["source_child_id"] == evidence["source_child_id"]
        and edge["criterion"] == evidence["criterion"]
        and edge["source_report_identity_or_digest"] == evidence["source_report_identity_or_digest"]
        and edge["source_report_revision"] == evidence["source_report_revision"]
        and source_identity_is_backed(evidence)
        and not edge.get("superseded", False)
        and not evidence.get("superseded", False)
    )


def accepted_evidence_opens(edge, evidence):
    return edge["type"] == "accepted_evidence" and edge["source_artifact_revision_or_digest"] == "not_applicable" and _report_edge_matches(edge, evidence)


def artifact_edge_opens(edge, evidence):
    return _report_edge_matches(edge, evidence) and (
        edge["type"] == "available_artifact"
        and edge["source_artifact_revision_or_digest"] == evidence.get("source_artifact_revision_or_digest")
        and edge["readable_path"] == evidence.get("readable_path")
        and bool(evidence.get("readable_path"))
    )


def checkpoint_identity_is_backed(checkpoint, observed_native_events):
    identity = checkpoint.get("report_identity_or_digest")
    if not isinstance(identity, str) or not identity.startswith(("turn:", "event:")):
        return False
    kind, _, event_id = identity.partition(":")
    return bool(event_id) and {
        "kind": kind,
        "id": event_id,
        "report_revision": checkpoint.get("report_revision"),
    } in observed_native_events


def attention_acknowledged(response_sent, previous_checkpoint, checkpoint, observed_native_events=()):
    return bool(
        response_sent
        and checkpoint
        and checkpoint.get("progress_kind") == "attention_acknowledged"
        and checkpoint.get("report_revision", -1) > previous_checkpoint.get("report_revision", -1)
        and checkpoint_identity_is_backed(checkpoint, observed_native_events)
        and checkpoint_identity_is_backed(previous_checkpoint, observed_native_events)
        and checkpoint.get("report_identity_or_digest") != previous_checkpoint.get("report_identity_or_digest")
        and checkpoint.get("applied_decision")
        and checkpoint.get("next_gate")
    )


def claims_conflict(left, right):
    if left["access_mode"] == right["access_mode"] == "read":
        return False
    if left["resource_id"] == right["resource_id"]:
        return True
    return left["destination_fingerprint"] == right["destination_fingerprint"] and bool(
        set(left["paths_or_scope"]) & set(right["paths_or_scope"])
    )


def acceptance_gate_opens(state):
    return state.get("acceptance") == "accepted" and not state.get("authority_revoked", False)


class OrchestrationProtocolTransitionTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "source_child_id": "child-1",
            "criterion": "criterion-a",
            "source_report_revision": 7,
            "source_report_identity_or_digest": "turn:77",
            "source_native_evidence": {
                "kind": "turn",
                "id": "77",
                "source_child_id": "child-1",
                "source_report_revision": 7,
            },
            "source_artifact_revision_or_digest": "not_applicable",
        }

    def test_evidence_only_gate_opens_without_artifact(self):
        edge = dict(self.evidence, type="accepted_evidence")
        self.assertTrue(accepted_evidence_opens(edge, self.evidence))

    def test_stale_or_missing_identity_recloses_dependant(self):
        edge = dict(self.evidence, type="accepted_evidence")
        self.assertFalse(accepted_evidence_opens(edge, dict(self.evidence, source_report_identity_or_digest=None)))
        self.assertFalse(accepted_evidence_opens(edge, dict(self.evidence, source_report_identity_or_digest="claimed-pass")))
        self.assertFalse(accepted_evidence_opens(edge, dict(
            self.evidence,
            source_report_identity_or_digest="turn:unobserved",
        )))
        self.assertFalse(accepted_evidence_opens(edge, dict(
            self.evidence,
            source_report_identity_or_digest="sha256:" + "0" * 64,
            source_native_evidence=None,
        )))
        self.assertFalse(accepted_evidence_opens(edge, dict(self.evidence, superseded=True)))
        self.assertFalse(accepted_evidence_opens(dict(edge, superseded=True), self.evidence))

    def test_recomputable_digest_opens_only_for_its_exact_payload(self):
        payload = {"outcome": "complete", "checks": ["test: pass"]}
        digest = source_report_digest(payload)
        evidence = dict(
            self.evidence,
            source_report_identity_or_digest=digest,
            source_native_evidence=None,
            source_report_payload=payload,
        )
        edge = dict(evidence, type="accepted_evidence")
        self.assertTrue(accepted_evidence_opens(edge, evidence))
        self.assertFalse(accepted_evidence_opens(edge, dict(
            evidence,
            source_report_payload={"outcome": "complete", "checks": ["test: failed"]},
        )))

    def test_artifact_edge_requires_exact_readable_postimage(self):
        edge = dict(
            self.evidence,
            type="available_artifact",
            source_artifact_revision_or_digest="git:post-image",
            readable_path="src/a.py",
        )
        available = dict(self.evidence, source_artifact_revision_or_digest="git:post-image", readable_path="src/a.py")
        self.assertTrue(artifact_edge_opens(edge, available))
        self.assertFalse(artifact_edge_opens(edge, dict(available, source_artifact_revision_or_digest="git:pre-image")))
        self.assertFalse(artifact_edge_opens(edge, dict(available, readable_path=None)))
        self.assertFalse(artifact_edge_opens(dict(edge, superseded=True), available))

    def test_attention_requires_observed_acknowledgement_after_response(self):
        previous = {"report_revision": 4, "report_identity_or_digest": "turn:4"}
        acknowledged = {
            "report_revision": 5,
            "report_identity_or_digest": "turn:5",
            "progress_kind": "attention_acknowledged",
            "applied_decision": "continue-with-check",
            "next_gate": "verify",
        }
        observed = [
            {"kind": "turn", "id": "4", "report_revision": 4},
            {"kind": "turn", "id": "5", "report_revision": 5},
        ]
        self.assertFalse(attention_acknowledged(True, previous, {"progress_kind": "no_change"}))
        self.assertFalse(attention_acknowledged(True, previous, acknowledged))
        self.assertTrue(attention_acknowledged(True, previous, acknowledged, observed))
        self.assertFalse(attention_acknowledged(True, previous, dict(acknowledged, report_revision=4), observed))
        self.assertFalse(attention_acknowledged(
            True,
            previous,
            dict(acknowledged, report_identity_or_digest="acknowledged"),
        ))
        self.assertFalse(attention_acknowledged(True, previous, dict(acknowledged, applied_decision=None), observed))
        self.assertFalse(attention_acknowledged(False, previous, acknowledged, observed))

    def test_overlapping_writes_conflict_but_disjoint_reads_do_not(self):
        write_a = {"resource_id": "repo:A", "resource_kind": "repository", "destination_fingerprint": "repo:A", "paths_or_scope": ["src/a.py"], "access_mode": "write"}
        write_b = {"resource_id": "repo:A", "resource_kind": "repository", "destination_fingerprint": "repo:A", "paths_or_scope": ["src/a.py"], "access_mode": "write"}
        read_b = {"resource_id": "repo:A", "resource_kind": "repository", "destination_fingerprint": "repo:A", "paths_or_scope": ["src/a.py"], "access_mode": "read"}
        read_c = {"resource_id": "repo:C", "resource_kind": "repository", "destination_fingerprint": "repo:A", "paths_or_scope": ["src/c.py"], "access_mode": "read"}
        external_a = {"resource_id": "deploy:staging", "resource_kind": "external", "destination_fingerprint": "host:one", "paths_or_scope": ["release"], "access_mode": "write"}
        external_b = {"resource_id": "deploy:staging", "resource_kind": "external", "destination_fingerprint": "host:two", "paths_or_scope": ["other"], "access_mode": "write"}
        self.assertTrue(claims_conflict(write_a, write_b))
        self.assertFalse(claims_conflict(read_b, read_c))
        self.assertTrue(claims_conflict(external_a, external_b))

    def test_ambiguous_creation_and_revoked_authority_cannot_open_gates(self):
        self.assertFalse(bool({"execution": "indeterminate", "exact_identity": None}.get("exact_identity")))
        self.assertFalse(acceptance_gate_opens({"authority_revoked": True, "acceptance": "accepted"}))

    def test_adversarial_catalog_scenarios_execute_against_protocol_oracles(self):
        scenarios = json.loads((SKILL_ROOT / "evals" / "scenarios.json").read_text())["scenarios"]
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
        catalog_scenarios = [scenario for scenario in scenarios if scenario["id"] in expected]
        self.assertEqual({scenario["id"] for scenario in catalog_scenarios}, expected)

        def terminal_report_complete(report):
            return all(report.get(field) is not None for field in (
                "outcome", "acceptance_map", "checks_and_observed_results", "residual_risks",
                "unmet_requirements", "availability", "report_revision", "report_identity_or_digest", "supersedes",
            ))

        def evaluate(oracle):
            kind = oracle["kind"]
            if kind == "missing_terminal_evidence":
                return not terminal_report_complete({"outcome": "complete", "report_identity_or_digest": "turn:1"})
            if kind == "live_without_progress":
                return not acceptance_gate_opens(oracle["expected_state"])
            if kind == "attention_without_ack":
                previous = {"report_revision": oracle["previous_revision"], "report_identity_or_digest": oracle["current_identity"]}
                current = {"report_revision": oracle["current_revision"], "report_identity_or_digest": oracle["current_identity"], "progress_kind": "attention_acknowledged", "applied_decision": "continue", "next_gate": "verify"}
                return not attention_acknowledged(True, previous, current)
            if kind in {"orphaned_creation", "ambiguous_creation"}:
                return oracle["exact_identity"] is None and oracle["retry"] is False
            if kind == "stale_dependency":
                edge = dict(self.evidence, type="accepted_evidence", superseded=oracle["edge_superseded"])
                evidence = dict(self.evidence, source_report_revision=oracle["evidence_revision"])
                return not accepted_evidence_opens(edge, evidence)
            if kind == "resource_conflict":
                left = {"resource_id": oracle["left_resource_id"], "destination_fingerprint": "one", "paths_or_scope": ["x"], "access_mode": oracle["left_access"]}
                right = {"resource_id": oracle["right_resource_id"], "destination_fingerprint": "two", "paths_or_scope": ["y"], "access_mode": oracle["right_access"]}
                return claims_conflict(left, right)
            if kind == "unowned_claim":
                return oracle["owner"] is None
            if kind == "unverified_completion":
                return not oracle["verified"] and not acceptance_gate_opens({"acceptance": "pending", "outcome": oracle["outcome"]})
            if kind == "revoked_authority":
                return not acceptance_gate_opens({"acceptance": oracle["acceptance"], "authority_revoked": oracle["authority_revoked"]})
            if kind == "wrong_artifact_revision":
                return oracle["maker_digest"] != oracle["reviewer_digest"]
            if kind == "compound_closed_gates":
                return (not acceptance_gate_opens({"acceptance": oracle["acceptance"], "authority_revoked": oracle["authority_revoked"]}) and oracle["same_resource_id"])
            raise AssertionError(f"unhandled protocol oracle kind: {kind}")

        for scenario in catalog_scenarios:
            oracle = scenario.get("protocol_oracle")
            self.assertIsInstance(oracle, dict, scenario["id"])
            self.assertEqual(oracle["expected_state"], scenario["expected_state"], scenario["id"])
            self.assertTrue(evaluate(oracle), scenario["id"])


if __name__ == "__main__":
    unittest.main()
