import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_behavioral_evals_provenance", ROOT / "scripts" / "run_behavioral_evals.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class BehavioralReportProvenance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skill = Path(self.temp.name) / "skill"
        (self.skill / "evals").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("skill content\n")
        (self.skill / "evals" / "evals.json").write_text('{"evals": []}\n')
        (self.skill / "evals" / "scenarios.json").write_text('{"schema_version": 1, "scenarios": []}\n')
        schema = {
            "type": "object",
            "properties": {
                "eval_id": {"type": "integer"},
                "decision": {"type": "string"},
                "planned_calls": {"type": "array"},
                "facts": {"type": "object", "properties": {}},
                "explanation": {"type": "string"},
            },
            "required": ["eval_id", "decision", "planned_calls", "facts", "explanation"],
        }
        (self.skill / "evals" / "result.schema.json").write_text(json.dumps(schema))
        self.result = {
            "eval_id": 1,
            "decision": "inspect",
            "planned_calls": [],
            "facts": {},
            "explanation": "simulation",
        }

    def execute(self, *, during_call=None):
        def fake_run(command, **_kwargs):
            if during_call:
                during_call()
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(self.result))
            return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n', stderr="")

        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run):
            return runner.run_once(
                installed_root=self.skill,
                catalog_entry={"id": 1, "prompt": "test"},
                scenario={"eval_id": 1, "checks": {}},
                codex_bin="codex",
                model=None,
                timeout=1,
                mutation=None,
                input_hashes={
                    "catalog_sha256": runner._sha256(self.skill / "evals" / "evals.json"),
                    "scenarios_sha256": runner._sha256(self.skill / "evals" / "scenarios.json"),
                },
            )

    def test_success_reports_installed_candidate_and_consumed_input_hashes(self):
        installed = runner._file_hashes(self.skill)

        outcome = self.execute()

        provenance = outcome["provenance"]
        self.assertEqual(provenance["installed_skill_sha256"], {str(path): digest for path, digest in installed.items()})
        self.assertEqual(provenance["candidate_skill_sha256"], provenance["installed_skill_sha256"])
        self.assertEqual(provenance["catalog_sha256"], installed[Path("evals/evals.json")])
        self.assertEqual(provenance["scenarios_sha256"], installed[Path("evals/scenarios.json")])
        self.assertEqual(provenance["result_schema_sha256"], installed[Path("evals/result.schema.json")])
        self.assertIsNone(provenance["mutation_config_sha256"])

    def test_changed_installed_tree_fails_instead_of_returning_false_provenance(self):
        def alter_installed_input():
            (self.skill / "SKILL.md").write_text("changed while evaluating\n")

        with self.assertRaisesRegex(runner.HarnessError, "installed skill changed during eval"):
            self.execute(during_call=alter_installed_input)

    def test_mutated_candidate_is_bound_to_post_mutation_bytes(self):
        mutation = {
            "id": "change-skill",
            "eval_id": 1,
            "target": "SKILL.md",
            "replace": {"old": "skill content", "new": "mutated content"},
            "expected_violation": "behavior change",
        }
        installed_digest = runner._sha256(self.skill / "SKILL.md")

        outcome = self.execute_mutated(mutation)

        provenance = outcome["provenance"]
        self.assertEqual(provenance["installed_skill_sha256"]["SKILL.md"], installed_digest)
        self.assertNotEqual(provenance["candidate_skill_sha256"]["SKILL.md"], installed_digest)
        self.assertEqual(provenance["candidate_skill_sha256"]["SKILL.md"], outcome["mutation"]["after_sha256"])
        self.assertEqual(outcome["mutation"]["before_sha256"], installed_digest)

    def execute_mutated(self, mutation):
        mutation_path = Path(self.temp.name) / "mutation.json"
        mutation_path.write_text(json.dumps(mutation))
        mutation_hashes = {}
        loaded_mutation = runner.load_mutation(mutation_path, mutation_hashes)
        def fake_run(command, **_kwargs):
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(self.result))
            return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n', stderr="")

        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run):
            return runner.run_once(
                installed_root=self.skill,
                catalog_entry={"id": 1, "prompt": "test"},
                scenario={"eval_id": 1, "checks": {}},
                codex_bin="codex",
                model=None,
                timeout=1,
                mutation=loaded_mutation,
                input_hashes={
                    "catalog_sha256": runner._sha256(self.skill / "evals" / "evals.json"),
                    "scenarios_sha256": runner._sha256(self.skill / "evals" / "scenarios.json"),
                    "mutation_config_sha256": mutation_hashes[mutation_path.name],
                },
            )

    def test_compact_report_preserves_per_run_provenance(self):
        provenance = {"catalog_sha256": "catalog-digest"}
        compact = runner.compact_report(
            {
                "schema_version": 1,
                "runs": [{"eval_id": 1, "run": 1, "status": "PASS", "failures": [], "mutation": None, "provenance": provenance}],
                "summary": {"total": 1},
            }
        )

        self.assertEqual(compact["runs"][0]["provenance"], provenance)

    def test_configuration_digest_is_for_the_exact_bytes_parsed(self):
        path = Path(self.temp.name) / "catalog.json"
        raw = b'{ "evals": [{"id": 1, "prompt": "x", "expected_output": "", "assertions": [], "files": []}] }\n'
        path.write_bytes(raw)
        hashes = {}

        self.assertEqual(runner.load_catalog(path, hashes)[0]["id"], 1)
        self.assertEqual(hashes[path.name], hashlib.sha256(raw).hexdigest())

    def test_copy_drift_is_rejected_before_model_execution(self):
        real_copytree = runner.shutil.copytree

        def altered_copy(*args, **kwargs):
            copied = real_copytree(*args, **kwargs)
            destination = args[1]
            (Path(destination) / "SKILL.md").write_text("copy drift\n")
            return copied

        with mock.patch.object(runner.shutil, "copytree", side_effect=altered_copy), mock.patch.object(
            runner.subprocess, "run"
        ) as model_call:
            with self.assertRaisesRegex(runner.HarnessError, "copied skill tree does not match"):
                runner.run_once(
                    installed_root=self.skill,
                    catalog_entry={"id": 1, "prompt": "test"},
                    scenario={"eval_id": 1, "checks": {}},
                    codex_bin="codex",
                    model=None,
                    timeout=1,
                    mutation=None,
                    input_hashes={
                        "catalog_sha256": runner._sha256(self.skill / "evals" / "evals.json"),
                        "scenarios_sha256": runner._sha256(self.skill / "evals" / "scenarios.json"),
                    },
                )
        model_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
