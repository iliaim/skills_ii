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
`2` means the harness could not establish a trustworthy result.

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

The red-control command succeeds only when the named expected violation is observed. A different
behavior failure or harness error is not mutation proof. Follow it with repeated green runs of the
unmodified skill.

## Add or change a case

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
