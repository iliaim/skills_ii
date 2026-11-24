# Provider: Claude Code

Load only when dispatching a worker or cold reviewer to Claude Code or Claude Desktop. Shared ownership, prompt core, and checkout gates live in [task-contract.md](../task-contract.md).

## Tier-1 native dispatch (Claude caller)

1. **Worker subagent**: Pre-create an isolated git worktree (`git worktree add`) before launching `Agent` / native subagent tools so the child starts in its assigned directory and proves `cwd` before editing.
2. **Cold reviewer subagent**: **Forbid** `isolation: "worktree"` on Reviewer subagents — it rebinds relative shell guard paths and leaves orphan worktrees on disk. Launch cold read-only reviewers directly in read-only/plan mode against the target checkout or exact commit SHA.

## Tier-2 CLI and cross-host dispatch

Unset `ANTHROPIC_API_KEY` before every launch so Claude uses subscription/OAuth auth rather than metered API credits, and lock down MCP surfaces with `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` unless the task contract explicitly names a required server:

- **Worker launch** (pre-verified worktree, interactive or headless `-p` with `< /dev/null`):

```sh
env -u ANTHROPIC_API_KEY claude -p --permission-mode acceptEdits \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  "<brief>" < /dev/null
```

- **Cold read-only reviewer launch** (`--permission-mode plan`, zero write permissions, strict MCP):

```sh
env -u ANTHROPIC_API_KEY claude -p --permission-mode plan \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  "<review-brief>" < /dev/null
```

- **Resume exact persisted session** (idle session only; never `--continue`):

```sh
env -u ANTHROPIC_API_KEY claude --resume <session-id>
# or non-interactive single turn:
env -u ANTHROPIC_API_KEY claude -p --resume <session-id> "<follow-up>" < /dev/null
```

## Guardrails

- Never start a writable worker with `bypassPermissions` unless human-approved in trusted config; prefer `acceptEdits` inside an isolated worktree with repository hooks active.
- Never resume an active writer (`--resume` on a running session risks interleaved transcript writes); verify the session is idle first.
- `--fork-session` creates a new session identity from old history and is neither fresh creation nor cold review.
