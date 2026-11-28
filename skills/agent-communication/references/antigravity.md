# Antigravity recipient routes

Read only for an Antigravity recipient, including the `agy` CLI. The shared [message contract](message-contract.md) owns identity, authority, disposition and
observation, and [its routing rules](message-contract.md#choose-one-route-per-message) own route selection and fallback.

Distinguish an existing app/CLI conversation from a worker process already controlled by the caller. Resolve the exact conversation ID and owning host through
supported native evidence; a project name or model choice is not a session identity. Verify sending, result observation and wake-up separately before claiming a
working route.

## Native peers inside Antigravity

The [native subagent documentation](https://antigravity.google/docs/subagents?tab=cli#inter-agent-communication-and-nesting-limits) describes routing by unique
agent conversation IDs and automatic wake-up of idle subagents on incoming messages. This differs from the Codex live-subagent `send_message`/`followup_task`
distinction. Use only the actual native tools exposed in that Antigravity surface; do not invent their names or apply internal-peer behavior to an external
sender, another host or an unrelated persisted conversation. A documented wake-up still is not an action-bound ACK or verified completion. Killed subagents
cannot be reawakened according to that reference.

## Existing conversations

### Local `ConversationService` HTTP+JSON API

When Antigravity's language server is running locally, shell commands inside an agent turn receive `ANTIGRAVITY_LS_ADDRESS` (`host:port`, no scheme), `ANTIGRAVITY_CSRF_TOKEN`, and `ANTIGRAVITY_CONVERSATION_ID` (with optional `ANTIGRAVITY_PROJECT_ID`). `POST` requests to `http://$ANTIGRAVITY_LS_ADDRESS/product.v1.ConversationService/<Method>` with `Content-Type: application/json`, `Connect-Protocol-Version: 1`, and `x-antigravity-csrf-token: $ANTIGRAVITY_CSRF_TOKEN` support:

- `ListConversations`: lists interactive conversations (`pageSize`, `pageToken`, `projectId`, `parentConversationId`, `tags`, `includeArchived`). Archived and agent-started child conversations are omitted by default.
- `GetConversation`: reads a single conversation's `metadata`, `annotations`, and `state` (`summary`, `updateTime`, and `runState`: `RUN_STATE_IDLE`, `RUN_STATE_RUNNING`, or `RUN_STATE_CANCELLING`) for an exact `conversationId`.

Do not use `ConversationService` to spawn or message subagents inside an active agent turn — use the native subagent tools (`invoke_subagent`, `send_message`) instead. `runState` and `summary` are metadata leads, not an action-bound ACK or proof of task completion.

### `agentapi` CLI

The [official sidecar documentation](https://antigravity.google/docs/sidecars#agentapi) describes `agentapi send-message <conversation_id> <prompt>` within the sidecar environment. On hosts where `ANTIGRAVITY_AGENTAPI_EXE` is set or `agentapi` is on `PATH`, feature-detect the exact executable with `agentapi --help`; observed subcommands include `get-conversation-metadata <conversation_id>`, `new-conversation [--model=...] [--title=...] [--profile=...] <prompt>`, and `send-message [--title=<title>] <recipient_id> <content>`.

The installed `agy --help` alone does not establish that `agentapi` is available or authorized. Transport acceptance from `agentapi send-message` is not receiver acknowledgement; verify effects independently. Do not install a sidecar, alter configuration or invent a generic `agy send` to obtain a route. If none is verified, use only an existing authorized mailbox with an actual reader/poller, or report `contact-unavailable`. Never switch routes to bypass a refusal or compensate for an uncertain send.

## Local brain transcripts

Antigravity persists conversation transcripts on the owning host under three surface-specific brain roots (where `<gemini-root>` defaults to `~/.gemini` unless overridden by the host environment):

```text
<gemini-root>/{antigravity,antigravity-cli,antigravity-ide}/brain/<conversation-id>/.system_generated/logs/transcript.jsonl
```

Start with compact `transcript.jsonl` and read the corresponding line of `transcript_full.jsonl` only when `truncated_fields` is present. Resolve the exact `<conversation-id>` first; never scan across unrelated conversations or treat transcript recency alone as proof of a live receiver. Before resuming an idle conversation, verify turn state metadata-first (for example via `agent-session-investigation`'s `inspect_jsonl.py --backend agy`) alongside live process evidence.

## Caller-owned workers and exact-ID continuation

[Headless mode](https://antigravity.google/docs/cli/headless/) documents single-turn `agy -p "<brief>" --output-format stream-json` (for example with `< /dev/null` and Google/Vertex metered API env keys unset when host policy requires subscription quota) and multi-turn `--input-format stream-json` with `--output-format stream-json` in one caller-owned process. When an authorized caller already owns that process and its input/output, retain the observed conversation identity and correlate each result to its action/revision. A result event is evidence to check, not independent verification of every requested effect.

`agy conversations list` lists saved conversations and disk usage (`agy conversations clean` is destructive lifecycle control, never messaging); `agy remote-control` manages the remote-control background daemon. `agy --conversation <id>` (with aliases `--resume` / `-r`) resumes an exact persisted conversation and executes a turn; `--continue` (`-c`) chooses the most recent one and is never an exact-ID selector. Neither is ordinary messaging to an active owner. Use `agy --conversation <id>` only as intentional continuation when continuation authority is established and exact-ID turn-state plus process checks confirm the conversation is idle. Cross-host work uses a verified owning-host client or controller route, not a local path pretending to be remote.

The answer comes back through the verified worker output or an agreed record. For another host, use a verified owning-host route or an existing mailbox.
