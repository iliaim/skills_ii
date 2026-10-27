# Grok recipient routes

Read only for a Grok recipient. First identify whether it is Grok Build, an API conversation, a
browser chat, or a Grok model hosted in another runtime. Use the hosting runtime's reference for
the last case. The shared [message contract](message-contract.md) owns identity, authority,
disposition and observation; [cross-provider routes](cross-provider-routes.md) owns cross-host
selection and fallback.

## Grok Build

[Official headless and ACP documentation](https://docs.x.ai/build/cli/headless-scripting) describes
programmatic workers; the [CLI reference](https://docs.x.ai/build/cli/reference) documents
`grok agent stdio`. Feature-detect the installed executable and selected subcommand before use.
An authorized caller-owned worker may expose structured input/output through a supported client.
Bind the observed native session to the owning host, correlate results to action/revision and check
required effects independently. This does not establish a message route to an arbitrary live TUI.

Installed help can differ from web examples. In the local help checked on 2026-10-27,
`--session-id` creates a new conversation and requires `--fork-session` when combined with resume;
do not infer continuation from that flag. `--resume` executes in an existing session, while
`--continue` selects the latest session in the directory. Neither is ordinary contact with an active
writer. CLI inventory/export or leader-management capabilities alone do not prove message delivery.
Do not probe private leader sockets or start a second writer to obtain a route.

## API and browser conversations

The [Responses API documentation](https://docs.x.ai/developers/model-capabilities/text/comparison)
describes continuation with `previous_response_id`. That binds an API conversation, not an existing
grok.com chat. Use only an authorized API integration with its actual response IDs and observable
results. API access does not establish access to the user's browser conversation or a running
coding session, and a completed API response does not by itself verify external tool effects.

## No verified route

If exact native identity, an authorized sending route or usable result observation is unavailable,
report that gap and use only an existing authorized mailbox with a reader/poller. Cross-host
communication needs an actual owning-host/runtime route; a shared filename does not provide it.
No Grok session was contacted during the local help check, and no live cross-runtime delivery,
authentication or wake-up behavior was verified. Starting/resuming workers or configuring bridges
requires separate authority; this reference grants none.
