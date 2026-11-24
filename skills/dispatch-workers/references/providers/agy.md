# Provider: Antigravity (`agy`)

Load only when dispatching a worker or cold reviewer to Antigravity. Shared ownership, prompt core, and checkout gates live in [task-contract.md](../task-contract.md).

## Tier-1 native dispatch (Antigravity caller)

1. **In-session subagents**: Use `invoke_subagent` with `Workspace: "share"` or `"branch"` for writable workers and `Workspace: "inherit"` for cold read-only reviewers. Leave `Model` on `"inherit"` unless the user or trusted config specifies a tier.
2. **Swarm board workers**: Use `swarm` (`action: "add"`, `workspace: "share"` or `"branch"`) when coordinating multiple workers on a shared board; omit `fork` for cold reviewers so checker reasoning stays independent.

## Tier-2 CLI and cross-host dispatch

Unset **all four** Google/Vertex metered environment keys before every `agy` launch so subscription quota is used instead of metered billing:

```sh
env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_GENAI_USE_VERTEXAI -u AGY_ADC_AUTH
```

### Mandatory pre-launch guard check

Before launching any non-plan `agy` worker that can edit files or run shell commands, verify `.agents/hooks.json` exists and configures the repository's fail-closed `PreToolUse` guard. If `.agents/hooks.json` is missing or invalid on a guarded repository, **fail closed** and refuse non-plan worker dispatch until hooks are repaired.

- **Headless worker launch** (streaming JSON events, `< /dev/null`):

```sh
env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_GENAI_USE_VERTEXAI -u AGY_ADC_AUTH \
  agy -p "<brief>" --output-format stream-json < /dev/null
```

- **Cold read-only reviewer launch** (read-only/plan scope, no maker history):

```sh
env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_GENAI_USE_VERTEXAI -u AGY_ADC_AUTH \
  agy -p "<review-brief>" --output-format stream-json < /dev/null
```

- **Resume exact conversation** (idle conversation only; never `--continue`):

```sh
env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_GENAI_USE_VERTEXAI -u AGY_ADC_AUTH \
  agy --conversation <id>
```

## Guardrails

- Multi-turn caller-owned headless streams use `--input-format stream-json --output-format stream-json`; retain the observed conversation ID from the stream header.
- Never kill an idle `agy` subagent whose workspace has unlanded changes; land or extract its diff before retiring.
