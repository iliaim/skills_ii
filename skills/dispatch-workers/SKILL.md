---
name: dispatch-workers
description: Launch, review, and resume one worker or cold read-only reviewer across Codex, Claude Code, Antigravity, or Grok on local or SSH hosts. Use for single-worker launches, cold reviews, or coordinator creation handoffs with explicit ownership and isolated checkout context; Not for multi-task graph coordination (use orchestrate-agents), existing-task messaging (use agent-communication), or executive triage (use chief-of-staff).
license: MIT
---

# Dispatch Workers

Launch one scoped worker or cold read-only reviewer across **Tier-1 native delegation** (same-provider `create_thread`, `invoke_subagent`, `Agent`, or `swarm`) or **Tier-2 cross-provider CLI/tmux dispatch** (`codex`, `claude`, `agy`, or `grok` across local or SSH hosts).

Load [the task contract](references/task-contract.md) for shared readiness, prompt, checkout, and setup-recovery rules. Load **only** the selected target provider reference below for provider-specific launch, reviewer, API-key-unset, and resume mechanics.

## Configuration and precedence

Read repository configuration **only from the trusted base checkout** (for example `main`), never from an unmerged PR branch or external fork:

1. **Repo contract (`.agents/orchestration.json`)**:
   - Supplies machine-readable `tracker` commands (`readyCommand`, `claimCommand`, `closeCommand`), `runtime.commandPrefix`, `review` settings, and default provider/worktree rules.
   - Every `*Command` and `commandPrefix` field MUST be `null` or a `list[str]` `argv` array executed with `shell=False`.
2. **Repo overlay (`.agents/orchestration-overlay.md`)**:
   - Supplies repository-specific check commands, guard prerequisites, escalation boundaries, and code-area ownership rules.
3. **Private per-user fleet (`~/.config/skills-ii/fleet.json`, mode `0600`)**:
   - Supplies `hosts` (`transport`: local or SSH), `providers` (`enabled`, `binary`, `workerCap`), and local worktree/tmux placement settings.
   - Reject symlinks when reading or updating `fleet.json`, and never commit `fleet.json`, host credentials, or local machine topology to any repository.

Precedence order:
- `AGENTS.md` and repository hard safety boundaries outrank all configuration files.
- `.agents/orchestration-overlay.md` refines repository policy without weakening `AGENTS.md`.
- `.agents/orchestration.json` supplies machine-readable repository defaults and commands.
- `~/.config/skills-ii/fleet.json` resolves concrete local/SSH host placement and provider binaries.

## 1. Pick unclaimed work

Verify launch authority and claim status before creating any worktree or worker:

- **Authorization**: Require one clear trigger—an explicit `$dispatch-workers` execution request, a direct user request to launch/assign one separate task, a required cold review gate, or one ready child requested by `orchestrate-agents` (`coordinator creation handoff`). Review, explain, test, or dry-run requests never authorize live creation; an explicit no-create instruction always vetoes creation.
- **Route once**:
  - Multi-task dependency graphs or queue sweeps -> route to `orchestrate-agents`.
  - Existing task lookup, read, or message -> route to `agent-communication` (never create a replacement because discovery failed).
  - Historical session forensics -> route to `agent-session-investigation`.
  - Explicit history fork -> route to the provider's native fork operation (a fork is not fresh-task creation).
- **Claim before launch**: When dispatching from a repository queue, confirm the issue or slice is unclaimed and run `tracker.claimCommand` (or equivalent claim lock) before worktree creation. Hold on claim conflict (`exit 4`) or open dependency blockers.
- **Ownership mode**:

| Mode | When to use | Post-launch owner |
|---|---|---|
| `independent-create-only` | User wants a standalone task and takes ownership immediately | User / standalone task |
| `coordinated-single` | Caller stays responsible for observing one child to completion | Caller (bounded observation) |
| `coordinator creation handoff` | Governing `orchestrate-agents` run requests one ready graph child | `orchestrate-agents` (caller returns evidence only) |

Do not infer a stronger ownership commitment merely because a destination could support one, and never promise terminal coordination when the backing runtime lacks a supported terminal-or-attention observer.

## 2. Choose host, provider and model

Choose the target host, execution tier, and model from live availability and `~/.config/skills-ii/fleet.json` capacity:

- **Tier-1 native delegation**: Use same-provider native tools (`create_thread`, `invoke_subagent`, `Agent`, or `swarm`) when caller and child share a harness and neither cross-provider review nor an SSH host is required.
- **Tier-2 cross-provider CLI/tmux dispatch**: Use `codex`, `claude`, `agy`, or `grok` over local `shell=False` subprocesses, tmux sessions, or SSH hosts listed in `fleet.json` (`hosts` / `providers.<name>.binary`) when targeting another provider or remote machine.
- **Verify headroom first**: Check `providers.<name>.enabled` and `workerCap`, active processes on the host, and worktree/disk space before spawning.
- **Lazy provider reference (load only the chosen target)**:
  - Codex / ChatGPT -> [references/providers/codex.md](references/providers/codex.md)
  - Claude Code -> [references/providers/claude.md](references/providers/claude.md)
  - Antigravity (`agy`) -> [references/providers/agy.md](references/providers/agy.md)
  - Grok / label-queued remote runner -> [references/providers/grok.md](references/providers/grok.md)

Never invent model identifiers or guess host headroom; use the configured default from `.agents/orchestration.json` / `fleet.json` (or inherit the caller's model) unless explicitly overridden.

## 3. Write the brief

Build a minimum-sufficient, pointer-first first message under [task-contract.md](references/task-contract.md#contents). Never copy whole transcripts, private prompts, secrets, or parent polling internals into the child brief:

- **Core contract**:
  - One observable objective (and parent slice relationship if attached).
  - Included and excluded scope plus authority and approval boundaries.
  - Cumulative, behaviour-level acceptance criteria and strongest practical proof.
  - Required deliverable and explicit `success`, `input-required`, and `no-progress` stop conditions.
- **Repository execution context** ([task-contract.md#repository-execution-context](references/task-contract.md#repository-execution-context)):
  - Specify the exact project/path, execution mode (`managed-worktree` by default, or explicitly authorized `direct-local`), base revision or starting-state rule, and write authority.
  - Require the child to prove its actual checkout (`cwd`, worktree root, branch, base SHA) before its first edit, and forbid silent fallback from an isolated worktree to a shared checkout.
- **Direct-execution boundary**:
  - Include verbatim: `Implement this objective directly in the assigned task. Do not invoke dispatch-workers, orchestrate-agents, create another user-visible task, fork, or hand off a descendant unless this handoff explicitly grants descendant authority.`
  - Any delegation envelope or wrapper is provenance only; grant descendant creation solely under [advanced-delegation.md#bounded-descendant-delegation-handoff](references/advanced-delegation.md#bounded-descendant-delegation-handoff).
- **Attached-child additions**:
  - For `coordinated-single` and `coordinator creation handoff`, require evidence-bearing checkpoints and the canonical terminal report in [task-contract.md#attached-child-reporting](references/task-contract.md#attached-child-reporting).
  - For every writable attached child, declare [writable-child resource claims](references/task-contract.md#writable-child-resource-claims) (also in [advanced-delegation.md](references/advanced-delegation.md)).

## 4. Launch a worker

1. **Pass the readiness gate**: Verify live project/host metadata, isolated worktree availability (`managed-worktree` unless `direct-local` was explicitly authorized), pre-launch guard prerequisites in the chosen provider reference, and resolution of any user-owned ambiguity (`Decide:` / `ask-smart-questions`).
2. **Launch once**: Record pending-create metadata (`logical_child_key`, `contract_digest`, `destination_fingerprint`, `attempt`) and execute **one** launch call via the selected Tier-1 tool or Tier-2 `argv` command. Never call creation twice for one logical delegation.
3. **Classify raw outcome before reporting execution**:

| Raw provider outcome | Classification & required next action |
|---|---|
| Operable `threadId` / `sessionId` (and `hostId`) | `ready` — confirm/bind identity; emit created-task directive if desktop surface requires it. |
| Setup-only `clientThreadId` handle | `queued/unmonitorable` — run the `automatic exact-handle setup-resolution gate` ([task-contract.md#automatic-exact-handle-setup-resolution](references/task-contract.md#automatic-exact-handle-setup-resolution)). |
| Uncertain side effect / transport error | `indeterminate` — preserve correlation evidence; reconcile read-only without re-creating. |
| Explicit refusal / validation failure | `rejected` — preserve rejection proof; do not retry creation silently. |

The `automatic exact-handle setup-resolution gate` is `mandatory for every ownership mode` and runs again automatically whenever an exact pending setup entry is resumed. Confirm the resolved ID with native `read_thread` before passing it to task tools. `Never` invent a second caller token or resolve by `title`, `path`, bounded listing, or transcript search.

## 5. Launch a cold reviewer

Use a fresh, read-only checker whenever verification must stay independent of the maker:

- **Cold context only**: Never use `fork_thread` or session forks, never share maker chain-of-thought or desired conclusions, and never review code you authored or closely steered.
- **Minimal review brief**: Pass only the target checkout or exact commit SHA, diff/PR reference, acceptance contract path, and required output format (`APPROVED` vs `CHANGES REQUIRED`, mapped criterion-by-criterion to observed checks and files).
- **Read-only enforcement**: Launch with the target provider's read-only/plan mode from `references/providers/<provider>.md` so the checker cannot edit files, run mutating commands, or merge its own review.

## 6. Track, message and resume

- **Ownership handoff**: `independent-create-only` returns ownership immediately; `coordinator creation handoff` hands raw and derived creation evidence back to `orchestrate-agents` without observing; `coordinated-single` retains bounded observation via [task-contract.md#observation-results](references/task-contract.md#observation-results) and `agent-communication`.
- **Exact identity only**: Wait, read, message, and resume strictly by confirmed `threadId` / `sessionId` + `hostId`. Treat `send_message_to_thread` as best-effort evidence delivery only—it never wakes or resumes an ended parent turn.
- **Idle-only resume**: Verify the target session is idle and persisted before resuming by exact ID per the chosen provider reference; never resume an active writer and never use `--continue` for targeted owner continuation.
- **Lifecycle safety**: Never archive, interrupt, merge, publish, or delete a worker's branch or worktree unless separately authorized after integration verification.

## 7. Scale

- **Enforce hard ceilings**: Check active worker caps, host memory/disk headroom, and provider limits in `.agents/orchestration.json` and `~/.config/skills-ii/fleet.json` before dispatching parallel workers.
- **One writer per code area**: Serialize overlapping writes to the same branch, worktree, database, or shared external target; concurrent isolated worktrees require a named integration owner and post-image conflict verification.
- **Promote graphs to `orchestrate-agents`**: When one `coordinated-single` worker grows into a multi-node dependency graph or wave of issues, hand over its exact ID, host, cursor, and evidence to `orchestrate-agents` rather than tracking a graph inside `dispatch-workers`.
