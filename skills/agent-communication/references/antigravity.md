# Antigravity recipient routes

Read only for an Antigravity recipient, including the `agy` CLI. The shared
[message contract](message-contract.md) owns identity, authority, disposition and observation;
[cross-provider routes](cross-provider-routes.md) owns cross-runtime/host selection and fallback.

Distinguish an existing app/CLI conversation from a worker process already controlled by the
caller. Resolve the exact conversation ID and owning host through supported native evidence;
a project name or model choice is not a session identity. Verify sending, result observation and
wake-up separately before claiming a working route.

## Native peers inside Antigravity

The [native subagent documentation](https://antigravity.google/docs/subagents?tab=cli#inter-agent-communication-and-nesting-limits)
describes routing by unique agent conversation IDs and automatic wake-up of idle subagents on
incoming messages. This differs from the Codex live-subagent `send_message`/`followup_task`
distinction. Use only the actual native tools exposed in that Antigravity surface; do not invent
their names or apply internal-peer behavior to an external Codex sender, another host or an
unrelated persisted conversation. A documented wake-up still is not an action-bound ACK or verified
completion. Killed subagents cannot be reawakened according to that reference.

## Existing conversations

The [official sidecar documentation](https://antigravity.google/docs/sidecars#agentapi) describes
`agentapi send-message <conversation_id> <prompt>` within the sidecar environment. This is a
capability lead, not proof that an external sender has that executable, target access, a supported
exact read/status route or wake-up guarantees. Feature-detect the owning host's actual surface.
The installed `agy --help` alone does not establish that `agentapi` is externally available.
Do not install a sidecar, alter configuration or invent a generic `agy send` to obtain a route.
If none is verified, use only an existing authorized mailbox with an actual reader/poller, or report
contact unavailable. Never switch routes to bypass a refusal or compensate for an uncertain send.

## Caller-owned workers

[Headless mode](https://antigravity.google/docs/cli/headless/) documents `--input-format stream-json`
with `--output-format stream-json` for multiple turns in one process. When an authorized caller
already owns that process and its input/output, retain the observed conversation identity and
correlate each result to its action/revision. A result event is evidence to check, not independent
verification of every requested effect.

`agy --conversation <id>` resumes a conversation and executes a turn; `--continue` chooses the
most recent one. Neither is ordinary messaging to an active owner. Starting/resuming a worker needs
its own authority and exclusive execution context; this reference grants neither. Cross-host work
uses a verified owning-host client or controller route, not a local path pretending to be remote.

Documentation and local CLI help were checked on 2026-10-27. No Antigravity session was contacted,
and no live cross-runtime delivery or wake-up behavior was verified.
