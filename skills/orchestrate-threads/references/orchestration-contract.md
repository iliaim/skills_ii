# Orchestration contract

This is the normative contract for `orchestrate-threads`. Live tool descriptions control current
operations, fields, backing-kind support, and result shapes. `delegate-to-thread` remains the sole
owner of one-task creation and its child prompt; `agent-communication` remains the sole owner of
supported exact-ID inspection, waiting, contact, and continuation.

## Root contract and readiness

Define one root outcome with:

- included scope and explicit non-goals;
- the authority and constraints shared by the run;
- cumulative, observable parent acceptance and the strongest practical proof;
- a terminal success rule plus input-required and no-progress stops; and
- bounded child outcomes, each mapped to a root criterion.

Do not treat a loose backlog as one orchestration. Child completion is evidence for the root; no
child may complete it.

Construct a shallow acyclic dependency graph. Every edge names one gate:

- `accepted_evidence`: verified upstream evidence is sufficient; or
- `available_artifact`: the dependant needs integrated or otherwise readable work.

Acceptance alone never satisfies an artifact edge. Dispatch a child only when every dependency gate
is open, the destination and writer plan are safe, and all applicable limits permit it. Serialize
conflicting writers in a shared destination. Isolated worktrees may overlap when a named integration
owner and conflict-resolution gate prevent either result from being treated as integrated early.

Record each dependency edge as an evidence-bound admission record:

```text
source_child_id
source_report_revision
source_report_identity_or_digest
source_artifact_revision_or_digest (or `not_applicable` for `accepted_evidence`)
criterion
observed_at
supersedes
```

An `accepted_evidence` edge opens only for the exact source child, logical report revision, and
immutable source report identity/digest recorded on that edge. Its artifact field is explicitly
`not_applicable`; acceptance must not invent an integration requirement. The logical
`source_report_revision` is not authoritative freshness evidence because provider revisions may be
reused, reordered, or absent. Preserve a native identity as `turn:<id>` or `event:<id>`, or a report
digest as `sha256:<64-hex-digest>`; without one, the edge remains pending/incomplete. A newer or contradictory report, artifact revision, or
observation supersedes the record and recloses every affected dependant until the edge is remapped.
The parent retains the matching raw native event/turn. A digest path is admissible only when the
canonical source-report payload is paired with an independently authenticated immutable provenance
record naming the source child, report revision, criterion, and exact digest; recomputation alone
is integrity checking, not issuer authentication. An identity-shaped label alone cannot open an edge.
An `available_artifact` edge additionally requires an exact readable path and commit/HEAD or another
immutable artifact revision. Missing, stale, ambiguous, superseded, or unacknowledged evidence never
opens a gate.

## Acceptance-contract and cold-review gates

When the parent supplies an acceptance contract, read the exact file before dispatch and treat it as run
authority for cumulative criteria, named checkpoints, stop conditions, and required evidence. Map each
criterion and checkpoint into the transcript-local ledger. For a contract with T0–T8 or equivalent
IDs, record every task and candidate criterion separately with its required status, evidence, and
dependency; a success-criteria summary is not a task ledger. At each named stop checkpoint, re-read
the fresh diff and evidence before opening the next gate. If the contract requires an independent
challenger before implementation or after a named phase, dispatch a cold read-only reviewer, or use
bounded read-only subagents when the result belongs in the current response. The review request must
include the exact contract path, the candidate or artifact revision, the read-only boundary, the
checkpoint, and the required disposition. A gate opens only from a report that identifies the exact
reviewed revision, maps findings to criteria, lists dispositions, records unresolved blockers, and is
bound to a native turn/event identity or a SHA-256 report digest. Commentary or status text alone is
not review evidence.

Before the first dispatch, resolve the run-specific limits that materially govern:

- active direct children;
- total direct children;
- observation calls or waits;
- corrective continuations per child; and
- repeated no-progress escalation.

Active and total child ceilings are positive when dispatch is allowed; observation, correction, and
no-progress budgets may be zero. Record whether each limit is a user, policy, or tool hard ceiling or
a coordinator-local operating budget. Never exceed a hard ceiling without revised authority. A local
budget may be recomputed transparently after material progress when objective, scope, authority,
cost, and risk are unchanged. Exhaustion otherwise suspends the affected work or returns it
incomplete. Elapsed time is only an escalation signal unless a named host or controller enforces it.

## Transcript-local ledger

Keep one concise row per direct child. This is coordination evidence in the current transcript, not
a scheduler or durable status database. Always record the logical child, mapped root criterion,
identity or creation evidence, execution, task liveness, observation health, progress, acceptance,
availability, blocker or next gate, and evidence reference. Add dependencies, cursor, integration
route, assurance state, resource claims, or other fields only when they apply.

Keep raw provider evidence separate from derived state:

| Dimension | States and rules |
|---|---|
| Creation | `existing` registers the exact operable identity for its backing kind without creation; `ready` records the identity returned by creation; retain `hostId` when returned or required by the operation. `queued/unmonitorable` (creation pending) records only a non-operable `clientThreadId`; `indeterminate` records only stable correlation evidence, if any; `rejected` requires provider evidence that neither a task nor setup exists. |
| Execution | Track useful transitions such as `not_started`, `discovering`, `executing`, `verifying`, `needs_attention`, `terminal`, and `incomplete`. Transport silence or timeout is not child failure. |
| Task liveness | Independently record `live`, `not_live`, or `unknown`. A live child may have no progress. |
| Observation health | Independently record `connected`, `waiting`, `reconciling`, or `unknown`. A timeout changes this dimension only. |
| Progress | Record `phase_change`, `evidence_added`, `blocker_opened`, `blocker_cleared`, `attention_acknowledged`, `verification_complete`, or `no_change`; require a newer report/native event identity for a changed claim. |
| Acceptance | `pending` until evidence mapping, then `accepted`, `rejected`, or `incomplete`. Terminal execution is never automatic acceptance. |
| Availability | `not_required`, `pending`, `available`, or `unavailable`. Child acceptance does not prove worktree integration or artifact readability. |

Record meaningful state or evidence changes, not repeated unchanged snapshots. Map every root
criterion to accepted and, when required, available evidence or to an explicit gap. Require attached
children to return the checkpoint and terminal-report fields defined by the delegate task contract;
ordinary commentary, child status, and message delivery do not satisfy those fields.

## Resource claims and writer admission

The [delegate task contract](../../delegate-to-thread/references/task-contract.md) is the sole owner
of the resource-claim field schema and the child-facing declaration requirement. Before dispatch, the
parent verifies that each writable child has a complete claim for every repository and external shared
resource it can mutate. Unknown or conflicting claims hold dispatch. Shared reads may overlap;
overlapping writes serialize, including worktrees, branches, generated artifacts, databases,
deployments, queues, and other shared mutable targets. Isolated worktrees may overlap only with a
named integration owner and a post-image conflict check. Observation timeout or lost routeability does
not release a claim; only the named owner may release or transfer it after terminal evidence or an
explicit transfer. These are protocol claims, not runtime locks: if no controller or provider enforces
them, the parent must fail closed or serialize procedurally and report that limitation.

## Creation handoff and adoption

Managing tasks does not imply authority to create them. Initialize a graph from supplied existing
exact identities without calling `delegate-to-thread` or any creation operation. Preserve each exact
operable `threadId` and any returned or required `hostId`, register it as `existing`, and use `agent-communication` only for supported
exact-ID operations. If an exact identity cannot be established, hold that node and surface the
identity gate; never create a replacement or reconcile by title.

Only for a node explicitly authorized as new, call `delegate-to-thread` in explicit **coordinator
creation handoff** mode.
Supply the bounded outcome, parent relationship, root criterion, scope, authority, cumulative child
acceptance and proof, deliverable, stop conditions, and—when the child may write—the integration
owner, allowed integration action, and evidence it must return. The child prompt must not contain
the root's observation mechanics, cursors, wait budget, or ledger.
For a writable child, preserve the delegate contract's exact execution-boundary evidence, including
`execution_evidence`: the dispatch mode, starting-state rule, observed checkout, write authority, first checkpoint, and
terminal report must remain bound to the same project/worktree before integration is considered.

Before delegating, the parent records a pending-create entry containing `logical_child_key`,
`contract_digest`, `destination_fingerprint`, and `attempt`. After the create call, it records the raw
provider result before deriving state and completing registration. A setup-only result immediately
enters the delegate contract's bounded automatic exact-handle setup-resolution gate. If a turn ends in
that interval, the next turn repeats the gate for that exact pending entry. No second create,
title/path match, or bounded-list absence inference is permitted; without a proven exact identity the
node remains `queued/unmonitorable` and its dependants stay held. Use `indeterminate` only when a
provider may have created a side effect without an exact reconciliation route.

Delegate creates once and returns raw and derived creation evidence after the bounded setup-resolution
gate:

- Ready: register the returned operable identity, including `hostId` when supplied or required;
  exact-ID operations may begin.
- Queued/unmonitorable: register only the runtime-owned `clientThreadId` setup handle after the
  automatic gate is exhausted; it is non-operable and cannot be observed, contacted, or used to
  unlock a dependant. Do not create a second caller token. On a later exact pending-entry resume,
  repeat the same bounded gate; otherwise remain suspended without another create
  call.
- Indeterminate: retain only returned stable correlation evidence. Reconcile only through a
  supported exact route.
- Rejected: retain exact proof, leave the node undispatched, and hold dependants.

Never retry creation, match by title, scrape unrelated transcripts, or construct a replacement.

Absence of a real task ID after the bounded automatic gate is not a root-wide stop. Preserve the raw
provider result and classify the node as `queued/unmonitorable`; use `indeterminate` only when the
provider may have created a side effect without an exact reconciliation route. Hold that node and
its dependants only. The parent may continue independent root work and bounded current-response
read-only reviews whose dependencies are open. Do not observe or contact a `clientThreadId`, invent
an ID, retry creation, match by title, scrape transcripts, or create a replacement. Reconcile only
through the same exact-handle gate when the pending entry is resumed.

If one delegate-owned coordinated child grows into a graph, adopt its exact ID, host, cursor,
delegated-contract reference, execution evidence, acceptance evidence, and availability evidence.
Delegate-owned observation then ceases; the root becomes the one observer. Do not recreate or reset
the child.

## Observation, attention, and correction

After a real identity exists, route supported operations through `agent-communication` under this
root's governance:

- Batch bounded waits within the live waiter target limit. Preserve every cursor against its exact
  child and pass it only to that child's next wait.
- Record changed checkpoints; suppress unchanged timeouts. A per-target error stays correlated to
  that child and leaves its coordination incomplete while other safe observations may continue.
- When new user input interrupts a wait, answer from last observed evidence and reassess before
  waiting again. The interruption is not child progress, attention, failure, or completion.
- On `needs_attention`, hold that child and its dependants. Resolve factual or operational input only
  within existing authority; surface any human-owned policy, product, credential, destructive, or
  authority decision exactly. One blocked child does not automatically block the root while other
  ready work or root criteria can progress.
- Require the exact question, authority, blocked scope, and raising report revision in the attention
  record. After a permitted parent response, hold the child and affected dependants until a later
  observed checkpoint reports `attention_acknowledged`, the applied decision, and the next gate. A
  successful message send is not acknowledgement, and the same answer is not resent while awaiting
  acknowledgement.
- At terminal execution, retrieve only missing canonical evidence and map every delegated criterion.
  Recompute dependency and cumulative root gates rather than trusting the child's status.
- For a safely repairable in-scope defect or proof gap, continue the same exact child with only the
  unmet criterion, grounded finding, and next gate, within its correction bound. Stronger contrary
  evidence may move acceptance back to `pending` or `rejected` and close affected dependency gates;
  preserve the raw record and mark prior derived evidence superseded.
- If a running child loses authority while still executing, hold acceptance, integration, and all
  dependent gates. Use only a supported hold/stop route; if the runtime cannot enforce the revocation,
  report the child as uncontrollable and do not treat later child claims as authorized evidence.
- When the no-progress threshold is reached without a new diagnosis or materially different
  correction, preserve the child, mark affected acceptance incomplete, and escalate instead of
  looping. A proven terminal failure may gain an explicitly authorized successor node; preserve the
  original identity and evidence and never treat the successor as a retry of uncertain creation.

Visible messages are task turns, not hidden callbacks. Notifications, child messages, and heartbeat
runs do not automatically insert results into or resume an ended parent turn. Keep the parent turn
active while observing a ready child; an ended parent requires a normal follow-up.

## Integration authority

Every writable child contract names:

- the integration owner;
- the allowed integration action; and
- returned evidence such as an artifact path, diff, commit identity, or verification result.

Accepting a child's bounded result does not authorize integration. The orchestrator integrates only
when the user and repository lifecycle already grant that authority and the owning procedure permits
the action. Otherwise report accepted-but-not-integrated, the availability state, preserved evidence,
and the exact next gate. Never implicitly merge, publish, hand off, interrupt, clean, or retire work.

## Conditional modes

Read [advanced modes](advanced-modes.md) only when independent assurance, hierarchical descendants,
native goals, or a durable coordination mode is in scope. It owns the additional rules for those
cases; none applies to an ordinary bounded graph.

## Changed intent and terminal stops

When parent intent changes, stop new dispatch and preserve every existing task. Distinguish old and
new objectives, classify each child for continuing relevance, and do not interrupt, archive, hand
off, delete, clean, or silently rescope it. Require revised cumulative acceptance or explicit
ownership transfer before continuing the changed run.

Stop successfully only when every cumulative root criterion, required proof, and required artifact
availability gate passes. Stop for human input when authority, product policy, hierarchical risk,
unsupported durability, destructive/external action, a new dependency or ADR, or the objective must
change. Stop for no progress when the same material failure repeats without a new diagnosis or
materially different correction. Report the exact identities, evidence, unmet criteria, and next
authorized gate; never convert incomplete work into completion.
