# Mode: `thread-graph`

Operational bridge for `.agents/orchestration.json` (`"mode": "thread-graph"` or `"auto"` without an issue queue), mapping [SKILL.md](../../SKILL.md) and `.agents/orchestration.json` onto [orchestration-contract.md](../orchestration-contract.md) and conditional [advanced-modes.md](../advanced-modes.md).

## 1. Sibling delegation & creation routing

- **Single vs graph vs existing**: Keep one attached child in `dispatch-workers` (`coordinated-single`, adopting its exact `threadId`/`hostId`/cursor once if promoted), use `agent-communication` for supplied existing identities, and invoke `dispatch-workers` (`coordinator creation handoff`) only for explicitly authorized new graph nodes; see [Root contract and readiness](../orchestration-contract.md#root-contract-and-readiness) and [Creation handoff and adoption](../orchestration-contract.md#creation-handoff-and-adoption).
- **Pending-create classification**: Record the pending-create entry before calling creation and store raw provider output first:
  - `ready` -> hand exact `threadId`/`hostId` observation to `agent-communication`.
  - `queued/unmonitorable` -> holds only a non-operable `clientThreadId` after the setup-resolution gate; never observe, contact, expect parent wake, retry creation, or unlock dependants; reconcile solely by resuming the exact pending entry.
  - `indeterminate` / `rejected` -> hold node and dependants without retry creation or title-matching; preserve raw correlation or rejection proof.

## 2. Dependency gates, writer claims, and `T0–T8` contracts

- **Dependency edges**: Open `accepted_evidence` (`source_artifact_revision_or_digest: not_applicable`) or `available_artifact` (requiring post-image `readable_path` + `artifact_observation_id`) only from backed `source_report_identity_or_digest` provenance; see [Root contract and readiness](../orchestration-contract.md#root-contract-and-readiness) and [Resource claims and writer admission](../orchestration-contract.md#resource-claims-and-writer-admission).
- **`T0–T8` & cold review**: When an acceptance contract specifies `T0–T8` or named stop checkpoints, track every criterion individually in the transcript-local ledger and require revision-bound cold review reports; see [Acceptance-contract and cold-review gates](../orchestration-contract.md#acceptance-contract-and-cold-review-gates) and [Transcript-local ledger](../orchestration-contract.md#transcript-local-ledger).

## 3. Attention, `Waiting:` / `Decide:`, and integration stops

- **Observation & pauses**: Keep the parent turn active for bounded live-turn batches, or record `Waiting: <who> | ends when <condition> | re-check <UTC>` between turns/authorized heartbeats (see [SKILL.md#5-never-stuck](../../SKILL.md#5-never-stuck)).
- **Escalations & acks**: Surface owner-reserved blockers via `Decide:` under [SKILL.md#2-decision-rights](../../SKILL.md#2-decision-rights), and enforce `attention_acknowledged`, bounded same-child corrections, and no-progress / changed-intent stops per [Observation, attention, and correction](../orchestration-contract.md#observation-attention-and-correction) and [Changed intent and terminal stops](../orchestration-contract.md#changed-intent-and-terminal-stops).
- **Integration boundary**: Child acceptance never grants integration authority; execute or report `accepted-but-not-integrated` strictly under [Integration authority](../orchestration-contract.md#integration-authority).
