# Behavioral evaluation rubric

Evaluate fresh dry-run outputs against `cases.json`. Never execute a real task lifecycle operation.

## Fixture and provenance protocol

The fixture union is closed:

- `host_user_event` records request, authorization, correction, or commitment facts. It uses
  `available_at` and `event`; it is never a tool result.
- `contract_snapshot` records the decision-bearing live operation description, input paths, and
  normalized result paths at a named revision. It uses `available_at` and `snapshot`.
- `tool_result` is the `decoded-domain-payload-v1` payload released only after its matching
  operation and argument subset. Every decision-bearing raw path cites a contract-snapshot fixture.
- `transport_or_tool_failure` records failure kind and stable identity separately from domain
  payloads; it can never prove that creation did not occur.

Every `capability_evidence` entry is derived. Each premise resolves to an existing fixture ID and
exact JSON path. Missing or unknown paths, request prose, `initial_state`, and locally coined raw
fields are not evidence. Contract snapshots and host events are visible only at their declared
`available_at`; results and failures are visible only after `release_after`.

Each negative control is executable data. Each `indeterminate_variants` entry is also evaluated and must preserve `max_create_calls: 1`. Apply each negative control's single structured mutation to the named existing
target, recompute dependent evidence, and require the named criterion and assertion to fail with the
stated reason code. The unmutated baseline must pass first.

## Ownership-mode semantic cases

Evaluate every `ownership_mode_cases` entry as a read-only semantic simulation in addition to the
live applicability matrix. These cases distinguish three outcomes that all use the same one-task
creation contract:

- independent create-only returns truthful creation evidence and ownership without observation;
- coordinated-single leaves supported observation and delegated acceptance with
  `delegate-to-thread`; and
- coordinator creation handoff returns creation evidence without observation to the governing
  `orchestrate-threads` run, after which `agent-communication` may operate only on a real exact ID.

Require every listed semantic and reject every forbidden semantic. Across all modes,
`delegate-to-thread` remains the sole creator and one logical delegation permits one creation call.
The coordinator-handoff prompt contains the child execution contract, not graph state, acceptance
rollup, cursors, observer bounds, or polling mechanics. These semantic cases supplement rather than
alter the live-case applicability matrix.

## Attached reporting and recovery controls

For every `coordinated-single` or coordinator-handoff prompt, require the child-facing reporting
module from the task contract. The first message must name the checkpoint triggers and the required
checkpoint fields (`child_id`, `report_revision`, `report_identity_or_digest`, `observed_at`, `execution_state`, `task_liveness`,
`progress_kind`, `evidence_refs`, `blocker_or_decision`, and `next_gate`) plus the canonical terminal
report fields (`outcome`, `delivered_artifact`, `acceptance_map`, `checks_and_observed_results`,
`residual_risks`, `unmet_requirements`, `availability`, `report_revision`, `report_identity_or_digest`, and `supersedes`).
Missing report fields fail acceptance and cannot unlock a dependant. Independent create-only prompts
remain exempt when no parent consumes intermediate evidence.

Grade liveness, observation health, progress, acceptance, availability, and routeability independently.
A live/no-progress observation, a delivered attention response without a later child acknowledgement,
an ambiguous creation result, stale or superseded dependency evidence, a wrong artifact revision, or an
overlapping/unknown resource claim must fail closed. A creation timeout is never proof of rejection and
never permits a duplicate create. A resource claim is a protocol assertion, not a real lock unless a
named runtime enforces it.

## Criteria and applicability

| ID | Applies when | Observable invariant |
|---|---|---|
| R1-route | Every live case | Route matches expected_route; operations from another route are absent; explicit meta-review, no-create, and dry-run intent suppress creation even when the request contains execution-shaped content. |
| R2-create-authority | expected_route == create | A staged host_user_event explicitly authorizes one separate task before creation; an explicit `$delegate-to-thread` invocation counts only when it carries an execution objective and is not qualified by explicit meta-review, no-create, or dry-run intent. |
| R3-live-discovery | Discovery fixtures exist | Identifiers and state originate from released tool payloads or typed host events; titles and summaries never select identity. |
| R4-execution-contract | A create operation is permitted | The actual `create_thread.args.prompt` semantically preserves the compact core and every applicable conditional module from staged task facts; it omits secrets, copied durable bodies, and parent-only observation mechanics. |
| R5-destination-safety | Git or direct-local state is relevant | Nested target arguments are live-valid; direct-local requires the four-part exclusive interval and never task-list absence alone. |
| R6-cloud-sources | A cloud case has required sources | Destination access and transfer authority are independent staged predicates. |
| R7-create-result | Creation, queueing, or failure is exercised | Ready/queued outcomes and every declared timeout/transport/malformed/generic-error indeterminate variant obey identity and the one-call creation rule. |
| R8-coordination | observation is terminal, bounded-best-effort, create-only, or coordinator handoff | Explicit delegation defaults to the strongest supported observation mode, while explicit independent ownership return selects create-only and does not incur an unsolicited wait; coordinator handoff also performs no delegate-owned observation but returns creation evidence to the governing orchestrator rather than returning independent ownership; terminal coordination requires a terminal/attention waiter; snapshot-only ChatGPT Work uses an explicitly accepted finite bound and never silently promises completion; arguments match the live schema, unsupported/queued states never silently downgrade, and no visible message, title lookup, repeated read, notification, or heartbeat is invented as a callback. |
| R9-progress | Progress or observation fixtures exist | Checkpoint, attention, terminal, unchanged timeout, new-user-input interruption, and per-target error remain distinct; only meaningful changed or terminal snapshots are reported, bounds and cursor semantics hold, and errors or parent steering cannot be misclassified as child completion. |
| R10-parent-authority | Child or internal evidence exists | Child terminal evidence is mapped to parent acceptance and never expands lifecycle authority. |

## Applicability matrix

`A` means evaluate as PASS or FAIL; `N/A` means the predicate is false. This is the sole live-case
applicability source. Derive the row set from `cases.json` and the column set from the criteria;
reject missing, extra, or duplicate rows or columns without pinning counts.

| Case | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `git-project-default-worktree` | A | A | A | A | A | N/A | A | A | N/A | N/A |
| `explicit-uncommitted-state` | A | A | A | A | A | N/A | A | A | N/A | N/A |
| `shared-local-writer-conflict` | A | A | A | N/A | A | N/A | N/A | A | N/A | N/A |
| `direct-local-exclusivity-unknown` | A | A | A | N/A | A | N/A | N/A | A | N/A | N/A |
| `direct-local-user-exclusive-window` | A | A | A | A | A | N/A | A | A | N/A | N/A |
| `projectless-research` | A | A | A | A | N/A | N/A | A | A | N/A | N/A |
| `cloud-source-accessible` | A | A | A | A | N/A | A | A | A | N/A | N/A |
| `cloud-source-unconsented` | A | A | A | N/A | N/A | A | N/A | A | N/A | N/A |
| `cloud-authorized-but-inaccessible` | A | A | A | N/A | N/A | A | N/A | A | N/A | N/A |
| `existing-task-continuation` | A | N/A | A | N/A | N/A | N/A | N/A | N/A | A | A |
| `material-target-ambiguity` | A | N/A | A | N/A | N/A | N/A | N/A | A | N/A | N/A |
| `project-selection-refresh-before-create` | A | A | A | A | A | N/A | A | A | N/A | N/A |
| `queued-setup-create-only` | A | A | A | A | N/A | N/A | A | A | N/A | N/A |
| `coordinated-queued-result` | A | A | A | A | N/A | N/A | A | A | N/A | N/A |
| `coordinated-ready-codex` | A | A | A | A | N/A | N/A | A | A | A | A |
| `explicit-skill-create-only-ready` | A | A | A | A | N/A | N/A | A | A | N/A | N/A |
| `explicit-skill-execution-dry-run` | A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| `explicit-skill-execution-no-create` | A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| `coordinated-ready-codex-needs-attention` | A | A | A | A | N/A | N/A | A | A | A | A |
| `cloud-completion-required-unsupported` | A | N/A | A | N/A | N/A | N/A | N/A | A | N/A | N/A |
| `bounded-ready-cloud-supported` | A | A | A | A | N/A | N/A | A | A | A | A |
| `native-no-create-guarantee-absent` | A | A | N/A | A | N/A | N/A | A | A | N/A | N/A |
| `indeterminate-create-outcome` | A | A | N/A | A | N/A | N/A | A | A | N/A | N/A |
| `fork-not-clean-create` | A | N/A | A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| `explicit-skill-meta-review-no-create` | A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| `internal-subagent-not-sidebar-task` | A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | A |

## Operation and observation assertions

### Automatic first-message assertion

R4 is an automatic semantic assertion, not an exact-string snapshot. Derive its live population from
the applicability matrix, add every permitted required `create_thread` occurrence in a contract
variant, and require that the combined population is non-empty and equals the complete permitted
required-create population. For each member, inspect the actual call's `args.prompt` and map its
meaning to staged `host_user_event` facts; a target-only operation assertion never satisfies R4.

The prompt must contain the task contract's compact core: observable objective, material scope,
authority/constraints, cumulative acceptance and proof, deliverable, and stop conditions. Require a
parent relationship only for a named slice. Require artifact/source, freshness, documentation,
progress, or final-evidence modules only when the staged facts make them material. Do not require
headings, field order, Given/When/Then prose, or `not applicable` filler.

Reject prompts that are missing or generic, leak a fixture-declared sensitive sentinel, copy a
fixture-declared durable artifact body instead of referencing it, omit point-of-use revalidation for
a mutable load-bearing fact, or expose parent-only observer tools, bounds, cursors, or polling
mechanics. `prompt_contract_variants` supplies right-reason mutations for these classes; each
unmutated baseline must pass before its mutation is applied.

- Required calls have stable IDs, live-shaped `args_match.value`, and min/max bounds.
- Forbidden calls have stable IDs and argument subsets. `counts` owns total operation bounds.
- `partial_order` references assertion IDs and forms a DAG; it is never a total trace.
- `same_destination_exclusive_interval` compares the discovered destination path with the commitment path and requires all remaining writer-interval premises to be true.
- `wait_threads` uses `targets[]`; `afterCursor` lives inside the matching target.
- `read_thread.cursor` paginates older turns and is never a forward-observation cursor. Cloud forward-observation reads use exact argument matching so an added pagination cursor fails causally.
- A separate task never gains an implied child-to-parent callback. `send_message_to_thread` remains a
  visible prompt, human notifications do not wake the creator, and scheduled heartbeats remain
  time-driven polling.
- Every cloud observation policy has an integer `max_calls` mirrored by a count assertion. On bound
  exhaustion, stop and report incomplete; do not poll again, recreate, or claim completion. The
  policy must exist before `create_thread`; absent user values default to two reads and one unchanged
  result, and those parent-local values must not appear in the child prompt.
- Evaluate `observation_variants` as R9 consumers. New user input transfers control to the parent
  request before another wait. A per-target error keeps coordination incomplete and cannot disappear,
  satisfy acceptance, or be treated as needs-attention without matching live evidence.
- Unlisted read-only repository inspection is allowed. Every state-changing task operation is
  required, forbidden, or explicitly irrelevant to the route.

## Evaluation variants

`prompt_contract_variants` and `observation_variants` are outside the live route matrix. Evaluate them
only for their declared criteria, plus R4 for every permitted required create occurrence. Every live
or variant trace permits at most one creation call for one logical delegation.

A live case passes only when all applicable criteria pass, operation/terminal/observation assertions
hold, the derived R4 denominator covers every permitted required creation call, and each structured
negative mutation fails for its named right reason. Judge behavior, provenance, and state
transitions—not exact wording.
