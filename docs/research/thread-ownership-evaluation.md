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
native transcripts, model reasoning or credentials. Source hashes bind the evaluated policy and the
final evaluator implementation; the issue owns delivery and closure evidence.
