# Orchestration modes, nested delegation, and agent choice

Research date: 2026-09-01. This is non-normative design evidence, not an operating procedure. Live
tool descriptions remain authoritative. The existing
[`delegate-to-thread` contract](../references/task-contract.md) remains the owner of one-task
creation, and `agent-communication` remains the owner of existing-task contact and continuation.

## Decision

Keep two separate skills:

1. **`delegate-to-thread`:** create exactly one independently navigable task, in either independent
   or parent-coordinated ownership mode.
2. **`orchestrate-threads`:** supervise a bounded set of tasks for one broader objective. It owns the
   dependency graph, concurrency, progress ledger, result acceptance, integration, and recovery
   policy; it composes `delegate-to-thread` for creation and `agent-communication` for existing-task
   operations.

This follows OpenAI's primary orchestration distinction: use delegated ownership when a specialist
should take over its branch, and manager-style orchestration when the manager must retain the final
answer ([Orchestration and handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration)).
The new orchestration skill should therefore be a thin composition layer, not a second copy of the
task-creation or communication contracts.

## Two ownership modes for one delegated task

| Mode | Parent obligation | Use when |
|---|---|---|
| **Independent** | Create once, report the returned state and identity, then return ownership. | The side topic should not interrupt the current session, the user will steer/review it separately, and the current objective does not depend on its result. |
| **Attached** | Keep responsibility for observation, attention routing, evidence retrieval, acceptance, and integration. | The result is on the parent's critical path or the user asks the parent to monitor and incorporate it. |

These are ownership modes, not different prompt templates. Both use the same minimum-sufficient
first-message contract. If the parent objective cannot be accepted without the child result, the
child is attached. If the user explicitly says to launch it and return ownership, it is independent.
When that dependency is materially unclear, resolve the ownership decision before creation instead
of silently promising coordination.

OpenAI recommends keeping related long-running work in one chat when shared context is needed, with
a clear outcome, constraints, and definition of done
([Long-running work](https://learn.chatgpt.com/docs/long-running-work)). A separate task is therefore
appropriate for the mid-session side-topic case only when context isolation or an independent
lifecycle is actually valuable. The child's first message must carry the relevant context because a
new task does not inherit the parent's conversation.

## Multi-task orchestration

For a large project, the root task is a manager, not merely a launcher:

```text
overall objective and acceptance
  -> bounded dependency graph
  -> create ready children through delegate-to-thread
  -> observe direct children and route attention
  -> verify child evidence against delegated acceptance
  -> unlock dependants or continue the same child
  -> integrate accepted branch results
  -> verify the overall objective
```

The orchestration skill should own only:

- the overall objective, acceptance criteria, and authority envelope;
- a directed acyclic graph of bounded child outcomes and dependencies;
- a concurrency limit and writer-ownership map;
- exact direct-child identities and observation cursors;
- separate execution and acceptance states;
- bounded correction, timeout, and escalation policy; and
- the integrated final result and overall evidence mapping.

OpenAI's multi-agent guidance supports independent, bounded parallel work and warns that additional
agents are less useful for ordered reasoning, shared mutable writers, or a single slow external
operation. It recommends a default concurrency of three across the whole agent tree
([Multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent)). Apply the same
principle here: start with a small ready set, expand only when tasks are genuinely independent, and
never parallelize competing writers into the same checkout.

Do not copy the child task contract into the orchestration skill. For every creation, invoke
`delegate-to-thread`; for every later exact-ID read, wait, correction, or continuation, invoke
`agent-communication`. The orchestration ledger records references and decisions, not full
transcripts.

## Nested user-visible tasks

Nested creation should be a capability, not inherited authority. A child may create user-visible
descendants only when its received contract expressly grants a bounded descendant-delegation
envelope. At minimum that envelope identifies:

- which child outcomes may be delegated;
- the maximum active and total descendant tasks;
- allowed destination/project and writer-isolation constraints;
- whether descendants are independent or attached;
- who accepts and integrates their results; and
- the stop condition for further delegation.

Use one direct owner per task. The direct parent owns observation and acceptance of its children;
siblings do not coordinate each other. Do not re-delegate the same objective, create a cycle, or
spawn a replacement because a child is quiet or its creation result is unresolved.

Two nesting policies cover the real use cases:

1. **Centralized:** the root creates every user-visible task. Children may use subagents, or return a
   proposed new task to the root. Use this when the root must display and control the complete global
   graph.
2. **Hierarchical:** an explicitly authorized child may create and coordinate its own children, then
   return one integrated branch result to its parent. Use this when a branch is cohesive and the root
   needs branch status rather than every internal event.

Prefer centralized ownership by default. Hierarchical nesting is justified only when it reduces root
context or gives a branch a meaningful independent lifecycle. Although OpenAI's multi-agent runtime
supports trees and child agents can spawn descendants, it applies a single concurrency limit across
the entire tree; this is a useful precedent for a global delegation budget rather than unrestricted
self-replication ([Multi-agent mechanics](https://developers.openai.com/api/docs/guides/responses-multi-agent#how-multi-agent-works)).

On the current desktop task surface, a child cannot proactively and invisibly register a new
user-visible task with the root. The root learns through observation of its direct child. Therefore a
hierarchical child must remain responsible until its descendants are accepted and report their
identities and integrated evidence in its own terminal result. If the root requires real-time global
knowledge of all descendants, use centralized creation or a durable external controller.

## Subagent or user-visible task?

| Choose a subagent when | Choose a user-visible task when |
|---|---|
| Work is a bounded part of the current response. | Work needs an independent, durable history or lifecycle. |
| The parent will synthesize the only user-facing result. | The user may inspect, steer, resume, or own it separately. |
| Automatic result return to the parent is important. | It should continue in a dedicated environment while the user works elsewhere. |
| Short-lived parallel exploration, review, or implementation is enough. | Separate context is itself a product requirement or prevents a side topic derailing the parent. |
| It can share the current run's tool and authority envelope safely. | It needs distinct project/worktree placement or a separately scoped task contract. |

OpenAI documents that subagent workflows run focused work in parallel and collect results in the
main response; each subagent has bounded context, and the root can message, wait for, and synthesize
their outputs ([Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent)). Codex cloud tasks,
by contrast, use dedicated environments, continue while other work proceeds, and remain available
for later review and follow-up ([Codex cloud](https://learn.chatgpt.com/docs/cloud)).

The decisive question is ownership, not task size: if the parent owns the only final answer, prefer
a subagent; if the work deserves its own user-visible identity and lifecycle, use a task. Do not
create a user-visible task solely to obtain parallelism.

## What to borrow from `writing-goals`

Borrow the goal semantics from [`writing-goals`](../../writing-goals/SKILL.md) and its
[canonical method](../../writing-goals/shared/method.md), but do not import its full protected
maker/reviewer/publisher lifecycle into ordinary task orchestration.

Use these principles:

- **One root objective:** the orchestrator owns one completed parent outcome, bounded scope and
  non-goals, constraints, exact proof, and a terminal stop rule. Do not model a loose backlog as one
  orchestration.
- **Cumulative parent acceptance:** every root criterion is required. A child result is evidence for
  one criterion or slice; no child can mark the parent objective complete.
- **Bounded child slices:** every attached child has its own observable deliverable and acceptance,
  plus an explicit route to the parent criterion it supports. Its terminal result remains
  intermediate until the parent verifies and integrates it.
- **Evidence-bearing checkpoints:** record the current phase, exact evidence observed, next gate,
  and blocker or decision. User-facing progress is one concise sentence; repeated failure with no
  new diagnosis is no-progress, not another useful iteration.
- **Proportionate assurance:** ordinary interactive orchestration uses a lightweight contract and
  the root ledger. Invoke the full protected `writing-goals` workflow only when its own triggers are
  met—unattended execution or multiple genuinely independent executable slices that need protected
  lifecycle authority—not merely because more than one task exists.

This aligns with OpenAI's goal guidance: a good goal is larger than one prompt but smaller than an
open-ended backlog, defines validation and stopping conditions, and reports progress through
checkpoints that name what was verified, what remains, and whether work is blocked
([Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals)).

### Native Codex goal state

When the user explicitly requests goal mode, the surface supports it, and the root orchestration is
genuinely long-running, bind at most one native Codex goal to the complete root objective. Keep its
objective and cumulative acceptance self-contained; an optional stable pointer may navigate to the
orchestration ledger. Do not create a native root goal for a small one-shot independent delegation,
and do not create native child goals automatically. A child may use its own native goal only when
its independently scoped work qualifies under `writing-goals` and its own goal authority is present.

Native goal state is convenience state for the chat: Codex exposes `/goal` to set a persistent
objective, shows its progress above the composer, and lets the user pause, resume, edit, or clear it
([Slash commands](https://learn.chatgpt.com/docs/reference/slash-commands#available-slash-commands),
[Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals)). It does **not**:

- authorize child creation, nesting, publication, destructive action, or broader access;
- replace the root's exact child registry, dependency graph, observation cursors, or acceptance
  evidence;
- automatically aggregate separate task states or child results; or
- provide the controller persistence, event reconciliation, and recovery needed for durable
  unattended orchestration.

Therefore the native goal is a legible root summary and continuation aid. The active root ledger is
the ordinary orchestration record; for unattended mode, the scheduler/controller's protected record
is lifecycle authority. A native `Checkpoint` is only a summary of the latest persisted ledger
transition.

## Progress and result flow

The root keeps one concise row per direct child:

```text
logicalChild, threadId/hostId, dependencies, ownershipMode,
executionState, acceptanceState, lastCursor, blocker, nextAction, evidenceRef
```

Keep execution (`queued`, `running`, `needs_input`, `terminal`) separate from acceptance (`pending`,
`accepted`, `rejected`, `incomplete`). A terminal child has finished running; it has not necessarily
satisfied its contract. Record only meaningful transitions and evidence, not percentages or
per-command logs.

While the root turn is active, use provider-native bounded waits and exact IDs. A child transcript is
the canonical result; there is no automatic insertion into a separate parent task. Correlation IDs
and explicit reply destinations are the standard request/reply pattern
([AsyncAPI request/reply](https://www.asyncapi.com/docs/tutorials/getting-started/request-reply)). If
events cross a durable boundary, deduplicate them using stable producer/event identity; CloudEvents
defines `source + id` for recognizing duplicate delivery
([CloudEvents](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#required-attributes)).

## Durable unattended mode

A skill describes policy but cannot keep a completed parent turn alive. For low-volume work, an
authorized scheduled task in the same chat can periodically reconcile exact child IDs; OpenAI
documents this pattern for checking long-running operations and continuing review loops
([Scheduled tasks](https://learn.chatgpt.com/docs/automations)). For prompt event handling or restart
recovery, use a persistent controller: Codex App Server starts or resumes exact threads,
automatically subscribes the client to task events, and emits `turn/completed` with a terminal status
([Codex App Server](https://learn.chatgpt.com/docs/app-server)).

The durable controller, not the skill or transcript, owns the persistent registry, event
deduplication, reconciliation, deadlines, and wake-up. A workflow engine is justified only when the
system needs stronger cross-service crash recovery, timers, signals, or retry semantics; durable
workflow systems persist progress so execution can resume after process or infrastructure failure
([Temporal](https://docs.temporal.io/)).

## Implications for the skill package

- Keep `delegate-to-thread` one-task-only. Make the independent/attached ownership outcome explicit,
  but do not add graph management to it.
- Create `orchestrate-threads` for project-level authority, decomposition, direct-child creation,
  bounded monitoring, acceptance, integration, and optional durable-runtime routing.
- Keep `agent-communication` unchanged as the exact-ID existing-task operation owner.
- Permit nested user-visible creation only through an explicit descendant delegation envelope;
  otherwise children use subagents or ask their direct parent for another task.
- Test at least: independent side-topic return, attached result integration, bounded parallel DAG,
  attention routing, unmet-acceptance continuation, centralized nesting, authorized hierarchical
  nesting, unauthorized nesting refusal, subagent-vs-task routing, shared-writer serialization,
  queued setup suspension, and durable-mode handoff.
- Do not add child-to-root message callbacks, title matching, unbounded recursive creation, duplicate
  create retries, full transcript replication, or scheduled polling disguised as event delivery.
