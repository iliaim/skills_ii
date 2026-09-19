---
name: orchestrate-threads
description: Coordinate several separate user-visible Codex tasks under one bounded parent objective. Use for a parent-managed dependency graph that needs central dispatch, monitoring, acceptance, correction, and integration; use delegate-to-thread for one task and subagents for work returning in the current response.
---

# Orchestrate Threads

Own one parent outcome across several attached user-visible tasks. This skill is the graph and
acceptance owner; it composes `delegate-to-thread` for each creation and `agent-communication` for
supported operations on an existing exact task identity. It does not duplicate either contract.

An explicit invocation with a multi-task execution objective, or a clear request for one task to
manage several other tasks, authorizes coordination only for the bounded graph placed in scope. It
authorizes a new direct-child creation only when the user explicitly requests new tasks or approves
a graph that identifies that node as new. Managing existing task IDs never implies creation. Review,
design, and dry-run requests do not authorize real task, goal, automation, repository, or external
mutations.

## Route before dispatch

- One independent side task whose result is not on the current objective's critical path:
  `delegate-to-thread` in independent create-only mode.
- One attached child: `delegate-to-thread` in coordinated-single mode.
- Several attached children or an explicit parent-managed dependency graph: this skill.
- An existing exact task: `agent-communication`; never create a replacement.
- Several existing exact tasks, or a mixed graph of existing and explicitly authorized new tasks:
  this skill. Register existing nodes without creation and use `agent-communication` for their
  supported exact-ID operations.
- Bounded work whose result belongs in the current response: authorized subagents. Parallelism alone
  does not justify a user-visible task.

If a coordinated single child expands into a graph, adopt its exact identity and evidence as
described in the contract; transfer observation ownership once and never recreate it.

Creation handoff has an explicit identity stop: a returned `clientThreadId` is the runtime-owned
setup handle and is `queued/unmonitorable`, not a live child. Keep its dependants held until the
runtime resolver or a native exact-ID callback and `read_thread` confirmation produce a real task ID.
Do not invent a second caller token or search transcripts during normal delegation. Keep the parent
turn active while observing a ready child; an ended parent requires a normal follow-up.

## Procedure

1. Inspect the current task, project, observation, communication, native-goal, and automation tool
   descriptions needed for the request. Live descriptions control callable behavior.
2. Read and apply the core [orchestration contract](references/orchestration-contract.md). Read
   [advanced modes](references/advanced-modes.md) only when independent assurance, descendants,
   native goals, or a durable mode is in scope. The core owns graph state, acceptance, correction,
   integration, and stopping behavior; the annex owns only those conditional additions.
3. Resolve one root outcome and cumulative acceptance, then a shallow graph of bounded child
   outcomes. Before the first dispatch, resolve material hard limits, local operating budgets, and
   writer or integration ownership required by the contract.
4. Register each ready existing task by its exact identity without creation. For each ready child
   explicitly authorized as new, invoke `delegate-to-thread` in **coordinator creation handoff**
   mode. It constructs the first-message contract, creates exactly once, classifies the result, and
   returns creation evidence without observing the child. Record only the identity actually
   supplied or returned.
5. After a real `threadId` exists, use `agent-communication` for supported exact-ID waits, reads,
   attention replies, and continuations. Keep execution, acceptance, and artifact availability
   separate; map evidence before unlocking dependants. The parent always validates the result.
   Add a cold, read-only checker only when user or project policy requires it or independent review
   materially improves assurance.
6. Continue the same exact child for a safely repairable in-scope defect or evidence gap within the
   correction bound. Never retry or replace queued or indeterminate creation. After a proven terminal
   failure, a successor is a new explicitly authorized node that preserves the prior identity and
   evidence; it is never an implicit retry.
7. Integrate only through the named owner and an already-authorized lifecycle procedure. Complete
   the parent only when every cumulative root criterion and required artifact-availability gate has
   evidence.

Keep progress useful: report a phase or evidence change, blocker, next gate, or final rollup. Do not
invent percentages, per-command updates, a generated task tree, or a separate status store.

Every attached child receives a first-message requirement for evidence-bearing checkpoints and one
canonical terminal report. The parent accepts only observed, revision-bound reports: liveness,
observation health, progress, acceptance, and artifact availability remain separate, and missing,
stale, ambiguous, superseded, or unacknowledged evidence keeps the affected gate closed.

Do not merge, publish, hand off, interrupt, archive, clean, retire, start a native goal in the parent,
or create an automation unless that separate action is authorized and its owning procedure permits
it. The contract defines the narrower child-local goal rule.
