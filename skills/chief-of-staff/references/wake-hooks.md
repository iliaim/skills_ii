# Wake Hooks and Cross-Harness Guard Wiring

Wire [chief_guard.py](../scripts/chief_guard.py) across Claude Code, Codex, and Antigravity so `SKILLS_II_ROLE=chief` enforces the executive boundary mechanically while non-chief sessions pass through untouched.

## Behavior by `SKILLS_II_ROLE`

- **Non-chief (`SKILLS_II_ROLE` unset or `!= "chief"`)**:
  - Claude Code / Codex payloads return exit code `0` with empty output.
  - Antigravity camelCase payloads (`"toolCall"` present) return exit code `0` with `{"decision":"allow"}` on stdout so global hook installation never disrupts worker or orchestrator sessions.
- **Chief (`SKILLS_II_ROLE=chief`)**:
  - Denies project source edits (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `write_to_file`, `write_file`, `edit_file`, `replace_file_content`, `multi_replace_file_content`, `apply_patch`).
  - Allows writes only to `.agents/orchestration.json`, `.agents/orchestration-overlay.md`, `~/.config/{skills-ii,chief-of-staff}/...`, `~/.local/state/{skills-ii,chief-of-staff}/...`, and `<gemini-root>/{antigravity,antigravity-cli,antigravity-ide}/brain/...`, rejecting `..` traversal and symlinks.
  - Denies mutating shell commands (`git commit/push/merge/rebase/reset/checkout`, `npm run build`, redirections into repo files, `sed -i`, inline `python -c`), while allowing read-only inspection (`git status`, `gh issue list`) and Chief helper scripts.
  - Fails closed on malformed stdin JSON (`exit 2`).

## Claude Code (`.claude/settings.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/skills/chief-of-staff/scripts/chief_guard.py"
          }
        ]
      }
    ]
  }
}
```

## Codex (`.codex/hooks.json`)

Use `"matcher": "*"` so every Codex file-mutation and shell tool (`Edit`, `Write`, `MultiEdit`, `Bash`, `exec_command`, `shell_command`, `apply_patch`, `write_stdin`) is gated while read-only tools pass straight through:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/skills/chief-of-staff/scripts/chief_guard.py"
          }
        ]
      }
    ]
  }
}
```

## Antigravity (`.agents/hooks.json`)

Antigravity uses top-level named hook objects with flat arrays for `SessionStart` / `Stop` and grouped `{matcher, hooks}` entries for `PreToolUse`:

```json
{
  "chief-of-staff-guard": {
    "PreToolUse": [
      {
        "matcher": "write_to_file|write_file|edit_file|replace_file_content|multi_replace_file_content|run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/skills/chief-of-staff/scripts/chief_guard.py",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "type": "command",
        "command": "python3 /path/to/skills/chief-of-staff/scripts/briefing_board.py --help >/dev/null"
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "true"
      }
    ]
  }
}
```

## Zero-Token Idle-Gated Wakes

- Launch Chief with `SKILLS_II_ROLE=chief` in its environment so worker subagents (which run without `SKILLS_II_ROLE=chief`) are never blocked by `chief_guard.py`.
- Keep the headed Chief session asleep at zero token cost between events; wake only on:
  1. Direct human input (including `Decide:` responses or `/briefing` / `/setup` commands).
  2. Verified state-change notifications from `Stop` or subagent completion hooks when a stream reaches a milestone, blocks, or exhausts retries.
- Never poll in a tight loop; inspect state once per wake, refresh the `/briefing` snapshot, triage per [modes.md](modes.md), and return to idle.
