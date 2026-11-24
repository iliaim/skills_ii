# Provider: Codex and ChatGPT

Load only when dispatching a worker or cold reviewer to Codex or ChatGPT. Shared ownership, prompt core, checkout gates, and setup-handle rules live in [task-contract.md](../task-contract.md).

## Tier-1 native dispatch (Codex / ChatGPT caller)

1. **Fresh user-visible task**: Call `create_thread` once per logical delegation; never call twice to retry an uncertain result.
2. **History fork**: Call `fork_thread` **only** when the user explicitly requests forking completed Codex history; a fork is not fresh-task creation and never replaces a cold reviewer.
3. **Setup-only `clientThreadId` gate**: If creation returns only a `clientThreadId`, immediately run the `automatic exact-handle setup-resolution gate` in [task-contract.md#automatic-exact-handle-setup-resolution](../task-contract.md#automatic-exact-handle-setup-resolution). Confirm the real `threadId` and `hostId` via native `read_thread` before any `wait_threads` or `send_message_to_thread` call. Never resolve by title, path, listing, or transcript search.
4. **In-turn subagents**: For work that stays inside the current response rather than creating a user-visible task, use native `spawn_agent` / `send_message` / `followup_task`.

## Tier-2 CLI and cross-host dispatch

Run local or SSH Codex CLI workers with `shell=False` `argv` arrays from `~/.config/skills-ii/fleet.json` and unset `OPENAI_API_KEY` so subscription/OAuth auth is used instead of metered API billing:

- **Worker launch** (isolated worktree, `< /dev/null` prevents background/tmux stdin hangs):

```sh
env -u OPENAI_API_KEY codex exec --cd <worktree> --sandbox workspace-write "<brief>" < /dev/null
```

- **Cold read-only reviewer launch** (fresh session, no maker reasoning, read-only sandbox):

```sh
env -u OPENAI_API_KEY codex exec --cd <worktree> -s read-only "<review-brief>" < /dev/null
```

- **Resume exact persisted session** (idle writer only, verified rollout under `CODEX_HOME`):

```sh
env -u OPENAI_API_KEY codex -C <cwd> resume <session-id>
# or non-interactive single turn:
env -u OPENAI_API_KEY codex exec resume <session-id> "<follow-up>" < /dev/null
```

## Guardrails

- Check `codex --version` / `--help` on the target host before first dispatch; desktop-bundled and shell `codex` binaries may differ.
- Never run `codex exec` against the coordinator or main checkout for writable work unless `direct-local` was explicitly authorized.
- For SSH hosts, execute `codex` on the owning host over `ssh <host>` with `< /dev/null` and capture the exact thread/session ID from structured output before tracking.
