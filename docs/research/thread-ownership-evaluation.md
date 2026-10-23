# Thread ownership evaluation

The ordinary-message protocol separates a receiver's execution commitment from transport delivery,
observed activity and accepted completion. The bounded investigation found visible incoming requests
that were displaced by prior context or explicitly rejected as unrelated; another observation was
stale. Those observations did not establish that both participants believed the other owned execution.
The work and acceptance contract are recorded in [issue #4](https://github.com/iliaim/skills_ii/issues/4).

## Method and results

The [message contract](../../skills/agent-communication/references/message-contract.md) is the single
owner of ordinary-message processing. Delegation and orchestration retain their existing creation,
resource and acceptance rules. Incoming requests are checked against the receiver's existing
human/task authority; sender provenance and a request digest cannot create permission.

The separate paired runner uses fresh ephemeral Codex CLI invocations with tools disabled and closed
structured outputs. A validated mock operation produces real bytes in private harness scratch;
independent reads generate action-, revision-, actor- and payload-bound receipts. The model never
receives the grader or expected answers. Echo, unrelated-result and mutual-wait fixtures are synthetic
inputs, followed by a fresh sender correction and fresh receiver execution. They are not claimed as
model-generated original failures. An exhausted correction budget stops the exchange without effects.

The retained [synthetic evidence](thread-ownership-evidence.json), collected on 2026-09-30 with
Python 3.14.3 and Codex CLI 0.154.0 using its default model, records:

- 24 named scenarios passing, with three accepted runs each for nominal execution, echo recovery and
  mutual-wait recovery: 30 selected green runs.
- Explicit callback authority holds/refusals alongside permitted scratch completion; denied action
  requests are failures even when the executor prevents their effects.
- Replay, superseded and revised actions, uncertain results, conflicting payloads, compacted role
  context, stale observation, ownership release and writer-claim checks.
- A full accepted-work paragraph mutation yielding `BEHAVIOR_FAIL` with `execution_missing` and zero
  scratch effects, followed by three green nominal runs of the unmodified candidate.
- `python3 -m pytest -q skills`: 151 tests and 170 subtests passed. Skill Creator package validation
  passed for agent-communication, delegate-to-thread and orchestrate-threads.

The old skill's nominal case passed. An initial one-sentence mutation also passed because nearby
execution instructions remained. Neither is evidence of a detected failure; both controls are
retained. The effective mutation replaces the accepted-work paragraph only in a temporary copy, with
configuration and before/after hashes recorded. There is no claim of a reproduced pre-fix model failure.

Two valid initial traces were graded too narrowly: a revision beyond the human grant was held for
`authority` rather than `scope`, and a stale observation was held for reconciliation before an exact
completed receipt. The corrected grader admits those meanings only in their relevant contexts;
write prevention, superseded-revision rejection and final receipt checks remain strict. The original
grades are retained, regression tests cover the distinction, and fresh affected-case reruns pass.

A separate controlled internal-subagent exchange produced the requested 31-byte note. Root and a
cold reviewer independently read its content and SHA-256; after redelivery, bytes, hash and modification
time matched the initial observation. Receiver acceptance, execution and replay dispositions are
reported history preserved by root. These observations corroborate completion and no observed rewrite;
they do not independently establish the entire write history.

## Cold review corrections (2026-10-23)

The follow-up cold review found four evaluator defects: receiver prompts duplicated the requested
work outside the incoming message, report destinations could overwrite companion instructions,
preflight diagnostics could enter retained reports, and a refused write could create a scratch
effect before grading rejected it. The evaluator now obtains a receiver's assignment only from the
incoming wrapper, including its explicit request intent. Execution authority stays in separate trusted
context. Writes require an accepted disposition without a boundary; held observations remain valid
for authorized reconciliation.

Output checks preserve both the selected installation route and resolved source. They protect the
containing skill collection and checkout, including direct symlinked members, parent segments,
worktree Git markers, external source-reference aliases and hardlinks. An external standalone report
path remains usable. A preflight failure retains a fixed category instead of raw CLI diagnostics.

The new offline regressions fail against the pre-fix runner. The final suite passes 163 tests and
213 subtests. Code and security reviewers independently closed the findings; root inspected the
changes and ran the checks. The final fresh catalog passes all 24 scenarios, with three green runs
each for nominal execution, echo recovery and mutual-wait recovery: 30 green runs. Root independently
regraded those runs and both final red controls against real disposable scratch observations. The
fresh correction evidence is retained under `review_fix_validation` in the existing
[synthetic evidence](thread-ownership-evidence.json), separately from the historical September results.

An initial ignore-incoming policy mutation still passed and is retained as an ineffective control.
A direct control instead removes `incoming_tool_output` from both receiver phases while leaving
policy and trusted grants unchanged. It produces the named `execution_missing` behavior failure and
zero effects. The existing echo mutation also produces that failure with zero effects. Neither red
result is a harness error. Hand-authored provider doubles separately verify the real rendered input
boundary; they are not counted as fresh model runs.

The first catalog attempt exposed a real scope-denied receiver still requesting a write. The executor
blocked it and grading failed; the partial run was stopped. The interface now explicitly distinguishes
a receiver's actual execution request from the sender's desired operation. The final catalog and
repeat results recorded in the evidence use that clarified interface. Earlier failures and ineffective
controls are not recast as passes.

For a fresh missing-input control, run from the repository root with a compatible authenticated CLI
and an external report path:

```python
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

path = Path("skills/agent-communication/scripts/run_paired_evals.py")
spec = importlib.util.spec_from_file_location("paired", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
original = runner.model_call

def drop_incoming(root, phase, request, context, evidence, **kwargs):
    if phase in {"receiver_action", "receiver_result"}:
        evidence = {key: value for key, value in evidence.items()
                    if key != "incoming_tool_output"}
    return original(root, phase, request, context, evidence, **kwargs)

with patch.object(runner, "model_call", side_effect=drop_incoming):
    exit_code = runner.main(["--case", "nominal", "--output", "/tmp/paired-input-drop.json"])
run = json.loads(Path("/tmp/paired-input-drop.json").read_text())["runs"][0]
assert exit_code == 1 and run["status"] == "BEHAVIOR_FAIL"
assert "execution_missing" in run["failures"]
assert run["independent_observation"]["effect_count"] == 0
```

These remain controlled CLI/scratch results using the default model of Codex CLI 0.163.0.
They do not establish native transport reliability or a statistical provider success rate.

## Reproduction and limits

From the repository root, follow the [evaluation methodology](../../skills/agent-communication/references/eval-methodology.md#paired-senderreceiver-evaluations):

```sh
python3 -m pytest -q skills
python3 skills/agent-communication/scripts/run_paired_evals.py --runs 1 --output /tmp/paired-catalog.json
python3 skills/agent-communication/scripts/run_paired_evals.py \
  --case nominal --runs 1 --mutation skills/agent-communication/evals/mutations/paired-echo.json \
  --expect-failure --output /tmp/paired-red.json
python3 skills/agent-communication/scripts/run_paired_evals.py \
  --case nominal --case echo --case mutual-wait --runs 3 --output /tmp/paired-green.json
```

Reports stay outside the installed skill tree. Exit 0 on a red-control command means the named
behavior violation was observed; any harness error takes exit 2 precedence. Model-backed evaluations
are separate from offline CI and require an authenticated compatible CLI. Repeated invocations are
fresh contexts, not a statistical estimate of provider reliability.

These results establish controlled skill behavior and scratch effects. They do not establish native
app delivery reliability, real application side effects, provider compaction or distributed
exactly-once execution. The retained artifact contains synthetic structured evidence, not private
native transcripts, model reasoning or credentials. Source hashes identify each evaluated revision:
the September block remains historical and `review_fix_validation` records the corrected evaluator.
The original issue owns its delivery evidence; [PR #8](https://github.com/iliaim/skills_ii/pull/8)
records these follow-up corrections and verification.

## Native authorization and reporting follow-up

The October 23 follow-up tested actual local Codex tasks and native `send_message_to_thread`,
`read_thread` and `wait_threads`, separately from the CLI simulations above. The final scenario
consumed the contracts at `90f33097ed25279b397e64331d76e10d89cf99eb`. Raw native IDs,
transcripts, host paths and private receipts remain local; [PR #9](https://github.com/iliaim/skills_ii/pull/9)
records the delivered changes and checks.

Earlier attempts remain failures in the retained evidence. A setup-only attempt used unsupported
read limits and reacquired responses while changing their presentation. A subsequent exact replay
withheld its callback because the sender's original request required a later coordinator trigger
that the unchanged replay did not convey. Its prose-only duplicate notice also omitted required
report fields. One bounded correction verified recovery, but did not establish unassisted replay.
The contracts now retain scoped human evidence, show bounded native parsing and local reparsing,
preserve observable replay decisions, and require canonical fields for unsuccessful outcomes too.

The last scenario reused the same real pair under those clarified contracts. The coordinator
supplied setup and one dispatch, then sent no further participant messages:

- A sent an initial request, a byte-identical replay, then a same-revision conflicting payload
  changing only the first row value. B performed the initial work itself: five rows, total 13,
  with independently verified grouping and input digest.
- B sent exactly two direct callbacks. Their actual native receipts in A matched the outbound
  payloads. Initial and replay reports contained all eleven canonical terminal fields, valid
  recomputed digests, matching own-record JSON, and increasing revisions with supersession.
- B held the conflict without a third callback or artifact write. Its own held report retained
  all eleven fields and a valid digest. A independently verified the result and expected hold.
- Both artifacts retained their content, hash, size, inode and exact nanosecond modification time.
  No authorization reads, root corrections or acknowledgement sends occurred during this scenario;
  both tasks ended idle. Earlier authorization verification used two distinct human evidence reads per participant,
  one for the current request and one for the earlier grant, rather than one total read.

Cold review found no outstanding source findings. Offline validation passed 163 tests and 246
subtests; the completeness regression now authenticates valid baselines before removing each field
for complete, held, refused and duplicate reports. Three package validators and three extracted
provider-example response/error cases passed. The final native sequence is a bounded behavioral
check in retained contexts, not a fresh-context replication, a provider reliability estimate or a
proof of distributed exactly-once execution.
