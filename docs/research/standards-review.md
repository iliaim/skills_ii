# Standards review and implemented improvements

Reviewed 2026-09-30 against baseline `e4e478b19c470431d53fde73b85a39b4eebcbd9a`.
Scope: all three skills, their provider/ownership contracts, Python evaluators, synthetic fixtures,
package structure, research references, and repository validation/delivery setup. This is a
source-grounded engineering review, not certification against a universal agent standard.

## Research and challenge process

The work used five ordered batches: research; repository challenge; improvement planning and
independent plan challenge; implementation; independent review and verification. Nine native
subagents covered packaging, evaluation practices, orchestration practices, three corresponding
repository challenges, planning, plan challenge, and harness implementation. Six research/challenge
agents used Luna. A native agent-thread limit prevented additional native agents or follow-up turns.
Two further independent reviewer roles ran through isolated ephemeral Codex CLI processes: three
harness reviews and two contract/maintenance reviews. Thus the work used eleven agent roles across
fourteen successful agent runs. The CLI account rejected Luna, so those reviewers used its configured
default model. Failed model attempts are excluded from those counts.

Reviewers received source snapshots as untrusted data, had no enabled tool surfaces, and returned
schema-validated findings bound to the snapshot digest. The integration owner reproduced actionable
findings, inspected all diffs, and ran verification independently. Source reviews did not count as
runtime proof. Review repairs stayed in the bounded implementation scope.

Primary-source research and applicability distinctions:

- [Skill format and authoring](skill-standards.md): Agent Skills specification and official OpenAI
  authoring/distribution guidance. Packaging requirements were distinguished from routing advice.
- [Evaluation standards](evaluation-standards.md): Python process/JSON semantics, JSON Schema,
  OpenAI structured output/evaluation guidance, pytest reliability, and GitHub Actions practices.
- [Orchestration standards](orchestration-standards.md): authorization, provenance, untrusted inputs,
  bounded concurrency, observation, and ambiguous side effects. Durable-workflow patterns were used
  as analogies, never as provider guarantees or new policy requirements.

## Findings and dispositions

| Priority | Confirmed opportunity | Implemented result |
| --- | --- | --- |
| P1 | Harness diagnostics could count as mutation proof; another eval's failure could also qualify. | Require the selected eval's valid `BEHAVIOR_FAIL` and named violation. Any harness error takes exit-code priority `2`, including mixed runs. |
| P1 | Malformed event/configuration shapes escaped error classification; prefix-only bounds could crash grading. | Validate JSON roots, event/item shapes, mutation objects, selector/operand types, and report prefix count failures normally. Malformed configuration yields a path-specific harness error before execution. |
| P1 | Misspelled scenario constraints were silently ignored. | Close the existing check, call-rule, argument-condition, and precedence vocabularies; validate operators before preflight. Expected argument data remains arbitrary. |
| P1 | The temporary provider schema did not require every nested object property. | Recursively require and close the current provider object schemas, including nullable `hostId`. The generic schema remains unchanged. This follows [OpenAI's strict schema requirements](https://developers.openai.com/api/docs/guides/structured-outputs). |
| P1 | Coordination evidence and rubric implied authority from skill invocation despite the existing caller-ownership contract. | Bind the coordinated fixture and negative control to explicit typed user coordination intent; retain create-only and orchestrator handoff semantics. |
| P1 | The admission oracle could consume discovery evidence before its release operation. | Check actual operation occurrence, arguments, release-before-admission, and declared partial order. A cloud read explicitly selects its observation/bound evidence; later terminal evidence is checked separately. Invalid dependency IDs fail closed. |
| P2 | A fresh environment lacked declared test dependencies and a reliable root validation command. | Add pinned existing dev dependencies, a README recipe, cache ignores, and an offline Actions job with read-only permissions, finite timeout, verified full-SHA official actions, and no persisted checkout credentials. |
| P2 | Two research links targeted an absent writing-goals package. | Mark the historical reference as external/unbundled and link the included orchestration contract. |

The original safety boundaries were largely strong: exact task identity, separate authorization and
technical capability, ambiguous-creation no-retry rules, writer ownership, bounded fan-out,
observation/acceptance separation, and synthetic right-reason controls. No normative skill entrypoint
or runtime ownership contract needed rewriting.

Recommendations not adopted:

- Shortening discovery descriptions: no demonstrated routing failure; all three packages validate.
- Additional generic taint wording: existing untrusted-source and authority boundaries already cover
  the identified concern. Duplicating the rules would create another normative source.
- Strict duplicate-key/NaN decoding: advisory compatibility work, not needed for the reproduced bugs.
- Runtime locks/controllers, retry infrastructure, arbitrary concurrency numbers, or new providers:
  not justified for an instruction/contract collection.
- Plugin manifests, publication metadata, or license selection: distribution/product choices outside
  the demonstrated repair scope.
- Portable packaging validation in CI: the installed authoring validator was run separately; the
  new repository gate promises offline Python contract coverage only.

## Verification evidence

Baseline: `python3 -m pytest -q -p no:cacheprovider` passed 90 tests and 45 subtests. A fresh venv
without system packages initially lacked pytest; root unittest discovery collected zero tests.

After installing only `requirements-dev.txt` into `/tmp/skills-ii-fresh-venv`:

```sh
/tmp/skills-ii-fresh-venv/bin/python -m pytest -q skills
/tmp/skills-ii-fresh-venv/bin/python skills/agent-communication/scripts/run_behavioral_evals.py --list
git diff --check
```

Results: 108 tests and 95 subtests passed with no skips; the listing returned all 36 eval IDs;
the diff check passed. New regressions were also run against isolated baseline source before repair:
the initial harness regressions produced 29 failing test/subtest instances, the coordination grant
regression failed both false/missing-grant subcases, and review-discovered malformed-input/admission
paths were reproduced before their fixes. The final mixed-null selector regression failed both
subcases before selector validation and passes afterward.

All three packages passed the installed Skill Creator validator separately:

```sh
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/agent-communication
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/delegate-to-thread
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/orchestrate-threads
```

That environment includes PyYAML; it is not an undeclared requirement of the repository's pytest gate.
Workflow triggers, permissions, timeout, action pins, credential settings, README command agreement,
and changed relative Markdown links were checked locally. Remote CI execution is reported in the PR.

The three `SKILL.md` files and generic result schema remain byte-identical to baseline. The generic
schema SHA-256 is `223244b4370dc6e2e2307102be95877cc2e36e1372be57ccd42c7d063bc258dc`.
Delegate catalog populations remain 26 cases/64 controls, 3 observation variants/6 controls, and
12 prompt variants. Case IDs and partial-order ratchets are unchanged; only the deliberately renamed
coordination-control IDs change their control digest. No controls were removed.

Final independent source reviews returned no actionable findings:

- Harness snapshot: `16bec3cd5d4ccbc605c6aaa619deb7db7ff66d22deeb6c38f28404d78e2fcd4e`.
- Contract/maintenance snapshot: `03de447164bd6667bc9ff086073fe2857b119a8663f62955ad63294d944e51bc`.

Limits: the reviews were source-only. Offline tests, schema invariants, and fake-process tests verify
the contract/harness behavior; they do not prove real provider delivery, task creation, or model
stability. No live behavioral evaluation was run. The repository's GitHub plan did not expose branch
protection, so no protection settings were changed. Dependency/action installation remains dependent
on ordinary package and GitHub availability.
