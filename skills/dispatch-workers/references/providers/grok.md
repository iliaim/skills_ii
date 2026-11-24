# Provider: Grok and Label-Queued Remote Runners

Load only when dispatching work to a Grok runtime or a label-queued external/remote bot (`grok-bot` pattern). Shared ownership, prompt core, checkout gates, and setup-handle rules live in [task-contract.md](../task-contract.md).

## Dispatch modes

| Mode | When to use | Tracking / completion gate |
|---|---|---|
| Label-queued remote runner (`grok-bot`) | Task requires external dashboards, remote consoles, or host privileges unavailable locally | Terminal outcome label (`grok-bot-done` / `grok-bot-blocked`) + post-condition proof |
| Direct Grok CLI (`grok`) | Local or SSH host in `~/.config/skills-ii/fleet.json` has `grok` enabled | Exact session ID + stdout/ACP result + independent repo check |

## Label-queued external / remote bot handoff (`grok-bot`)

When a task requires privileges or consoles unavailable on local worker hosts (external cloud dashboards, DNS/registrar panels, remote host consoles, or cross-agent external administration), dispatch via the repository's label-queued issue runner (`grok-bot` or the queue label configured in `.agents/orchestration.json`):

1. **Zero secrets in issues**: Never write API keys, tokens, passwords, session cookies, or private host credentials into the issue title, body, or comments. Name only the credential store or path on the runner host where the remote bot reads them.
2. **Structured handoff issue**: Open or update an issue titled `<Runner>: <concise action>` with the queue label (`grok-bot`), including:
   - why the remote runner handoff is required;
   - exact steps or target outcome and post-condition verification checks;
   - related issue/PR links; and
   - explicit owner-approval proof if the action falls under owner-reserved authority.
3. **Re-queuing an existing issue**: Update the issue body with the new instructions, clear any stale outcome labels, and remove then re-add the `grok-bot` queue label so a fresh pickup cycle starts cleanly.
4. **Outcome-label verification**: Never infer pickup or completion from free-form comment text alone. Confirm the remote runner applied its terminal outcome label (for example `grok-bot-done` vs `grok-bot-blocked`) and verify the linked post-condition before unblocking dependent work.

## Direct Grok CLI / API dispatch

When `~/.config/skills-ii/fleet.json` or `.agents/orchestration.json` enables direct `grok` CLI execution:

- **Feature-detect first**: Verify the installed `grok` binary (`grok --help`, `grok agent stdio`) on the target host before first dispatch; installed flags can differ from web docs.
- **Metered spend & keys**: Unset metered API keys when subscription/OAuth auth is configured; require explicit owner spend authorization before running metered `XAI_API_KEY` API dispatches.
- **Headless / stdin discipline**: Pass `< /dev/null` on one-shot headless invocations (`grok -p "<brief>" < /dev/null`) so background shells never hang waiting on stdin; use structured ACP/stdio only when the caller explicitly manages that stream.
- **Idle-only resume**: Resume an idle persisted session strictly by exact ID (`grok --resume <session-id>`), never `--continue`.
- **Session-creation distinction**: Never treat `--session-id` as resume; local CLI `--session-id` starts a new conversation unless paired with `--fork-session`.
- **Cold review**: Run read-only checks against the exact commit SHA without passing maker reasoning or reusing a writable session.
