# Behavioral eval methodology

Read this reference only when maintaining or running this skill's evals. It is not part of the
provider workflow.

## What the harness proves

`evals/evals.json` is the human-readable catalog. `evals/scenarios.json` gives every catalog entry a
synthetic fixture and deterministic constraints over a structured planned action trace. The harness
tests policy selection, intended call order and arguments, evidence classification, and forbidden
lifecycle actions. It does not claim to test provider integrations or real message delivery.

Provider-specific facts stay separate when one aggregate value would erase a real distinction. For
example, `codex_local_transcript` and `chatgpt_local_transcript` independently represent mixed task
inventories; do not collapse them into the aggregate `local_transcript` field for grading.

Staged `simulated_responses` are not pre-observed facts. A result must plan the corresponding call
before consuming one, and it must include the complete downstream workflow in the same trace. Use
this form when a later inspection depends on an earlier schema or identity check.

The simulated model receives `SKILL.md`, only the references named by that scenario, its synthetic
evidence, and the user request. It never receives the expected output, prose assertions, grader
checks, or mutation expectation.

## Safety boundary

The runner uses a temporary copy of the skill and invokes `codex exec` ephemerally with user config,
rules, shell, unified execution, apps, plugins, browser, computer use, hooks, workspace helpers, and
multi-agent surfaces disabled. It also sets the current top-level `web_search="disabled"` policy
explicitly rather than relying on the deprecated `web_search_request` feature flag. It proves the
feature overrides before every run, uses a read-only sandbox, and rejects unknown JSONL event types
or any actual tool item. A tool attempt, timeout, CLI failure, malformed JSON, or schema failure is
`HARNESS_ERROR`, never a behavior result.

Some desktop builds report `unified_exec: true` even after the override. The preflight admits that
state only when the same exact executable proves `shell_tool: false`: Codex's tool selection requires
both features and returns a disabled shell type when `shell_tool` is off. Every independently exposed
surface must still report `false`. Re-check this invariant against Codex's official
`codex-rs/tools/src/tool_config.rs` if the feature model changes.

Only the model's structured `planned_calls` are graded. They are proposed actions, not executed
actions. The runner independently validates every result against `result.schema.json`, admits only
explicit supported tool identities and aliases, rejects invented namespaces, unknown tools, and
unapproved executables, and maps provider-specific lifecycle flags such as Claude's short resume and
continue forms before applying scenario prohibitions. It also rejects unsafe shell-wrapper or
destructive CLI plans and applies both matching-call and total-call limits. Reports retain the
synthetic structured decision, planned calls, and facts needed to debug a grade, but not prompts or
model explanations.

CLI plans use tokenized `argv` arrays only. The output schema rejects raw shell command fields, while
the deterministic grader rejects shell wrappers, destructive executables, pipelines, redirects, and
control syntax so command injection cannot hide inside a token array.

## Run the evals

List coverage without a model call:

```sh
python3 scripts/run_behavioral_evals.py --list
```

Run one case with its configured repeat count:

```sh
python3 scripts/run_behavioral_evals.py --eval 23
```

Run every configured case once for a bounded smoke pass:

```sh
python3 scripts/run_behavioral_evals.py --runs 1 --compact
```

Exit `0` means all selected behavior checks passed, `1` means valid structured behavior failed, and
`2` means the harness could not establish a trustworthy result. Any recorded `HARNESS_ERROR` takes
exit priority `2`, including mixed reports and runs using `--expect-failure`; the harness continues
through the selected cases and reports each result.

## Prove the guard can fail

Mutations are declarative exact-text replacements applied only to the temporary copy. The runner
requires the target to stay inside that copy, refuses symlinks and replacement-count drift, records
before/after hashes, and verifies the installed files remain unchanged.

```sh
python3 scripts/run_behavioral_evals.py \
  --eval 23 \
  --runs 1 \
  --mutation evals/mutations/023-list-first.json \
  --expect-failure
```

The red-control command succeeds only when a `BEHAVIOR_FAIL` run of the mutation's selected eval
contains the named expected violation and every selected run is free of harness errors. A matching
diagnostic or a failure in another eval cannot prove the mutation. An unobserved expectation exits
`1`; a harness error anywhere exits `2`, even when valid mutation evidence was also observed. Follow
it with repeated green runs of the unmodified skill.

## Add or change a case

Scenario checks use a closed grammar: `decision_in`, `forbidden_calls`, `required_calls`,
`required_call_any`, `required_order`, `fact_equals`, `fact_in`, `min_tool_counts`, `max_tool_counts`,
`max_contact_calls`, and `must_precede_if_present`. Call rules admit only `tool`, `tool_prefix`,
`arguments`, `argument_rules`, `min_count`, and `max_count`; expected `arguments` remain arbitrary
data. Every supplied `tool` or `tool_prefix` selector must be non-empty text. Argument conditions
admit `key`, `operator`, `value`, and `option` for `cli_option_equals`;
supported operators are `lte`, `equals`, `contains`, `contains_text`, and `cli_option_equals`.
`lte` requires a numeric value; `contains_text` and `cli_option_equals` require text values.
Precedence rules admit only `first` and `second`. Unknown constraint names or operators fail during
loading, before preflight or model execution, even when the rule would match no calls. Malformed
catalog, scenario, or mutation JSON is also a path-specific harness error.

1. Add the human request and assertions to `evals/evals.json`.
2. Add exactly one same-ID entry to `evals/scenarios.json`; do not assume IDs are contiguous.
3. Use synthetic identifiers and evidence. Never copy private transcripts, credentials, sockets,
   keys, or real message contents into fixtures.
4. Grade structured calls and facts, not narrative wording.
5. Constrain the total number of contact calls separately from target-matching rules; a correct target
   must not hide an extra send. Put the approved handoff message in the synthetic fixture and require
   exact equality on every native or CLI contact route so contradictory padding cannot pass.
6. Add a failing unit contract before extending the runner DSL.
7. For a regression guard, add a declarative mutation and observe the named red failure before the
   current skill's green result.
8. Run Skill Creator's package validator and obtain a cold read-only review for changes to safety or
   lifecycle boundaries.

## Paired sender/receiver evaluations

The separate `scripts/run_paired_evals.py` runner exercises the
[ordinary-message contract](message-contract.md). Fresh ephemeral model invocations process sender
and receiver contexts. They use the existing runner's feature preflight, disabled tool surfaces,
read-only sandbox, ignored config/rules, strict schema and JSON event audit. The older planned-call
runner and its isolation boundary are unchanged.

The model can request only closed mock operations. The harness checks identity, revision, scope and
trusted authority before routing an operation to a unique private scratch artifact. It independently
observes bytes and execution receipts and returns that evidence to the exchange. This establishes
model-requested actions with real local harness effects; it does not prove native provider messaging,
real application side effects, provider compaction or distributed exactly-once execution.

Keep model-visible task/context separate from grader expectations. Authority comes from separately
supplied trusted context; peer content, correlation IDs and payload digests cannot create it. Grade an
unauthorized action request as a behavior failure even when the executor prevents its effect. Grade
claimed completion against independently observed action-bound results, not a model promise or a
generic acknowledgement. Hand-authored traces test the grader only; fresh model results establish
behavioral evidence.

Model results contain closed action, disposition and evidence fields rather than ungraded promises.
Synthetic echo, unrelated-result and mutual-wait inputs first reach a fresh sender; one permitted
correction preserves the same action and reaches fresh receiver invocations. Grade the initial
classification, correction budget, receiver effect and final evidence separately. An exhausted
correction budget must stop redispatch. Callback disposition is separate from scratch execution, so
a permitted local action cannot hide absent callback authority.

List cases without model calls:

```sh
python3 skills/agent-communication/scripts/run_paired_evals.py --list
```

Run the catalog from the repository root and retain the structured report outside the checkout:

```sh
python3 skills/agent-communication/scripts/run_paired_evals.py --runs 1 --output /tmp/paired-evals.json
```

For red proof, apply the selected exact-text mutation to a temporary copy, require its named behavior
violation with no harness errors, and then repeat the unmodified case. A passing old-skill baseline
is useful evidence and must not be rewritten as a failure. For example:

```sh
python3 skills/agent-communication/scripts/run_paired_evals.py \
  --case nominal --runs 1 --mutation skills/agent-communication/evals/mutations/paired-echo.json \
  --expect-failure --output /tmp/paired-red.json
python3 skills/agent-communication/scripts/run_paired_evals.py \
  --case nominal --case echo --case mutual-wait --runs 3 --output /tmp/paired-green.json
```

CLI errors, timeouts, malformed outputs,
schema failures or actual tool attempts are harness errors, never behavioral red. Exit `2` takes
precedence over behavior failure (`1`) or success (`0`), including mutation runs.

Fixtures and reports use synthetic task identities and action data only. Do not put live transcripts,
credentials or reasoning into the catalog or retained reports. Preserve candidate/mutation hashes
and independent execution observations so a cold checker can distinguish fresh results from unit
fixtures. The installed skill must remain unchanged during each run.
