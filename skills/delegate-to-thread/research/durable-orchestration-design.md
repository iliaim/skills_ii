# Coordinated and durable task orchestration

Research date: 2026-09-01. This is non-normative design evidence, not an operating procedure.
Live tool descriptions remain authoritative, and
[the task contract](../references/task-contract.md) remains the skill's sole normative contract.

## Decision

Use two tiers, not one oversized skill:

1. **Coordinated delegation:** `delegate-to-thread` creates each user-visible task and supplies its
   minimum-sufficient contract. The creating task stays alive, observes exact child identities, and
   uses `agent-communication` for later inspection, correction, continuation, or evidence retrieval.
2. **Durable unattended orchestration:** a scheduler or small controller persists the coordination
   record and wakes/reconciles work after the creating turn has ended. A model task is a worker and
   decision-maker inside this loop; it is not the durable state store.

This preserves the useful distinction OpenAI makes between independent chats and subagents. Separate
chats keep their own context and results, whereas the main thread automatically collects subagent
results ([Long-running work](https://learn.chatgpt.com/docs/long-running-work),
[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)). Use subagents when the
result only needs to return to the current response; use user-visible tasks when independent history,
steering, ownership, or longevity is the point.

## What the current desktop surface can and cannot do

The live desktop tools available on the research date support creating an asynchronous task,
waiting for the first of up to eight Codex tasks to complete or need attention, reading a task,
and sending a visible follow-up to an exact task. A wait cursor suppresses already-delivered results;
ordinary commentary does not wake the wait. A creation response can instead contain only a queued
client setup ID, which is not accepted by the task observation tools.

Therefore a live parent turn can coordinate ready Codex tasks efficiently, but it cannot promise to
wake after that turn ends. Desktop Activity and notifications inform the human that a chat is running,
ready, blocked, or needs input; they are not a machine callback into the creator
([Notifications](https://learn.chatgpt.com/docs/notifications)). Scheduled tasks can return to the
same chat with its existing context, but they are time- or supported-app-event-driven runs, not a
child-completion subscription ([Scheduled tasks](https://learn.chatgpt.com/docs/automations)).

Codex App Server is the stronger integration surface for a separate local controller. A client can
start or resume threads, receives `thread/status/changed`, `turn/*`, and `item/*` notifications on an
active connection, and receives `turn/completed` with `completed`, `interrupted`, or `failed` status.
It can also recover authoritative thread state with `thread/read` and `thread/list`
([Codex App Server](https://learn.chatgpt.com/docs/app-server)). These capabilities are not exposed by
the two skills themselves; using them requires a separate process or product integration.

## Tier 1: coordinated delegation in one live parent turn

The parent should operate as a small supervisor:

```text
define child contracts -> create once -> retain exact IDs -> bounded cursor wait
       -> attention: surface/answer -> terminal: retrieve missing evidence
       -> test against acceptance -> accept, continue same task, or report incomplete
```

For multiple ready Codex tasks, keep a set of `{threadId, hostId, cursor, acceptance}` records and
wait on up to the supported batch limit. Reuse the returned cursor for that exact task. Read history
only when the terminal wait omitted evidence needed for acceptance. Do not repeatedly poll every
transcript or narrate unchanged timeouts.

`delegate-to-thread` should remain the sole owner of creation and the first-message contract.
`agent-communication` should remain the sole owner of identifying, inspecting, contacting, and
intentionally continuing an existing task. The coordinator composes them; neither skill should copy
the other's rules.

A child that requests approval or user judgment is `needs_input`, not stalled. The parent surfaces
the exact question and sends one visible answer only after the user or existing authority resolves
it. A terminal child is `terminal_unverified`, not complete: the parent accepts it only after mapping
canonical output and observed checks to every delegated acceptance criterion. OpenAI similarly
recommends outcome, constraints, and verification criteria for long-running goals
([Long-running work](https://learn.chatgpt.com/docs/long-running-work)).

If the parent turn ends, report coordination as suspended or transferred to the user. Do not imply
that the child will call back or that observation continues.

## Tier 2: durable unattended orchestration

Choose the smallest mechanism that meets the service level:

- **Periodic, low-stakes follow-up:** attach a user-authorized scheduled run to the coordinator chat.
  Each run reconciles exact task IDs, records only changed state, and stops itself when every child is
  accepted or terminally unresolved. This has bounded detection latency and is polling.
- **Prompt completion/attention handling, crash recovery, or many tasks:** run a small controller
  against Codex App Server. Consume its event stream while connected and reconcile with `thread/read`
  or `thread/list` after reconnect. Do not represent a scheduled heartbeat as event-driven delivery.
- **Cross-service or high-consequence workflows:** use a durable workflow engine only when restart,
  timer, signal, and retry requirements justify its operational cost. Temporal, for example, persists
  workflow progress across process and infrastructure failure and separates deterministic workflow
  logic from failure-prone activities; activity retries are policy-controlled
  ([Temporal overview](https://docs.temporal.io/),
  [Temporal retry policies](https://docs.temporal.io/encyclopedia/retry-policies)).

HTTP's asynchronous model supports this separation: `202 Accepted` does not promise completion, and
its representation ought to identify a status monitor
([RFC 9110 section 15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)). A durable
coordinator should therefore persist a canonical operation record rather than infer status from chat
titles, timestamps, or prose.

### Minimum persistent record

One record per orchestration, with one child row per delegated task, is enough:

```text
orchestrationId, parentThreadId, objectiveRef, authorityRef, createdAt, deadline
childId, hostId, contractDigest, acceptanceRef, state, observationState
lastEventId/cursor, lastObservedAt, attempt, resultRef, unmetAcceptance, nextWakeAt
```

`childId` is the provider's real task identity; a queued client setup ID is recorded separately and
never treated as operable. `contractDigest` detects accidental prompt drift. `resultRef` points to the
canonical child transcript or artifact rather than copying it into the registry. Secrets, raw
reasoning, complete transcripts, and large logs do not belong in this record.

Use a stable `orchestrationId` as the correlation ID across creation, observation, and continuation.
AsyncAPI defines correlation IDs for message tracing/matching and explicit reply addresses for
request-reply operations ([AsyncAPI 3.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0)).
If events cross a durable boundary, include a producer-scoped event ID: CloudEvents defines
`source + id` as the identity by which consumers can recognize duplicate delivery
([CloudEvents 1.0](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#required-attributes)).

### Small state model

Keep task state separate from observation health:

```text
task:        dispatching -> queued -> running -> needs_input -> terminal_unverified
                                                    |                |
                                                    v                v
                                              running again   accepted | incomplete
terminal failures: failed | interrupted | cancelled | timed_out

observation: connected | waiting | reconciling | unknown
```

This prevents a transport timeout from being mislabeled as child failure. Progress is recorded only
when a task changes phase (`discovering`, `executing`, `verifying`), produces a meaningful checkpoint,
needs attention, or reaches a terminal result. Do not invent percentages or copy per-command output.

### Events, waits, and recovery

Prefer event notification while a supported connection is active, then reconcile from canonical
state after any disconnect. OpenAI Background Responses demonstrate the same dual model: a client can
poll a stable response ID or resume a background event stream from a saved sequence cursor
([Background mode](https://developers.openai.com/api/docs/guides/background)).

Treat delivery as at least once. Persist the event/cursor before or atomically with consequential
state changes; deduplicate by stable event identity; make handlers idempotent; and fetch canonical
task state before accepting a result. OpenAI webhooks may retry for up to 72 hours, can deliver
duplicates, recommend deduplication by `webhook-id`, and require signature verification for trusted
action handling ([OpenAI webhooks](https://developers.openai.com/api/docs/guides/webhooks)).

On controller restart:

1. load nonterminal orchestration rows;
2. reconcile every exact child ID with the provider;
3. apply only monotonic/newer observations;
4. re-register waits or subscriptions;
5. surface unresolved attention and overdue work once, without recreating a child.

### Attention, continuation, retry, and timeout policy

- Route approvals, missing authority, changed product decisions, credentials, and destructive actions
  to the human. An unattended controller must not manufacture consent.
- Send follow-up work to the same exact task when it is the same objective and retained context is
  useful. The message should name only the unmet acceptance evidence and next gate.
- Retry observation transport failures with capped exponential backoff and jitter. Reconcile before
  retrying any action whose outcome is unknown.
- Never retry creation merely because its response timed out or the task is quiet. One logical
  delegation has one creation attempt unless a provider-supported idempotency key proves replay safe.
- Retry child execution only for classified transient failures, within an attempt and elapsed-time
  budget. Permanent failures and repeated identical blockers become `incomplete` and require review.
- Use separate time limits for no-checkpoint warning, child execution, attention response, and the
  overall orchestration. Silence alone is not failure; provider state and missed contractual
  checkpoints are the evidence.

### Acceptance and authority

The coordinator owns integration, not the child's self-assessment. It accepts a child only when the
required artifact exists, evidence maps to the original criteria, required checks were actually
observed, and residual risks or unmet requirements are explicit. A reviewer result, status string,
or terminal event is evidence, never completion by itself.

Preserve least privilege per child: one bounded objective, isolated worktree for parallel writers,
minimum source access, explicit approval boundaries, and no credential transfer in prompts. OpenAI's
long-running-work guidance warns against concurrent write access to the same source and states that
goals retain their existing sandbox and approval policy
([Long-running work](https://learn.chatgpt.com/docs/long-running-work)). Authenticate controller
connections, restrict which projects and task IDs they may operate, verify signed external events,
and keep an audit trail of consequential messages and state transitions.

## What not to build

- Do not make children message the parent as a simulated hidden callback; visible peer messages are
  user-visible turns, not a durable event channel.
- Do not title-match tasks, scrape all transcripts, or create a replacement when identity is missing.
- Do not maintain a second prose status file beside the provider transcript and controller record.
- Do not store every token, command, or log line; store transitions, references, and acceptance
  evidence.
- Do not promise exactly-once delivery or execution. Aim for at-least-once observation with
  deduplicated, idempotent handling.
- Do not auto-answer approvals, broaden authority, restart silent workers, or create more writers to
  "make progress."
- Do not introduce a message broker, webhook service, or durable workflow engine for a handful of
  tasks that one live bounded wait or one scheduled reconciliation can safely handle.

## Recommended rollout

1. Make coordinated delegation the default only when a real Codex task ID and supported waiter are
   available; otherwise report create-only, queued, or incomplete truthfully.
2. Add a small orchestration ledger to the parent transcript/report: exact IDs, acceptance references,
   cursors, and current states. Keep it non-durable until a real unattended need is demonstrated.
3. For user-authorized periodic monitoring, attach a scheduled run to the same coordinator task and
   enforce a terminal stop rule.
4. If low-latency wake-up or crash recovery becomes necessary, build a narrow App Server controller
   with persisted identity, event deduplication, reconciliation, bounded retries, and human attention
   routing. Adopt a durable workflow engine only after those requirements exceed what the small
   controller can reliably provide.
