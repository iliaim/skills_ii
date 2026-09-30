import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_paired_evals", ROOT / "scripts" / "run_paired_evals.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class PairedEvalContracts(unittest.TestCase):
    def setUp(self):
        self.cases = {case["id"]: case for case in runner.load_cases(ROOT / "evals" / "paired-cases.json")}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)

    def executor(self, name="nominal"):
        case = self.cases[name]
        request = runner.make_request(case)
        executor = runner.ScratchExecutor(self.tmp / name, case, request)
        return case, request, executor

    def action(self, request, operation="write_artifact", status="accepted", reason="none"):
        return runner.response(request, phase="receiver_action", operation=operation, status=status, reason=reason)

    def valid_exchange(self, name):
        case, request, executor = self.executor(name)
        reason = runner.boundary(case)
        operation = runner.expected_operation(case)
        action = self.action(request, operation, "reported" if reason in {"status", "report"} else "held" if reason else "accepted", reason or "none")
        if case["context"]["callback_requested"]:
            action.update(callback_disposition="held", callback_reason="authority")
        receipt, failures = executor.execute(action)
        final = runner.response(request, phase="receiver_result", status="reported" if reason in {"status", "report"} else "held" if reason or not receipt else "completed", reason=reason or ("none" if receipt else "uncertain"), receipt=receipt)
        if case["context"]["callback_requested"]:
            final.update(callback_disposition="held", callback_reason="authority")
        return case, request, executor, action, final, failures

    def test_nominal_is_real_bytes_journal_and_actor_bound_receipt(self):
        case, request, executor, action, final, failures = self.valid_exchange("nominal")
        self.assertEqual(executor.artifact.read_bytes(), b"paired scratch alpha\n")
        self.assertEqual(json.loads(executor.journal.read_text())[0]["actor"], "receiver-B")
        self.assertEqual(final["receipt"]["effect_count"], 1)
        self.assertEqual(final["receipt"]["request_digest"], request["request_digest"])
        self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])

    def test_all_receiver_contexts_have_coherent_independent_oracle(self):
        for name, case in self.cases.items():
            if case["sender_observation"]:
                continue
            with self.subTest(case=name):
                case, request, executor, action, final, failures = self.valid_exchange(name)
                self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])
                classification = runner.response(request, phase="sender_classification", status="no_work" if request["intent"] != "execute" else "accepted" if final["receipt"] else "incomplete", receipt=final["receipt"])
                self.assertEqual(runner.grade_sender(request, classification, final, executor.receipt()), [])

    def test_authority_scope_owner_claim_stale_conflict_and_callback_block_requested_effect(self):
        for name in ("unauthorized-execution", "unauthorized-scope", "transfer-no-release", "transfer-writer-claim", "stale-revision", "future-revision", "conflicting-payload", "status-only", "report-only", "unauthorized-callback"):
            with self.subTest(case=name):
                case, request, executor = self.executor(name)
                count = executor.observe()["effect_count"]
                action = self.action(request, "callback" if name == "unauthorized-callback" else "write_artifact")
                receipt, failures = executor.execute(action)
                self.assertIn("unauthorized_action_request", failures)
                self.assertIsNone(receipt)
                self.assertEqual(executor.observe()["effect_count"], count)
                final = runner.response(request, phase="receiver_result")
                self.assertIn("unauthorized_action_request", runner.grade_receiver(case, request, action, final, executor, failures))

    def test_each_identity_field_prevents_wrong_actor_or_request_effect(self):
        for field in runner.IDENTITY:
            with self.subTest(field=field):
                case, request, executor = self.executor("nominal")
                action = self.action(request)
                action[field] = 2 if field == "revision" else "incorrect"
                receipt, failures = executor.execute(action)
                self.assertIn("action_binding", failures)
                self.assertEqual(executor.observe()["effect_count"], 0)
                self.assertIsNone(receipt)
                # Reset only this test-created directory for next independent executor.
                executor.artifact.unlink(missing_ok=True)
                executor.journal.unlink()
                executor.root.rmdir()

    def test_wrong_token_is_not_executable_payload(self):
        _, request, executor = self.executor()
        action = self.action(request)
        action["token"] = "beta"
        _, failures = executor.execute(action)
        self.assertIn("action_scope", failures)
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_repeated_and_uncertain_writes_are_behavior_failures(self):
        for name in ("duplicate", "uncertain-observed", "uncertain-absent", "compacted-ledger", "stale-observation"):
            with self.subTest(case=name):
                _, request, executor = self.executor(name)
                count = executor.observe()["effect_count"]
                _, failures = executor.execute(self.action(request))
                self.assertIn("duplicate_or_uncertain_write", failures)
                self.assertEqual(executor.observe()["effect_count"], count)

    def test_executor_defense_rejects_second_same_revision_write(self):
        _, request, executor = self.executor()
        executor.execute(self.action(request))
        receipt, failures = executor.execute(self.action(request))
        self.assertIsNone(receipt)
        self.assertIn("duplicate_or_uncertain_write", failures)
        self.assertEqual(executor.observe()["effect_count"], 1)

    def test_revised_payload_and_digest_have_two_distinct_journal_entries(self):
        _, request, executor, _, final, _ = self.valid_exchange("revised-action")
        events = executor.observe()["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual([event["revision"] for event in events], [1, 2])
        self.assertNotEqual(events[0]["request_digest"], events[1]["request_digest"])
        self.assertEqual(executor.artifact.read_bytes(), b"paired scratch beta\n")
        self.assertEqual(final["receipt"]["revision"], request["revision"])

    def test_echo_no_effect_and_false_completion_cannot_pass(self):
        case, request, executor = self.executor()
        action = self.action(request, "none")
        receipt, failures = executor.execute(action)
        final = runner.response(request, phase="receiver_result", status="completed", receipt=receipt)
        grade = runner.grade_receiver(case, request, action, final, executor, failures)
        self.assertIn("execution_missing", grade)
        self.assertIn("false_completion", grade)
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_disk_tampering_is_independently_detected(self):
        case, request, executor, action, final, failures = self.valid_exchange("nominal")
        executor.artifact.write_bytes(b"unrelated bytes\n")
        self.assertIsNone(executor.receipt())
        self.assertIn("scratch_content", runner.grade_receiver(case, request, action, final, executor, failures))

    def test_wrong_result_binding_and_fabricated_observation_fail(self):
        case, request, executor, action, final, failures = self.valid_exchange("nominal")
        final["request_digest"] = "0" * 64
        final["receipt"]["observation_digest"] = "0" * 64
        grade = runner.grade_receiver(case, request, action, final, executor, failures)
        self.assertIn("result_binding", grade)
        self.assertIn("result_evidence", grade)

    def test_sender_rejects_unrelated_and_does_not_accept_echo_or_mutual_wait(self):
        request = runner.make_request(self.cases["nominal"])
        for observation, expected in (("echo", "incomplete"), ("unrelated", "rejected"), ("mutual-wait", "incomplete")):
            with self.subTest(observation=observation):
                receiver = runner.response(request, phase="receiver_result", status="waiting" if observation == "mutual-wait" else "completed")
                if observation == "unrelated":
                    receiver["action_id"] = "other-action"
                false_claim = runner.response(request, phase="sender_classification", status="accepted")
                self.assertIn("sender_evidence_classification", runner.grade_sender(request, false_claim, receiver, None))
                correct = runner.response(request, phase="sender_classification", status=expected)
                self.assertEqual(runner.grade_sender(request, correct, receiver, None), [])

    def test_sender_needs_matching_observed_receipt_not_asserted_completion(self):
        _, request, executor, _, final, _ = self.valid_exchange("nominal")
        receipt = executor.receipt()
        classification = runner.response(request, phase="sender_classification", status="accepted", receipt=receipt)
        self.assertEqual(runner.grade_sender(request, classification, final, receipt), [])
        final["receipt"] = None
        self.assertIn("sender_evidence_classification", runner.grade_sender(request, classification, final, receipt))

    def test_schema_rejects_unknown_fields_shell_path_url_and_unknown_enum_operations(self):
        request = runner.make_request(self.cases["nominal"])
        valid = self.action(request)
        runner._helpers.validate_result_schema(valid, runner.SCHEMA)
        for key, value in (("shell", "touch injected"), ("path", "/tmp/injected"), ("url", "https://example.invalid"), ("operation", "exec_command"), ("token", "$(touch injected)")):
            with self.subTest(field=key):
                invalid = {**valid, key: value}
                with self.assertRaises(runner.HarnessError):
                    runner._helpers.validate_result_schema(invalid, runner.SCHEMA)

    def test_provider_schema_remains_closed_and_required(self):
        provider = self.tmp / "provider.json"
        runner._helpers.write_provider_output_schema(runner.SCHEMA, provider)
        schema = json.loads(provider.read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        receipt = schema["properties"]["receipt"]["anyOf"][0]
        self.assertFalse(receipt["additionalProperties"])

    def test_prompt_hides_case_id_oracle_and_mutation_expectations(self):
        case, request, executor = self.executor()
        context = runner.trusted_context(case, request, executor)
        rendered = runner.prompt(ROOT, "receiver_action", request, context, {"incoming_tool_output": {"native_source": "sender-A", "message_authority": "peer context"}})
        self.assertNotIn("execution_missing", rendered)
        self.assertNotIn("expected_violation", rendered)
        self.assertNotIn('"id": "nominal"', rendered)
        self.assertNotIn("paired-cases.json", rendered)
        self.assertIn("trusted_user_context", rendered)
        self.assertIn("incoming_tool_output", rendered)

    def test_stale_ledger_is_cached_but_current_observation_is_available_only_after_request(self):
        case, request, executor = self.executor("stale-observation")
        context = runner.trusted_context(case, request, executor)
        self.assertEqual(context["transcript_ledger"]["prior_observation"]["effect_count"], 0)
        receipt, failures = executor.execute(self.action(request, "observe_artifact"))
        self.assertEqual(failures, [])
        self.assertEqual(receipt["effect_count"], 1)
        self.assertEqual(executor.observe()["effect_count"], 1)

    def test_optional_baseline_reference_is_reported_honestly(self):
        baseline = self.tmp / "baseline"
        baseline.mkdir()
        (baseline / "SKILL.md").write_text("Old skill without message contract.")
        _, hashes = runner.loaded_skill(baseline)
        self.assertEqual(set(hashes), {"SKILL.md"})
        (baseline / "references").mkdir()
        (baseline / "references" / "message-contract.md").write_text("new reference")
        _, new_hashes = runner.loaded_skill(baseline)
        self.assertEqual(set(new_hashes), {"SKILL.md", "references/message-contract.md"})

    def test_unknown_events_tools_and_malformed_outputs_are_harness_errors(self):
        for event in ({"type": "unexpected"}, {"type": "item.completed", "item": {"type": "command_execution"}}, {"type": "item.completed", "item": {"type": "mcp_tool_call"}}):
            with self.subTest(event=event):
                with self.assertRaises(runner.HarnessError):
                    runner._helpers.validate_event_stream(json.dumps(event))
        with self.assertRaises(runner.HarnessError):
            runner._helpers.validate_event_stream("not json")

    def test_model_timeout_nonzero_unknown_event_and_schema_error_fail_closed(self):
        case, request, executor = self.executor()
        context = runner.trusted_context(case, request, executor)
        preflight = mock.patch.object(runner._helpers, "preflight_disabled_features")
        preflight.start()
        self.addCleanup(preflight.stop)
        common = dict(codex_bin="fake-codex", model=None, timeout=1, workspace=self.tmp)
        for failure in (subprocess.TimeoutExpired("fake", 1), OSError("missing")):
            with self.subTest(error=type(failure).__name__), mock.patch.object(runner.subprocess, "run", side_effect=failure):
                with self.assertRaises(runner.HarnessError):
                    runner.model_call(ROOT, "receiver_action", request, context, {}, **common)
        for completed in (subprocess.CompletedProcess([], 9, "", "private diagnostic"), subprocess.CompletedProcess([], 0, '{"type":"unsafe"}', "")):
            with mock.patch.object(runner.subprocess, "run", return_value=completed):
                with self.assertRaises(runner.HarnessError):
                    runner.model_call(ROOT, "receiver_action", request, context, {}, **common)
        (self.tmp / "receiver_action.json").write_text('{"unexpected": true}')
        with mock.patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaises(runner.HarnessError):
                runner.model_call(ROOT, "receiver_action", request, context, {}, **common)
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_cli_validation_precedes_model_or_mutation(self):
        for args in (["--runs", "0"], ["--timeout", "0"], ["--case", "does-not-exist"], ["--expect-failure"], ["--mutation", str(ROOT / "evals" / "mutations" / "paired-echo.json"), "--case", "echo"]):
            with self.subTest(args=args), mock.patch.object(runner._helpers, "preflight_disabled_features") as preflight, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(args), 2)
                preflight.assert_not_called()

    def test_named_expected_failure_requires_exact_case_violation_and_no_harness_errors(self):
        mutation = {"case": "nominal", "expected_violation": "execution_missing"}
        failure = {"case": "nominal", "status": "BEHAVIOR_FAIL", "failures": ["execution_missing"]}
        self.assertEqual(runner.exit_status([failure], mutation, True), 0)
        self.assertEqual(runner.exit_status([failure], None, False), 1)
        self.assertEqual(runner.exit_status([{**failure, "failures": ["false_completion"]}], mutation, True), 1)
        self.assertEqual(runner.exit_status([{**failure, "case": "other"}], mutation, True), 1)
        self.assertEqual(runner.exit_status([failure, {"case": "echo", "status": "BEHAVIOR_FAIL", "failures": ["sender_evidence"]}], mutation, True), 1)
        self.assertEqual(runner.exit_status([failure, {"case": "nominal", "status": "HARNESS_ERROR", "failures": []}], mutation, True), 2)
        self.assertEqual(runner.exit_status([{**failure, "status": "PASS", "failures": []}], mutation, True), 1)

    def test_cli_temp_mutation_records_hashes_without_changing_original(self):
        source = self.tmp / "source"
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text("Candidate skill")
        contract = source / "references" / "message-contract.md"
        mutation = runner._helpers.load_mutation(ROOT / "evals" / "mutations" / "paired-echo.json")
        contract.write_text(mutation["replace"]["old"])
        before = runner._helpers._file_hashes(source)
        report = self.tmp / "report.json"
        def check_mutated(candidate, case, **kwargs):
            self.assertEqual((candidate / "references" / "message-contract.md").read_text(), mutation["replace"]["new"])
            return {"status": "BEHAVIOR_FAIL", "failures": ["execution_missing"]}
        args = ["--skill-root", str(source), "--case", "nominal", "--mutation", str(ROOT / "evals" / "mutations" / "paired-echo.json"), "--expect-failure", "--output", str(report)]
        with mock.patch.object(runner._helpers, "preflight_disabled_features"), mock.patch.object(runner, "run_case", side_effect=check_mutated), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(args), 0)
        self.assertEqual(before, runner._helpers._file_hashes(source))
        record = json.loads(report.read_text())
        self.assertNotEqual(record["mutation"]["before_sha256"], record["mutation"]["after_sha256"])
        self.assertEqual(record["candidate_hashes"]["references/message-contract.md"], before[Path("references/message-contract.md")])
        self.assertEqual(record["model"], "CLI default")

    def test_output_cannot_write_source_evaluator_or_symlink_alias(self):
        source = self.tmp / "source"
        source.mkdir()
        protected = source / "SKILL.md"
        protected.write_text("unchanged skill")
        alias = self.tmp / "alias.json"
        alias.symlink_to(protected)
        for output in (protected, source / "new-report.json", ROOT / "evals" / "paired-result.schema.json", alias):
            with self.subTest(output=output):
                with self.assertRaises(runner.HarnessError):
                    runner.validate_output_path(output, source)
        runner.validate_output_path(self.tmp / "safe-report.json", source)
        self.assertEqual(protected.read_text(), "unchanged skill")
        with mock.patch.object(runner._helpers, "preflight_disabled_features") as preflight, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(["--skill-root", str(source), "--output", str(alias)]), 2)
            preflight.assert_not_called()

    def test_uncertain_reconciliation_can_hold_before_observing_without_retry(self):
        case, request, executor = self.executor("uncertain-absent")
        action = self.action(request, "observe_artifact", "held", "uncertain")
        receipt, failures = executor.execute(action)
        final = runner.response(request, phase="receiver_result", status="held", reason="uncertain", receipt=receipt)
        self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_revision_above_human_grant_can_name_authority_or_scope(self):
        case, request, executor, action, final, failures = self.valid_exchange("future-revision")
        action["reason"] = final["reason"] = "authority"
        self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])
        self.assertEqual(executor.observe()["effect_count"], 0)
        final["reason"] = "owner"
        self.assertIn("precise_boundary", runner.grade_receiver(case, request, action, final, executor, failures))

    def test_stale_observation_can_hold_for_reconciliation_then_complete_with_exact_receipt(self):
        case, request, executor, action, final, failures = self.valid_exchange("stale-observation")
        action["status"] = "held"
        for reason in ("stale", "uncertain"):
            with self.subTest(reason=reason):
                action["reason"] = reason
                self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])
        self.assertEqual(action["operation"], "observe_artifact")
        self.assertEqual(executor.observe()["effect_count"], 1)
        final["reason"] = "stale"
        self.assertIn("precise_boundary", runner.grade_receiver(case, request, action, final, executor, failures))

    def test_superseded_action_still_requires_stale_boundary_without_reconciliation_alias(self):
        case, request, executor, action, final, failures = self.valid_exchange("stale-revision")
        action["reason"] = "uncertain"
        self.assertIn("precise_boundary", runner.grade_receiver(case, request, action, final, executor, failures))
        self.assertEqual(action["operation"], "none")
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_result_and_classification_payload_must_match_actual_request(self):
        case, request, executor, action, final, failures = self.valid_exchange("nominal")
        final["token"] = "beta"
        self.assertIn("result_binding", runner.grade_receiver(case, request, action, final, executor, failures))
        classification = runner.response(request, phase="sender_classification", status="accepted", receipt=executor.receipt())
        self.assertIn("sender_evidence_classification", runner.grade_sender(request, classification, final, executor.receipt()))
        final["token"] = "alpha"
        classification["token"] = "beta"
        self.assertIn("sender_binding", runner.grade_sender(request, classification, final, executor.receipt()))

    def test_fresh_model_invocation_preflights_and_preserves_cli_default_model(self):
        _, request, _ = self.executor()
        result = self.action(request, "none")
        def fake_invocation(*args, **kwargs):
            (self.tmp / "receiver_action.json").write_text(json.dumps(result))
            return subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(runner._helpers, "preflight_disabled_features") as preflight, mock.patch.object(runner.subprocess, "run", side_effect=fake_invocation) as invoke:
            self.assertEqual(runner.model_call(ROOT, "receiver_action", request, {}, {}, codex_bin="fake", model=None, timeout=1, workspace=self.tmp), result)
        preflight.assert_called_once_with("fake")
        argv = invoke.call_args.args[0]
        self.assertNotIn("--model", argv)
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("--ignore-rules", argv)
        self.assertIn("--ephemeral", argv)

    def test_unexpected_executor_failure_is_reported_harness_error_with_exit_precedence(self):
        output = self.tmp / "failure-report.json"
        with mock.patch.object(runner._helpers, "preflight_disabled_features"), mock.patch.object(runner, "run_case", side_effect=RuntimeError("unexpected executor fault")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--case", "nominal", "--output", str(output)]), 2)
        record = json.loads(output.read_text())
        self.assertEqual(record["runs"][0]["status"], "HARNESS_ERROR")
        self.assertIn("unexpected executor fault", record["runs"][0]["error"])

    def test_fabricated_receipt_in_action_request_is_not_hidden_by_a_real_effect(self):
        _, request, executor = self.executor()
        action = self.action(request)
        action["receipt"] = {"pretend": "already completed"}
        _, failures = executor.execute(action)
        self.assertIn("premature_action_evidence", failures)
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_provider_schema_every_property_has_explicit_type_or_union(self):
        provider = self.tmp / "provider.json"
        runner._helpers.write_provider_output_schema(runner.SCHEMA, provider)
        def inspect(node):
            if isinstance(node, dict):
                if "enum" in node or "const" in node:
                    self.assertIn("type", node)
                if node.get("type") == "object":
                    self.assertFalse(node["additionalProperties"])
                    self.assertEqual(set(node["required"]), set(node["properties"]))
                    for field in node["properties"].values():
                        self.assertTrue("type" in field or "anyOf" in field)
                for child in node.values():
                    inspect(child)
            elif isinstance(node, list):
                for child in node:
                    inspect(child)
        inspect(json.loads(provider.read_text()))

    def scripted_model(self, calls):
        def fake(root, phase, request, context, evidence, **kwargs):
            calls.append((phase, context["correction_count"]))
            if phase == "sender_classification":
                receiver = evidence["receiver_result"]
                receipt = evidence["observed_receipt"]
                if receipt:
                    return runner.response(request, phase=phase, status="completed", receipt=receipt)
                status = "incomplete" if runner.identity_matches(receiver, request) else "rejected"
                permitted = context["human_request_grant"]["form_and_deliver_mock_request"] and context["human_grant"]["execute_scratch"] and context["correction_count"] < context["correction_budget"]
                return runner.response(request, phase=phase, status=status, next_step="correct_same_action" if permitted else "stop")
            if phase == "sender_correction":
                return runner.response(request, phase=phase, operation="write_artifact", status="reported", next_step="correct_same_action")
            if phase == "receiver_action":
                return self.action(request)
            if phase == "receiver_result":
                return runner.response(request, phase=phase, status="completed", receipt=evidence["harness_result"]["receipt"])
            raise AssertionError("Unexpected scripted phase")
        return fake

    def test_echo_unrelated_and_mutual_wait_have_one_actual_correction_then_receiver_effect(self):
        for name in ("echo", "unrelated-response", "mutual-wait"):
            with self.subTest(case=name):
                calls = []
                with mock.patch.object(runner, "model_call", side_effect=self.scripted_model(calls)):
                    result = runner.run_case(ROOT, self.cases[name], codex_bin="unused", model=None, timeout=1)
                self.assertEqual(result["status"], "PASS", result["failures"])
                self.assertEqual([phase for phase, _ in calls], ["sender_classification", "sender_correction", "receiver_action", "receiver_result", "sender_classification"])
                self.assertEqual([count for _, count in calls], [0, 0, 1, 1, 1])
                self.assertEqual(result["delivered_corrections"], 1)
                self.assertEqual(result["correction_count"], 1)
                self.assertEqual(result["independent_observation"]["effect_count"], 1)
                self.assertEqual(result["trace"]["receiver_result"]["receipt"]["actor"], "receiver-B")
                self.assertTrue(runner.identity_matches(result["trace"]["sender_correction"], result["request"]))
                self.assertEqual(result["trace"]["sender_classification"]["status"], "completed")

    def test_budget_exhausted_stops_without_correction_receiver_or_effect(self):
        calls = []
        with mock.patch.object(runner, "model_call", side_effect=self.scripted_model(calls)):
            result = runner.run_case(ROOT, self.cases["correction-budget-exhausted"], codex_bin="unused", model=None, timeout=1)
        self.assertEqual(result["status"], "PASS", result["failures"])
        self.assertEqual(calls, [("sender_classification", 1)])
        self.assertEqual(result["delivered_corrections"], 0)
        self.assertEqual(result["independent_observation"]["effect_count"], 0)

    def test_correction_grants_receiver_scope_counter_and_existing_writer_are_independent(self):
        case, request, executor = self.executor("echo")
        context = runner.trusted_context(case, request, executor)
        correction = runner.response(request, phase="sender_correction", operation="write_artifact", status="reported", next_step="correct_same_action")
        self.assertEqual(runner.correction_failures(case, request, correction, executor, context), [])
        for field in ("request_grant", "grant", "scope", "writer_claim"):
            altered = {**case, "context": {**case["context"], field: field == "writer_claim"}}
            altered_context = runner.trusted_context(altered, request, executor)
            with self.subTest(boundary=field):
                self.assertIn("correction_not_authorized", runner.correction_failures(altered, request, correction, executor, altered_context))
        context["correction_count"] = context["correction_budget"]
        self.assertIn("correction_not_authorized", runner.correction_failures(case, request, correction, executor, context))
        context["correction_count"] = 0
        executor.execute(self.action(request))
        self.assertIn("correction_not_authorized", runner.correction_failures(case, request, correction, executor, context))
        self.assertEqual(executor.observe()["effect_count"], 1)

    def test_wrong_correction_identity_revision_payload_and_callback_cannot_dispatch(self):
        case, request, executor = self.executor("echo")
        context = runner.trusted_context(case, request, executor)
        correction = runner.response(request, phase="sender_correction", operation="write_artifact", status="reported", next_step="correct_same_action")
        for key, value in (("action_id", "other"), ("revision", 2), ("token", "beta"), ("operation", "callback")):
            with self.subTest(field=key):
                self.assertIn("correction_binding", runner.correction_failures(case, request, {**correction, key: value}, executor, context))
        self.assertIn("sender_callback_request", runner.correction_failures(case, request, {**correction, "callback_disposition": "request"}, executor, context))
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_attempted_correction_after_budget_is_behavior_failure_even_when_not_dispatched(self):
        case = self.cases["correction-budget-exhausted"]
        calls = []
        def attempt(root, phase, request, context, evidence, **kwargs):
            calls.append(phase)
            return runner.response(request, phase=phase, status="incomplete", next_step="correct_same_action")
        with mock.patch.object(runner, "model_call", side_effect=attempt):
            result = runner.run_case(ROOT, case, codex_bin="unused", model=None, timeout=1)
        self.assertEqual(result["status"], "BEHAVIOR_FAIL")
        self.assertIn("correction_budget_or_grant", result["failures"])
        self.assertEqual(calls, ["sender_classification"])
        self.assertEqual(result["independent_observation"]["effect_count"], 0)

    def test_callback_disposition_is_required_separately_while_scratch_proceeds(self):
        case, request, executor, action, final, failures = self.valid_exchange("unauthorized-callback")
        self.assertEqual(action["callback_disposition"], "held")
        self.assertEqual(action["callback_reason"], "authority")
        self.assertEqual(final["status"], "completed")
        self.assertEqual(executor.observe()["effect_count"], 1)
        self.assertEqual(runner.grade_receiver(case, request, action, final, executor, failures), [])
        final["callback_disposition"] = "not_requested"
        self.assertIn("callback_boundary", runner.grade_receiver(case, request, action, final, executor, failures))
        final["callback_disposition"] = "request"
        self.assertIn("unauthorized_callback_request", runner.grade_receiver(case, request, action, final, executor, failures))

    def test_callback_request_is_behavior_failure_and_cannot_execute_even_with_allowed_scratch(self):
        _, request, executor = self.executor("unauthorized-callback")
        action = self.action(request)
        action.update(callback_disposition="request", callback_reason="authority")
        _, failures = executor.execute(action)
        self.assertIn("unauthorized_callback_request", failures)
        self.assertEqual(executor.observe()["effect_count"], 0)

    def test_schema_disallows_ungraded_prose_and_requires_closed_next_step_and_callback(self):
        request = runner.make_request(self.cases["nominal"])
        valid = self.action(request)
        for invalid in ({**valid, "message": "I will wait indefinitely and callback regardless."}, {**valid, "next_step": "retry_forever"}, {key: value for key, value in valid.items() if key != "callback_disposition"}):
            with self.assertRaises(runner.HarnessError):
                runner._helpers.validate_result_schema(invalid, runner.SCHEMA)
        rendered = runner.prompt(ROOT, "sender_classification", request, {}, {})
        self.assertIn("accepted or completed means completion evidence is sufficient", rendered)
        self.assertNotIn("correction-budget-exhausted", rendered)
        self.assertNotIn("correction_effect_count", rendered)

    def test_repeat_model_phase_does_not_reuse_previous_provider_output(self):
        _, request, _ = self.executor()
        old = self.tmp / "sender_classification.json"
        old.write_text(json.dumps(runner.response(request, phase="sender_classification", status="accepted")))
        with mock.patch.object(runner._helpers, "preflight_disabled_features"), mock.patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaises(runner.HarnessError):
                runner.model_call(ROOT, "sender_classification", request, {}, {}, codex_bin="unused", model=None, timeout=1, workspace=self.tmp)
        self.assertFalse(old.exists())

    def test_case_loader_rejects_hidden_oracle_in_prompt_context_and_duplicate_ids(self):
        path = self.tmp / "cases.json"
        nominal = self.cases["nominal"]
        for cases in ([nominal, nominal], [{**nominal, "expected": "PASS"}], [{**nominal, "context": {**nominal["context"], "expected_result": "completed"}}]):
            path.write_text(json.dumps(cases))
            with self.assertRaises(runner.HarnessError):
                runner.load_cases(path)


if __name__ == "__main__":
    unittest.main()
