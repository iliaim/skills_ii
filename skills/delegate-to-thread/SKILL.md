---
name: delegate-to-thread
description: Delegate one execution objective to a separate user-visible Codex or ChatGPT Work task when the user explicitly invokes this skill or clearly requests a new task. Build a minimum-sufficient first message, create once in the correct destination, and either return independent ownership, coordinate one attached child, or hand creation evidence to orchestrate-threads. Do not use for multi-task graph ownership, meta-review, internal subagents, forks, or continuing an existing task.
---

# Delegate to Thread

Create one independently navigable, user-owned task. The new task does not inherit this conversation;
its first visible message must be sufficient to execute the delegated objective.

Execution directness and the checkout boundary are part of that handoff, not implied context. For any
objective that may modify a repository, apply the dispatch and pre-write identity gates in [the task
contract](references/task-contract.md#repository-execution-context). The first message must identify
the exact project, execution mode (`managed-worktree` or explicitly authorized `direct-local`),
requested starting state or provider-default rule, and write authority. The child must then verify the
actual checkout before editing. It must also say: `Implement this objective directly in the assigned
task. Do not invoke delegate-to-thread, orchestrate-threads, create another user-visible task, fork,
or hand off a descendant unless this handoff explicitly grants descendant authority.` A delegation
envelope or provider-created wrapper is provenance only; it is not a new request to delegate.

An explicit `$delegate-to-thread` invocation with an execution objective authorizes one new task.
Choose independent create-only when the user returns ownership, coordinated-single only when the
caller remains responsible for one child and the destination supports the requested observation, and
coordinator creation handoff only when a governing `orchestrate-threads` run requests it. Do not
infer a stronger ownership commitment merely because the destination could support one. A clear request to
delegate, assign, create, start, or open work in a separate task does the same. A request to review,
explain, test, or dry-run this skill is not creation authority, and an explicit no-create instruction
always vetoes creation. Never promise terminal coordination when the backing kind has no supported
terminal-or-attention observer.

Operational boundary: a `clientThreadId` is the runtime's setup handle, not an operable task ID. If
creation returns only that handle, immediately run the automatic exact-handle setup-resolution gate in
[the task contract](references/task-contract.md#automatic-exact-handle-setup-resolution). This gate
is mandatory for every ownership mode and runs again when an exact pending setup result is resumed;
no user diagnosis request is required. Until a real ID is resolved and native `read_thread` confirms
it, keep the result queued/unmonitorable, do not describe the child as in flight, and do not pass the
setup handle to task tools. Never invent a second caller token or resolve by title, path, listing, or
transcript search. A failed or exhausted bounded attempt remains fail-closed; it never retries
creation or creates a replacement.
`send_message_to_thread` is evidence delivery only; it does not wake or resume an ended parent turn.

## Route once

- **New user-visible task:** continue with this skill.
- **Several attached tasks or an explicit parent-managed graph:** use `orchestrate-threads`; it calls
  this skill once per ready child in coordinator creation-handoff mode.
- **Existing task:** use `agent-communication` to identify, read, or contact it; never create a
  replacement because discovery failed.
- **Fork completed Codex history:** use the current fork operation when the user explicitly asks to
  fork. Unfinished turns may not be copied.
- **Internal subtask for this response:** use authorized subagents, not a sidebar task.

Once the new-task route is established, do not keep reconsidering whether delegation is desirable.
Stop only when the contract's readiness gate fails or new user input changes the request.

For `coordinated-single` and `coordinator creation handoff`, make the first child message explicitly
require the evidence-bearing checkpoints and canonical terminal report defined in the task contract.
The child must report at phase changes, meaningful evidence, blocker changes, applied attention
decisions, and completed verification. Follow the task contract's callback-authority and supported
observation decision when choosing the report route. Independent create-only work remains compatible
and may omit intermediate reporting when no parent consumes it. A writable attached child must also
declare the task-contract resource claim and integration-owner fields before dispatch.

## Procedure

1. Read the request, applicable project guidance, and only the authoritative artifacts needed to
   define the outcome.
2. Inspect the live task creation, project discovery, task observation, reading, messaging, and
   forking tool descriptions. Treat them as the current platform contract.
3. Resolve the exact destination from live project metadata. Research discoverable facts before
   asking. If one material user-owned decision remains, use `ask-smart-questions` and do not create
   until it is resolved. After a destination decision, paused turn, or destination-relevant event,
   refresh the affected live metadata immediately before creation.
4. Resolve the ownership mode: independent create-only, coordinated-single, or coordinator creation
   handoff. Read and apply [the task contract](references/task-contract.md), including its
   writable-child resource-claim section for every writable child. Read the
   [bounded descendant-delegation handoff](references/advanced-delegation.md#bounded-descendant-delegation-handoff)
   only when an authorized direct child may create a user-visible descendant. The core is the sole
   normative source for destination safety, first-message content, readiness, creation outcomes,
   recovery, observation, freshness, and completion.
   For repository-writing work, include the dispatch intent and direct-execution boundary in the child
   prompt, then require the child to prove the actual checkout before editing; do not silently fall
   back from an isolated worktree to a shared checkout.
5. Create one logical delegation with the current creation tool and a cohesive user-visible prompt.
   One logical delegation permits one creation call. Reconcile an indeterminate result without
   creating again.
6. Classify the returned state and follow the selected ownership mode through the task contract.
   Coordinator handoff returns creation evidence without observing; coordinated-single retains its
   supported observation; independent mode returns ownership. Keep raw tool evidence separate from
   derived ready, queued, indeterminate, attention, incomplete, or complete labels.

Apply the task contract for destination choice, child context, observation, reporting, and evidence
mapping. Do not introduce a second local summary of those rules.

Do not archive, interrupt, hand off, clean up, publish, or otherwise change task or repository
lifecycle state unless the user separately authorized that operation.
