# Mode: `repo-queue`

Use this mode when `.agents/orchestration.json` sets `"mode": "repo-queue"` or `"mode": "auto"` in a repository backed by an issue and pull-request queue (`tracker.readyCommand` or GitHub issues + PRs). Always read `.agents/orchestration.json` and `.agents/orchestration-overlay.md` from the trusted base checkout (`main`), never from an unmerged PR branch or external fork.

## 1. Queue admission and direction ordering

1. **Discover ready issues**: Run `tracker.readyCommand` (`argv` array executed with `shell=False`) or list open, unclaimed, unblocked issues within the orchestrator's declared scope (label, milestone, epic, or issue list).
2. **Order by direction**: Rank eligible work by priority and parent-chain alignment with `direction.anchorIssue`. Tasks directly unblocking `anchorIssue` or the active milestone take precedence over isolated cleanup.
3. **Premise check against base**: Before claiming or launching, inspect `git log` and current files on the base branch to verify the issue is not already resolved, duplicated by an open PR, or blocked on an open `needs:owner` question.
4. **Single-writer claim**: Run `tracker.claimCommand` before spawning a worker. Enforce one active writer per code area or shared resource; serialize overlapping tasks or stage dependent follow-ups behind the active PR.
5. **Headroom placement**: Check per-provider `workerCap` and host capacity before invoking `dispatch-workers`. Reserve headroom for cold reviews and repair passes rather than filling every slot with makers.

## 2. ETag-backed wakes and zero-polling waits

- **Never** run `sleep` loops or tight `gh pr view` polling inside an orchestrator turn.
- Record every active pause in structured form:
  `Waiting: <who> | ends when <condition> | re-check <UTC>`
- When a scheduler or wake hook monitors PR checks, reviews, or issue comments, use conditional HTTP `ETag` / `If-None-Match` requests (or webhook/CI event payloads) so `304 Not Modified` responses consume zero API budget and wake the orchestrator only on actual state changes.
- Before flagging a quiet worker as **stalled** (`>=15m` after turn end) or **hung** (`>=60m` mid-turn), verify whether a `git push` or CI workflow run is still actively executing on the worker's branch.

## 3. Maker-checker loop and `git range-diff` repairs

1. **Checker dispatch**: When a worker opens or updates a PR with passing local checks, launch a fresh cold read-only reviewer via `dispatch-workers` (`#5-launch-a-cold-reviewer`), never `fork_thread`. Pass only the tracking issue pointer, base/head SHAs, diff scope, and acceptance criteria.
2. **Structured verdict**: Require the checker to emit a revision-bound verdict line:
   `Checker verdict (<session>, head <sha>): APPROVE|CHANGES REQUIRED`
   accompanied by criterion-mapped findings, out-of-scope drift checks, and residual risks.
3. **Scoped repair (`CHANGES REQUIRED`)**:
   - Send only the grounded unmet findings back to the original maker on the same branch and worktree.
   - Require the maker to address only those findings without broadening scope or relaxing assertions.
   - On re-review, provide the exact commit delta:
     `git range-diff <base>..<prior-head> <base>..<head>`
     so the fresh checker audits only the repair changes and confirms no unintended edits landed.
4. **3-round convergence cap**: Count repair passes against `review.maxRepairRounds` (default `3`). If round 3 still returns `CHANGES REQUIRED`, stop repair loops: post a concise architectural/design note on the issue or PR explaining the divergence, run one advisory challenge or escalate via `Decide:` / `needs:owner`, and park the slice.
5. **Policy-triggered extra review**: Execute `review.policyCommand` (when configured) against the exact PR diff. Any policy match (secrets, auth, migrations, server code, deploy paths, guards, spend) requires a separate fresh cold review of the exact head SHA in addition to the routine checker approval.

## 4. Exact-SHA merge and 5-point unattended gate

Merge only when **all** of the following hold on the exact commit SHA:

1. `Checker verdict (<session>, head <sha>): APPROVE` matches the PR's current `<approved-sha>`.
2. Every extra cold review required by `review.policyCommand` or `.agents/orchestration-overlay.md` also approved `<approved-sha>`.
3. All required CI checks are green on `<approved-sha>` and the PR merges cleanly onto base without unresolved review threads.
4. No unresolved `Decide:` or `needs:owner` question remains open on the issue or PR.
5. **5-point unattended auto-merge safety gate** (mandatory whenever merging without an interactive human confirmation in-turn):
   - `merge.autoMergeEnvFlag` is configured in `.agents/orchestration.json` **and** explicitly set truthy in the trusted runtime environment;
   - `merge.matchHeadCommit` is `true` and `--match-head-commit <approved-sha>` is passed to the merge command;
   - `merge.strategy` matches the repository contract (for example `--merge`, never silent squash/rebase);
   - the diff touches zero owner-reserved categories (spend, security/credentials, look & feel, irreversible deletes, public comms); and
   - post-merge verification (`merge.publishCommand` or post-deploy smoke checks, if configured) is healthy and ready to observe.

Execute the merge strictly with exact-SHA enforcement:

```bash
gh pr merge <pr-number> --merge --match-head-commit <approved-sha>
```

Never force-merge, bypass branch hooks, or merge a branch whose head advanced after the checker approved `<approved-sha>`. If base moved and introduced a merge conflict, return the conflict resolution to the maker (or resolve cleanly with a fresh cold review of the resulting `<approved-sha>`) before re-attempting the merge.

## 5. Owner escalation and post-merge worker closeout

- **Owner escalations**:
  - Post a crisp `Decide:` block on the issue or PR (with `needs:owner` if used), listing concrete options, trade-offs, and one recommended default.
  - Record the pause as `Waiting: owner | ends when ANSWER: or Decide: received | re-check <UTC>`.
  - Bind decisions only from an interactive human turn (`Decide: <choice>`) or an authenticated `ANSWER:` comment; never apply silent timer defaults.
  - Keep independent, unblocked queue items moving while waiting on an owner decision for one issue or PR.
- **Closeout sequence**:
  1. Confirm the merge commit landed on the target base branch and run `merge.publishCommand` / smoke verification when configured.
  2. Run `tracker.closeCommand` (or close the issue with a proof comment naming the merge commit SHA and verified checks).
  3. Notify/retire the maker worker session cleanly so it does not linger or keep editing.
  4. Remove the temporary worktree and merged branch according to repository cleanup hygiene.
  5. Reconcile any remaining open PRs or dependent queue items before ending the tick.
