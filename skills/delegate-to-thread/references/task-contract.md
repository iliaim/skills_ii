# Task contract and context gate

This is the sole normative contract for tasks created through `delegate-to-thread`. The entry skill
routes and sequences the work; evaluations consume this contract but do not redefine it. Live tool
descriptions remain authoritative for current fields, destinations, and return shapes.

## Objective boundary

Give one task one observable outcome or one bounded slice of a named broader objective:

- **Standalone outcome:** after its evidence passes the delegated acceptance criteria, the task may
  satisfy that delegated objective.
- **Child slice:** its result is intermediate evidence only and cannot complete the named broader
  parent objective.

The creator must map final evidence to the relevant acceptance criteria before making any broader
completion claim. Child status alone is not proof.

## Minimum-sufficient first message

Every first message needs a compact core:

- one observable objective and, for a slice, its parent relationship;
- included and excluded scope;
- authority and constraints, including protected or approval-gated actions;
- cumulative, observable acceptance and the strongest practical proof;
- the required deliverable; and
- success, input-required, and no-progress stop conditions.

Add only context that changes the child's decisions, authority, proof, or output:

- exact artifacts or interfaces to read first;
- verified current state and relevant identifiers;
- source accessibility and bounded transfer authority;
- realistic compatibility, failure, or edge conditions;
- documentation duties; and
- progress checkpoints and final evidence mapping for work where intermediate coordination is useful.

For any repository-writing objective, the compact core also includes the execution context: exact
project/path, execution mode (`managed-worktree` or explicitly authorized `direct-local`), worktree
path, branch/ref and base revision when known, and whether the child may write. It must include this
direct-execution boundary: Implement this objective directly in this task; do not invoke `delegate-to-thread`,
`orchestrate-threads`, create another user-visible task, fork, or hand off a descendant unless the
first message explicitly grants descendant authority and defines its scope and owner. If a supported
isolated worktree is unavailable and direct-local writing was not explicitly authorized, stop before
writing and report `input-required`; the child must not choose another checkout or create a descendant
to repair missing context.

Do not add headings or `not applicable` filler merely to satisfy a template. A small create-only task
may be one tight paragraph. Parent observer names, read/wait limits, cursors, polling mechanics, and
local orchestration state never belong in the child's prompt. The attached-child return-route exception
below supplies only the parent identity and supported message route; the parent still owns observation.

Reference durable artifacts instead of copying them. Do not include whole transcripts, private
prompts, raw reasoning, long logs, secrets, credentials, personal data, unrelated history, guessed
facts, or authority the parent does not possess. Suggest a skill only when it materially changes how
the task should execute; use `writing-goals` for genuinely long-running multi-checkpoint work, not a
one-shot task. When a governing orchestration supplies child-local goal permission for a substantial
task, include it; do not infer that permission in standalone delegation. The goal may help the child
continue through verification but never replaces final evidence or parent acceptance.

## Attached-child reporting

For `coordinated-single` and `coordinator creation handoff`, the first message must explicitly require
evidence-bearing checkpoints and one canonical terminal report. A checkpoint is required at every phase
change, when meaningful evidence is produced, when a blocker opens or clears, after an attention
decision is applied, and when verification completes. The child must not substitute ordinary commentary,
a live status, or a terminal execution label for these reports. An independent create-only task remains
compatible with this contract and may omit intermediate checkpoints when no parent consumes them.

When the destination exposes a direct child-to-parent message route, the first message names the
parent's exact task ID and that route (for example, native `send_message_to_thread`). The child sends
an identity-bearing first checkpoint before substantive work, then every required phase and terminal
report, to that exact route; a local final report alone is insufficient for attached coordination. The creator never invents
a route for an unsupported backing kind: it states that callback delivery is unavailable and keeps
the parent on its supported observation path. A sent message is best-effort evidence delivery, not a
guaranteed callback, wake-up, or insertion into the parent turn; the child's own report remains the
canonical evidence record.

Each required checkpoint contains, at minimum:

```text
child_id
report_revision
report_identity_or_digest
observed_at
execution_state
task_liveness
progress_kind
evidence_refs
blocker_or_decision
next_gate
```

The canonical terminal report contains, at minimum:

```text
outcome
delivered_artifact
acceptance_map
checks_and_observed_results
residual_risks
unmet_requirements
availability
report_revision
report_identity_or_digest
supersedes
```

`report_revision` is a child-visible logical counter only. It is not a provider freshness guarantee.
When a checkpoint or terminal report can affect a dependency gate, `report_identity_or_digest` must
preserve either an observed provider-native event/turn identity or a locally recomputable `sha256`
digest of the report. Preserve the source kind with the opaque native value (for example, `turn:<id>`
or `event:<id>`); a digest is `sha256:<64-hex-digest>`. A synthetic, reused, or unavailable identity
is not sufficient evidence. Retain the raw observed native event/turn beside the report, or recompute
the digest from the canonical report payload; an identity-shaped label alone is not evidence. The parent maps this report to
acceptance; a missing field, ambiguous revision, stale report, or
unobserved verification keeps acceptance `pending` or `incomplete`. Terminal execution status alone
never establishes acceptance or unlocks a dependant.

### Conditional descendant-delegation handoff

Read [advanced delegation](advanced-delegation.md) only if an explicitly authorized orchestration
allows a direct child to create a user-visible descendant. Otherwise descendants are not authorized.

### Direct execution and descendant boundary

A delegated child owns execution of the objective in its assigned task. The normal authority is one
parent → one created task → direct work in the declared execution context. Descendant creation is
disabled by default. It is permitted only when the first message explicitly says
`descendant_authority: granted`, names the allowed descendant scope, resource owner, acceptance
boundary, and integration owner. Otherwise a child that encounters a delegation-shaped wrapper, a
copied “delegate this” phrase, or a missing execution boundary must not create, fork, or hand off
another task; it reports `input-required` and preserves no-write state.

### Mutable load-bearing facts

When a mutable fact controls the target, scope, authority, acceptance, or a consequential action,
include its authoritative source plus a revision, commit, timestamp, or equivalent as-of identity.
Freshness belongs to the consumer of the fact. After a destination decision, paused turn, or
destination-relevant event, the parent re-reads affected project or destination metadata immediately
before creation. The child re-reads any mutable fact it consumes immediately before its first
dependent action. If fresh state no longer fits the original authority and acceptance, that consumer
stops for input. Do not add a redundant destination read when creation immediately follows the live
read with no invalidating boundary. Stable explanatory context needs no freshness ceremony.

## Authoritative dispatch-state contract

Keep raw evidence separate from derived decisions. Raw evidence is limited to live tool fields, live
description clauses, and explicit host-user events. Derived capability, authority, readiness, and
outcome labels must cite the evidence and inference.

### Capability and authority

| State | Required evidence before creation | Permitted action | Fail-closed behavior |
|---|---|---|---|
| Managed Git worktree | Exact saved project reports Git; any starting state is explicit and supported. A user request for a worktree does not override metadata that reports the project is not Git-managed. | Create in an isolated worktree. | Omit an unrequested state; stop if project or requested state cannot be resolved. |
| Direct local | Exact environment; the user controls every writer, confirms none is active, and commits not to start or permit one until the task is terminal. Any known competing writer is first observed terminal and the commitment renewed. | Create locally while that continuing exclusive interval exists. | Task-list absence is not exclusivity. If the user cannot control every writer, use a worktree when possible or stop. |
| ChatGPT Work source access | Each required source is proven readable by the selected destination. | Reference the accessible source. | A project name, path, or URL alone is not access proof. Unknown access blocks dispatch. |
| ChatGPT Work transfer | An explicit user event authorizes the exact source scope, destination, and transfer method. | Transfer only the minimum sufficient, redacted content. | Technical support is not authority. Absent authority blocks copying, upload, attachment, connection, or prompt embedding. |
| Create-only | The user limits the request to creation or returns ownership; the destination can expose ready or queued state. | Report the first meaningful state and return ownership. | State ready, queued, or indeterminate accurately; never imply a later callback. |
| Coordinator creation handoff | A user-authorized governing `orchestrate-threads` run requests one ready graph node within its bounded creation envelope and already owns observation, acceptance, and integration policy. | Build the child contract, create once, classify the result, and return raw plus derived creation evidence to that coordinator without observing the child. | Do not return graph ownership to the user, start a second observer, or copy graph and ledger mechanics into the child prompt. Queued or indeterminate identity leaves coordinator observation suspended. |
| Terminal coordination | The request requires observed completion and the selected backing kind has a supported terminal/attention waiter. | Observe through the state table below. | Resolve known observer limitations before creation; unexpected queued/unsupported states become suspended or incomplete. |
| Bounded best-effort observation | The request accepts bounded snapshots and the selected ChatGPT Work backing kind supports status reads but no terminal/attention waiter. | Read within the pre-resolved finite budget and apply the state table below. | Bound exhaustion remains incomplete. Never relabel snapshots as terminal coordination. |

For bounded ChatGPT Work observation, resolve a finite parent-local budget before creation. Use the
user's bound when supplied; otherwise default to at most two reads and at most one unchanged result.
Exhaustion means observation is incomplete, not that the child failed. If the user requires observed
completion and the backing kind has no supported terminal/attention waiter, stop before creation and
offer a supported destination or an explicitly accepted create-only or bounded-best-effort mode.

### Creation result and recovery

One logical delegation means one creation call.

Before that call, record a transcript-local pending-create entry with the `logical_child_key`,
`contract_digest`, `destination_fingerprint`, and `attempt`. Record the raw provider result before
deriving `ready`, `queued`, `rejected`, or `indeterminate`. If the parent turn ends after creation but
before registration, the next turn reconciles this exact entry only by an exact provider identity, a
supported idempotency key, or an authorized controller record. It never retries creation, matches a
title/path, or infers rejection from absence in a bounded listing. If no such reconciliation exists,
preserve the side effect as `indeterminate`, suspend dependants, and report the limitation.

| Observed result | Derived state | Allowed follow-up |
|---|---|---|
| Real task/chat ID | Ready and operable for its supported backing kind. | Apply the selected observation mode; never create a replacement. |
| Client setup ID only | Queued (creation pending); not an operable task ID. | Report setup pending, emit the queued directive, and never pass the handle to task tools or retry creation. Do not call `list_threads`, inspect worktrees, or infer execution from titles, paths, or unrelated active tasks. `clientThreadId` is an opaque, provider-owned setup handle for this exact create attempt; the runtime owns its mapping to the eventual `threadId`. A later provider callback or the exact runtime resolver can supply the real ID, but only a successful native exact-ID read makes it operable. An internal desktop cache is not, by itself, a supported resolver; its exceptional platform-diagnosis gate is owned by [agent communication](../../agent-communication/references/codex-chatgpt.md#reconcile-a-client-setup-result-during-platform-diagnosis). |
| Rejection, timeout, transport loss, malformed result, generic error, or any other error | Rejected only when the live result proves no task or setup exists; otherwise indeterminate side effect. | Reconcile only through a returned stable identity or supported idempotency/exact lookup. Never call creation again, match by title, or claim failure without evidence. |

#### Provider-callback or runtime-resolver resolution for client setup IDs

When a later provider callback returns a real task UUID for this exact pending creation, preserve the
callback as raw creation evidence and confirm that UUID with a native exact-ID read. If setup remains
asynchronous, the preferred runtime contract is one exact resolver for the existing handle:

```text
wait_thread_creation(clientThreadId) →
  { status: "ready", threadId, hostId }
  | { status: "pending" }
  | { status: "failed" | "expired", code }
```

The provider owns the handle namespace and binds each handle to one create attempt, host, and
destination. The resolver must return the matching `hostId` with a ready ID, must not return a bare
candidate UUID, and must make failure terminal and explicit. The caller does not invent a separate
token or search transcripts to resolve the handle during normal delegation. A bounded listing may
omit the new task and is not a rejection signal; do not relist, retry, or create a replacement. Only
the confirmed real UUID—not the setup handle—becomes operable.

The native read must corroborate the callback UUID on the original host. When its live result exposes a
backing kind, project/destination, creation time, or assigned worktree, compare that fact with the
original request and hold on a mismatch. The current ordinary read surface does not guarantee those
extra fields: do not invent them as a recovery barrier. If a user or policy requires one that is not
observable, leave coordination suspended and report that limitation.

Thereafter use the resolved UUID—not the setup ID—for every read, wait, or message. A failed native
read, mismatch, or later conflict leaves coordination suspended: never retry creation, create a
replacement, or contact a title match.

For an expressly authorized undocumented desktop-cache lookup, use the strict correlation gate in
[agent communication](../../agent-communication/references/codex-chatgpt.md#reconcile-a-client-setup-result-during-platform-diagnosis).
It is a separate diagnostic route, not a fallback that weakens callback resolution.

### Observation results

A separate task is a peer. Its transcript is the primary record; no result is automatically inserted
into the creator. Use only operations whose live description supports the returned backing kind.

| Observation result | Parent transition |
|---|---|
| Progress checkpoint | Record meaningful changed evidence; continue only if coordination is still required. Ordinary commentary need not wake a wait. |
| Needs attention | Surface the exact blocker or user-owned decision. Do not continue blindly or treat it as completion. |
| Terminal result | Retrieve only missing evidence, then map it to acceptance. Standalone evidence may satisfy its delegated objective; slice evidence remains intermediate. |
| Unchanged timeout/snapshot | Suppress narration, preserve the returned cursor where applicable, and continue only within the resolved bound. |
| New user input interrupts the wait | Transfer control to the new parent input. Reassess the request before another wait; never classify the interruption as child progress, attention, failure, or completion. |
| Per-target error | Keep coordination incomplete, report the affected stable identity and error evidence, and continue only when live evidence supports a safe bounded recovery. Never treat the error as completion or silently drop it. |

Normalize every exact-ID observation into separate facts:

```text
task_liveness: live | not_live | unknown
observation_health: connected | waiting | reconciling | unknown
progress_kind: phase_change | evidence_added | blocker_opened |
               blocker_cleared | attention_acknowledged |
               verification_complete | no_change
```

Content recency, task liveness, observation health, progress changed/not changed, native revision or
turn identity, and routeability are all reported independently. A live child may have
`progress_kind=no_change`; a transport timeout changes observation health only. Claim changed progress
only when a newer checkpoint revision or native event identity is observed.

`needs_attention` must identify the exact question, authority required, blocked scope, and the report
revision that raised it. After a permitted parent response, the parent waits for a later child
checkpoint with `progress_kind=attention_acknowledged`, the applied decision, and the next gate.
Message delivery is not acknowledgement. Until that later checkpoint is observed, the child and all
affected dependants remain held, and the parent does not resend the same answer.

For ready Codex coordination, keep the creator turn active and use bounded `wait_threads` calls. Pass
each returned cursor as `afterCursor` inside the matching target on the next wait. A bounded timeout
may return compact progress; unchanged timeouts are expected. Use `read_thread` only if a terminal
wait omitted evidence needed for acceptance mapping.

For ready ChatGPT Work bounded observation, use only a live read/status operation that explicitly
supports chats. Apply the pre-resolved budget, suppress unchanged snapshots, and stop incomplete at
the bound. A pagination cursor for older turns is not a forward-observation cursor.

Never let the parent simulate or infer a child callback from a parent-issued
`send_message_to_thread`, title lookup, repeated history reads, desktop notifications, scheduled
heartbeats, or an assumption that a finished child will resume an ended parent turn. This does not
forbid the child's explicitly contracted, identity-bearing report to the named parent return route;
that delivery is still best effort and does not wake or resume the parent. Visible parent follow-ups
are only for a material correction, newly relevant context, or an answer the child requested; they do
not expand authority.

## Readiness gate

Do not create until every applicable statement is true:

- The user authorized one separate task directly or authorized its bounded graph node through the
  governing orchestration; meta-review, dry-run, and explicit no-create requests do not.
- Creation—not continuation, fork, or internal subagent work—is the correct route.
- Exact destination and project identity come from live metadata.
- Direct-local and cloud source/transfer requirements in the capability table pass independently.
- Any uncommitted state, branch, directory name, model, or reasoning override is explicit and live-supported.
- The first message contains the compact core and only material conditional context.
- For repository-writing objectives, execution context is explicit and internally consistent: project/path,
  managed-worktree or authorized direct-local mode, and branch/ref/worktree/base revision when applicable.
- The first message explicitly requires direct execution and states whether descendant authority is granted;
  absent explicit descendant authority, descendant delegation is prohibited.
- Acceptance is observable and cumulative; proof exists or its limitation and manual observation are explicit.
- Mutable load-bearing facts satisfy the freshness rule.
- Remaining ambiguity has been researched and any user-owned decision resolved through `ask-smart-questions`.
- The observation commitment is derived from the request and supported by the destination. Required terminal coordination has a terminal/attention waiter; any cloud snapshot budget is already resolved.
- The ownership mode is explicit. Coordinator creation handoff is used only for one ready child of a
  governing orchestration and returns creation evidence without delegate-owned observation;
  independent create-only returns ownership, while coordinated-single retains observation.
- Creation recovery will follow the result table; creation is never called twice for one logical delegation.

## Progress and final evidence

Use only useful child states: `discovering`, `executing`, `verifying`, `blocked`, `complete`, or
`incomplete`; queued setup is a parent-observed creation state. `task_liveness`, observation health,
progress, acceptance, and artifact availability are independent dimensions. Record the required
checkpoint at each reporting trigger above, and never turn silence or a timeout into a progress,
failure, or completion claim. Do not invent percentages, arbitrary status files, or per-command updates.

For attached work, require the canonical terminal report with outcome, delivered artifact, acceptance
map, checks and observed results, residual risks, unmet requirements, availability, report revision,
report identity/digest, and supersedes. For a small create-only task, the deliverable itself may be
the complete report.

For repository-writing work, the first checkpoint and terminal report must also include execution
context: project/path, cwd, worktree path, branch/ref, base revision, write authority, and changed
files/commit/PR when applicable. If that context cannot be proven, status is incomplete and no
completion claim is allowed.

After creation, the creator first classifies the raw creation result as ready, queued, rejected, or
indeterminate before making any user-facing claim about execution. For coordinated work with a real
task ID, use the supported exact-ID observer before describing execution; for create-only work,
report only the ready identity unless the user separately requests observation. A setup-only result
remains queued and is never described as started. When ready, report the returned operable
`threadId`/`hostId`; when queued, report setup pending and label `clientThreadId` only as a
non-operable setup correlation. The creator then emits the active surface's created-task directive.
In coordinator creation handoff, return the same evidence
to the governing orchestrator, which may use `agent-communication` only after a real task ID exists.
Do not observe on the orchestrator's behalf. In the current Codex desktop surface, use
`::created-thread{threadId="..."}` for a ready task or
`::created-thread{clientThreadId="..."}` for queued setup.

For `coordinated-single`, `queued` is also `unmonitorable` until an exact setup-wait result or
provider callback supplies a real ID and native confirmation succeeds. Do not end the parent turn
while implying that the child is still being observed; surface the missing setup-wait capability and
leave the dependent work suspended. A later parent turn may reconcile only the exact pending-create
entry, never a title, path, or listing match.

Skill text can require this reporting and fail-closed recovery procedure, but the current runtime
does not guarantee that setup completes before `create_thread` returns. Preserve the queued state,
hold dependants, and report that limitation rather than implying that a setup handle is observable.

### Preferred provider creation contract

For attached coordination, `create_thread` should wait until registration completes and return a real
`threadId` and `hostId`. If setup must remain asynchronous, expose one exact operation:

```text
wait_thread_creation(clientThreadId) → { threadId, hostId }
```

Only the returned real ID becomes operable. The parent confirms it with native `read_thread` and then
uses `wait_threads`. No separate caller-generated correlation token, event bus, or parent-resume
mechanism is required for this contract; an ended parent task requires a normal follow-up rather than
an implied callback.

## Platform references

These sources explain design intent; live app tool descriptions control callable behavior:

- [Projects and chats](https://learn.chatgpt.com/docs/projects)
- [Long-running work](https://learn.chatgpt.com/docs/long-running-work)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Git worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Notifications](https://learn.chatgpt.com/docs/notifications)
- [Webhooks](https://developers.openai.com/api/docs/guides/webhooks)
