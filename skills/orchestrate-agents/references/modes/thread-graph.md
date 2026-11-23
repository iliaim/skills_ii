# Mode: `thread-graph`

Use this mode when `.agents/orchestration.json` sets `"mode": "thread-graph"` or `"mode": "auto"` without an issue queue, coordinating several attached user-visible tasks under one bounded parent objective. This mode composes [../orchestration-contract.md](../orchestration-contract.md) (normative core) and [../advanced-modes.md](../advanced-modes.md) (conditional annexes for independent assurance, nesting, native goals, and durable polling).

## 1. Ownership boundaries across sibling skills

- **Coordinated single child**: One attached child stays in `dispatch-workers` (`coordinated-single` mode) unless it expands into a multi-task graph. When promoted, adopt its exact `threadId`, `hostId`, cursor, delegated contract, and current evidence once—never recreate or dual-observe it.
- **Existing exact identities**: Register supplied `threadId` / `hostId` pairs as `existing` without calling creation, and route all supported reads, waits, attention replies, and continuations through `agent-communication`.
- **New graph nodes**: Invoke `dispatch-workers` in **coordinator creation handoff** mode only for nodes explicitly authorized as new. It constructs the child's first-message contract, creates once, classifies the result, and returns creation evidence without observing the child.
- **Current-response parallelism**: When bounded work returns inside the current turn and needs no persistent user-visible thread, use read-only or bounded subagents rather than creating threads.

## 2. Creation classification and `clientThreadId` setup-resolution gate

Before calling creation, record a pending-create entry (`logical_child_key`, `contract_digest`, `destination_fingerprint`, `attempt`). After the create call, store the raw provider response before deriving state:

| Creation State | Evidence / Handle | Operable? | Orchestrator Action |
|---|---|---|---|
| `ready` | Real `threadId` (+ `hostId` when supplied) | Yes | Hand exact-ID observation to `agent-communication`. |
| `queued/unmonitorable` | Setup handle `clientThreadId` only | No | Hold node & dependants; never call `read`/`wait`/`send_message`, never expect parent wake, never retry creation. Reconcile only on pending-entry resume. |
| `indeterminate` | Correlation evidence only | No | Preserve raw response; never retry creation, title-match, or scrape unrelated transcripts. |
| `rejected` | Proven absence of task & setup | No | Keep undispatched, hold dependants, and surface rejection proof + next gate. |

## 3. Dependency edges: `accepted_evidence` vs `available_artifact`

Construct a shallow acyclic dependency graph where every edge names one gate and binds to immutable provenance:

- **`accepted_evidence`**:
  - Opens only when `source_child_id`, `source_report_revision`, criterion, and backed `source_report_identity_or_digest` (`turn:<id>`, `event:<id>`, or authenticated `sha256:<digest>`) match observed native records and are not superseded.
  - Set `source_artifact_revision_or_digest` to `not_applicable`; acceptance must not invent an integration requirement.
- **`available_artifact`**:
  - Requires everything in `accepted_evidence` **plus** an exact `readable_path`, immutable post-image `source_artifact_revision_or_digest`, and native filesystem post-image observation (`artifact_observation_id`).
  - Accepted work inside an unmerged worktree stays `accepted` with availability `pending` or `unavailable` until integrated.

Before dispatching any writable node, verify non-conflicting resource claims (`resource_id`, `destination_fingerprint`, `paths_or_scope`, `access_mode`). Serialize overlapping writers on shared checkouts; overlapping isolated worktrees require a named integration owner and post-image conflict check.

## 4. T0–T8 checkpoint ledger and revision-bound cold review

Maintain one concise transcript-local ledger row per direct child (never a separate scheduler or status database), recording:
- logical child key, mapped root criterion, and exact identity or creation evidence;
- raw execution state, task liveness (`live` / `not_live` / `unknown`), observation health (`connected` / `waiting` / `reconciling` / `unknown`), progress kind, acceptance (`pending` / `accepted` / `rejected` / `incomplete`), and availability (`not_required` / `pending` / `available` / `unavailable`); and
- active cursor, resource claims, blocker, and next gate (suppressing unchanged timeouts).

When the parent supplies an acceptance contract (such as `T0–T8` checkpoints or equivalent task IDs):

1. Read the exact contract file before dispatch and treat it as run authority.
2. Record every task and criterion individually in the transcript-local ledger with its required status, evidence, and dependencies (never collapse into a summary).
3. At each named stop checkpoint, re-read the fresh diff and raw evidence before opening the next gate.
4. Dispatch a cold read-only checker (subagent when returning in the current response, or authorized cold reviewer task) naming the exact contract path, candidate revision, read-only boundary, checkpoint, and required disposition.
5. Accept a gate only from a report bound to a native turn/event identity or authenticated SHA-256 digest that maps findings to criteria and lists unresolved blockers.

## 5. Attention, structured waits, and terminal integration

- **Live-turn vs paused observation**:
  - Keep the parent turn active while observing ready children in bounded batches within the live waiter target limit.
  - When pausing between turns or authorized heartbeat intervals, record:
    `Waiting: <who> | ends when <condition> | re-check <UTC>`
- **`needs_attention` & owner escalation**:
  - Hold the affected child and its dependants without automatically blocking unrelated ready branches.
  - Escalate owner-reserved decisions with `Decide:` (listing concrete options, trade-offs, and one recommended default); accept answers only from an interactive human turn (`Decide:`) or authenticated `ANSWER:` records.
  - After sending an authorized reply, hold the child until a newer observed checkpoint (`report_revision` strictly greater, new `report_identity_or_digest`) reports `attention_acknowledged`, `applied_decision`, and `next_gate`.
- **Bounded correction & no-progress stop**:
  - For a repairable defect within budget, continue the exact same child with only the unmet criterion, grounded finding, excluded scope, and next gate.
  - Compare the repaired revision against the reviewed one and reject unmapped scope drift (such as widened permissions or unrelated edits).
  - When the no-progress threshold is reached without a new diagnosis or materially different fix, stop looping, preserve the child and its evidence, and mark affected criteria incomplete.
- **Changed intent & terminal integration**:
  - If parent intent changes mid-run, halt new dispatch, preserve existing tasks, classify each child's relevance, and require revised acceptance before continuing.
  - Child acceptance never grants merge, publish, or cleanup authority.
  - Integrate only through the named integration owner and authorized repository lifecycle; otherwise stop with `accepted-but-not-integrated`, preserved evidence, and the exact next gate.

## 6. Terminal stop conditions

- **Complete**: Every cumulative root criterion, required proof, and required `available_artifact` gate passes with observed revision-bound evidence.
- **Input required**: Owner-reserved authority, credential, destructive action, ADR/dependency change, or scope shift blocks further progress; surface `Decide:` with options and wait.
- **No progress**: Repeated identical failure without a new diagnosis reaches the pre-resolved bound; report exact identities, preserved evidence, unmet criteria, and the next authorized gate without converting incomplete work into completion.
