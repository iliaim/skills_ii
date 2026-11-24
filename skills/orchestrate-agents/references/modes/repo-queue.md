# Mode: `repo-queue`

Repo-queue mechanics for `.agents/orchestration.json` (`"mode": "repo-queue"` or `"auto"` with an issue/PR queue). Shared tick, decision-rights, maker-checker, delivery, and recovery invariants live in [SKILL.md](../../SKILL.md); read config and overlay only from the trusted base checkout (`main`).

## 1. Queue admission and direction ordering

1. **Discover & rank**: Run `tracker.readyCommand` (`argv`, `shell=False`) within declared scope and rank ready issues by priority and parent-chain alignment with `direction.anchorIssue`.
2. **Base premise check**: Inspect `git log` and base files to skip or close issues already resolved or duplicated by an open PR.
3. **Single-writer claim**: Run `tracker.claimCommand` before spawning a worker; serialize overlapping writers per code area or shared resource.
4. **Headroom placement**: Check per-provider `workerCap` and reserve slots for cold reviews and repair passes before invoking `dispatch-workers`.

## 2. ETag-backed wakes and zero-polling waits

- Never run `sleep` loops or tight `gh pr view` polling inside a turn; record pauses on the issue/PR as `Waiting: <who> | ends when <condition> | re-check <UTC>` (see [SKILL.md#5-never-stuck](../../SKILL.md#5-never-stuck)).
- For scheduler or hook monitoring of PR checks, reviews, and issue comments, pass HTTP `ETag` / `If-None-Match` headers (or event payloads) so `304 Not Modified` costs zero quota and wakes only on state change.
- Verify whether a `git push` or CI workflow run is active on the PR branch before treating a quiet worker as stalled or hung.

## 3. PR review, `git range-diff`, and policy checks

1. **Verdict format**: Require the cold reviewer (see [SKILL.md#3a-maker-and-checker](../../SKILL.md#3a-maker-and-checker)) to post:
   `Checker verdict (<session>, head <sha>): APPROVE|CHANGES REQUIRED`
2. **Repair delta audit**: On `CHANGES REQUIRED`, send only unmet findings to the maker on the same branch; on re-review, pass:
   `git range-diff <base>..<prior-head> <base>..<head>`
   so the checker verifies only the repair delta and rejects out-of-scope edits.
3. **Policy trigger**: Run `review.policyCommand` (if configured) on the PR diff; any match requires an extra fresh cold review at the exact `<approved-sha>`.

## 4. Exact-SHA merge and 5-point unattended gate

Merge only when `Checker verdict (<session>, head <sha>): APPROVE` and any `review.policyCommand` extra review match the current PR head `<approved-sha>`, required CI checks are green with zero conflicts, and no `Decide:` / `needs:owner` gate is open.

For unattended auto-merge (no interactive human turn confirmation), **all 5 safety gates** must also hold:
1. `merge.autoMergeEnvFlag` is configured and explicitly truthy in the trusted runtime environment;
2. `merge.matchHeadCommit` is `true` and `--match-head-commit <approved-sha>` is passed;
3. `merge.strategy` (default `--merge`) is honored without silent squash/rebase overrides;
4. the diff touches zero owner-reserved categories; and
5. `merge.publishCommand` / post-deploy smoke verification is ready to observe.

Execute the merge using the configured `<merge.strategy>` (default `--merge`) with exact-SHA protection:

```bash
gh pr merge <pr-number> <merge.strategy> --match-head-commit <approved-sha>   # default strategy: --merge
```

If base advanced and caused a merge conflict, return resolution to the maker (or obtain a fresh cold review on the new `<approved-sha>`) before merging.

## 5. Issue escalation and post-merge closeout

- **Tracker escalations**: Post `Decide:` options on the issue/PR (apply `needs:owner` if used) with `Waiting: owner | ends when ANSWER: or Decide: received | re-check <UTC>`. Accept `ANSWER:` tracker comments only after verifying the author's identity via the tracker API as required by [SKILL.md#2-decision-rights](../../SKILL.md#2-decision-rights).
- **Closeout sequence**: Confirm the merge commit on base (and `merge.publishCommand` if configured), run `tracker.closeCommand` or close the issue with the merge SHA + verification proof, retire the maker session cleanly, and remove its temporary worktree/branch.
