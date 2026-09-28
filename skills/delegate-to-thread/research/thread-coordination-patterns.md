# Parent/child task coordination patterns

Research date: 2026-08-31. This is non-normative design evidence, not an operating procedure.
Product behavior can change; current tool descriptions remain authoritative for callable behavior,
and [the task contract](../references/task-contract.md) is the sole skill-level operating contract.

## Executive finding

For a user-visible Codex task created by another task, the best currently supported coordination
pattern is:

1. create exactly one task and retain its stable `threadId` and `hostId`;
2. make the child transcript the primary progress record;
3. while coordinated completion was requested, use cursor-aware, bounded `wait_threads` calls;
4. wake only for completion or attention, suppress unchanged snapshots, and pass each returned cursor
   as the next `afterCursor`;
5. fetch more with `read_thread` only if the terminal wait lacks evidence needed to evaluate the
   parent's acceptance criteria; and
6. use `send_message_to_thread` only for a material correction, new context, or an answer to a child
   question.

This is not constant short polling. It is an application-level event wait resembling bounded long
polling: the caller leaves one request pending, the service returns on a meaningful event or timeout,
and the caller resumes from a cursor. RFC 6202 explains why long polling reduces the latency and
resource trade-off of frequent short polling by replying when an event, status, or timeout occurs
([RFC 6202, section 2](https://www.rfc-editor.org/rfc/rfc6202.html#section-2)).

There is **no exposed built-in child-to-creator callback, parent subscription, webhook, or automatic
result propagation for separately created user-visible tasks** in the live desktop task tools. The
creator must wait/read, or return ownership to the user. This differs from internal subagent
workflows: OpenAI documents that the main thread collects subagent results into its final response
([Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)). Do not infer that behavior
for independent sidebar tasks.

## Why creation guards are not anti-delegation

The skill's purpose is to create a separate task. Its route checks should therefore read as
**classification guards**, not as a general instruction to avoid creation:

- if the user asked for a new, independently navigable task, creation is the intended action;
- if the user asked to continue an existing task, fork history, or run an internal subagent whose
  result automatically returns to the current response, those are different operations;
- once the new-task route is established and the readiness gate passes, the workflow should create
  one logical delegation rather than reconsidering delegation at every step.

This distinction matches OpenAI's public guidance: use separate chats for independent outcomes, keep
related context in a project, and avoid concurrent write access to the same source
([Long-running work](https://learn.chatgpt.com/docs/long-running-work),
[Projects and chats](https://learn.chatgpt.com/docs/projects)).

## What the desktop task surface supports now

The following is derived from the live tool descriptions available on 2026-08-31, not from an
external public API promise.

| Mechanism | Current role | Important limit |
|---|---|---|
| `create_thread` | Starts a user-owned Codex task or ChatGPT Work chat. A ready local task returns a `threadId` and `hostId`; worktree setup can return only a `clientThreadId`. | Creation is asynchronous. A queued client ID is not an operable task ID and cannot be passed to task tools. |
| `wait_threads` | Waits for the first of up to eight **Codex** tasks to complete or need attention. A zero timeout is a snapshot; bounded waits can return a cursor and compact progress. | Commentary does not wake the wait. It is not documented for ChatGPT Work chats. An up-to-date cursor suppresses previously delivered final text. |
| `read_thread` | Reads recent status and turn summaries for one task or chat; optional cursors page into older turns. | Its cursor is backward pagination, not a forward event-subscription cursor. Repeated reads are ordinary polling. |
| `send_message_to_thread` | Sends a visible follow-up prompt to an exact existing task or chat. | It is a user-visible message and may trigger another turn. It is not a hidden status/event channel and does not by itself expand authority. |
| Desktop notifications and Activity | Tell the human when a chat is unread, running, waiting, ready, or blocked. | They do not resume the originating agent or deliver the child's evidence into the parent transcript. See [Notifications](https://learn.chatgpt.com/docs/notifications). |
| Heartbeat/scheduled automation | Can wake the current local task on a schedule when the user explicitly asks for recurring monitoring or a later follow-up. | It is time-driven polling, not a child completion subscription. It should not be presented as an event callback. |

`send_message_to_thread` is generic peer messaging when an exact destination identity is known, but
the creation surface exposes no native `replyToParent`, parent-task identity, callback contract, or
typed completion event. Repurposing a visible follow-up message as a hidden callback would blur user
authorship, trigger semantics, and authorization. The safer current design is for the child to report
inside its own transcript and for the parent to observe it through the supported wait.

### Current coordination sequence

```text
parent task                       Codex service                    child task
    | create_thread(contract) -------->|                              |
    |<---- threadId + hostId -----------|                              |
    | wait_threads(id, cursor?) ------->|---- observe lifecycle ------>|
    |       [held until attention, completion, or timeout]             |
    |<---- state/evidence + cursor -----|<---- child transcript --------|
    | map terminal evidence to parent acceptance                       |
    | read_thread(id) only if evidence is missing                       |
```

If the parent finishes its turn after creation, it is no longer waiting and will not autonomously
resume merely because the child finishes. The human can use desktop notifications/Activity and then
return to either task. If the user requested create-only delegation, that ownership return is the
correct outcome rather than an incomplete orchestration loop.

## Operating implications

The dated observations above motivated the current contract, but they do not define it. Use
[the task contract](../references/task-contract.md) for creation outcomes, recovery, observation,
freshness, and completion. Keeping those rules in one place prevents research snapshots from
becoming a second, stale workflow.

## Open platform issue: setup-only creation handles

The live desktop runtime can return a `clientThreadId` while worktree setup is still in progress.
That value is a setup correlation, not an operable task ID: it cannot be passed to `read_thread`,
`wait_threads`, or `send_message_to_thread`. The public task surface still exposes no exact resolver,
but the local desktop can persist an exact setup-to-task binding that the skill may inspect through its
bounded recovery gate.

The smallest acceptable runtime fix is one of these:

1. Make `create_thread` wait for registration and return `{ threadId, hostId }`; or
2. If setup must remain asynchronous, add exactly
   `wait_thread_creation(clientThreadId)` with a discriminated result:
   `ready → { threadId, hostId }`, `pending`, or explicit `failed`/`expired`.

The runtime must own the handle namespace and bind each setup handle to one create attempt, host, and
destination. Any runtime resolver or local binding adapter must map only that exact handle, return no
bare candidate UUID, make setup failure explicit, and never require a caller-generated token,
title/path matching, or a second create call. After resolution, the caller confirms the real ID with
`read_thread` and may then use `wait_threads`.

Acceptance checks are intentionally small: immediate creation returns a real ID; delayed creation
resolves once when an exact binding is available; absent, ambiguous, stale, or failed setup remains
fail-closed without a duplicate; and setup-only IDs remain rejected by task operations. No event bus,
webhook, parent wake-up, or idempotency infrastructure is required for this issue.

When no exact binding can be proven, use native subagents when the parent must consume the result
immediately. Separate user-visible tasks remain valid for independent work, but the delegation skill
always attempts exact setup recovery before returning a queued/unmonitorable state. No event bus, webhook, parent wake-up, or idempotency infrastructure is required for this issue.

## Deferred platform alternatives

These are future platform possibilities, not requirements for the issue above. Do not add them to the
skill or runtime until the minimal creation-identity problem is fixed and a separate need is proven.

### 1. Creation returns a durable operation resource

HTTP `202 Accepted` is intentionally noncommittal; RFC 9110 says its representation ought to describe
the current status and point to or embed a status monitor
([RFC 9110, section 15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)). A task create
response should therefore return, atomically:

- `taskId` and `parentTaskId` (when a parent relationship exists);
- `status`, `createdAt`, and a monotonic revision;
- a canonical status/result locator;
- an event cursor or subscription locator; and
- the caller's stable idempotency key echoed back.

The status resource should have a small, documented state machine such as `queued`, `running`,
`needs_input`, `succeeded`, `failed`, and `cancelled`. Progress text is evidence attached to a state,
not a substitute for state.

### 2. Offer both pull and push observation

- **Bounded long poll / event wait:** keep the existing low-overhead default. Accept a last-seen cursor
  and return on a newer meaningful event or timeout. This is easy to authorize and works without a
  public callback endpoint.
- **SSE:** useful for a live UI that needs a one-way event stream. The HTML Standard defines event IDs,
  reconnection, and `Last-Event-ID`, allowing a client to resume after a broken connection
  ([Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)).
- **Webhook:** useful when an orchestrator must be awakened after it is no longer holding a request.
  OpenAI's own API webhooks deliver events to a controlled HTTP endpoint, require signature
  verification, retry failed delivery with exponential backoff, and may deliver duplicates that must
  be deduplicated by webhook ID
  ([OpenAI webhooks](https://developers.openai.com/api/docs/guides/webhooks)).
- **Brokered pub/sub or queue:** useful for high fan-out, durable processing, or several independent
  consumers. MQTT is an OASIS publish/subscribe standard that explicitly decouples applications and
  defines at-most-once, at-least-once, and exactly-once delivery modes
  ([MQTT 5.0](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)). This is infrastructure,
  not something the present skill should pretend exists.

For the current desktop skill, bounded wait is the right default. SSE, webhooks, and brokers are
future platform/API choices; no exposed task tool currently creates such a subscription.

### 3. Use typed, correlated, deduplicable events

A completion signal should be small and should point to the authoritative result rather than copy an
entire transcript. OpenAI's webhook example follows this pattern: a `response.completed` event carries
the response ID, then the receiver retrieves the response
([OpenAI webhooks](https://developers.openai.com/api/docs/guides/webhooks)).

A task event envelope should include at least:

```text
eventId, eventType, occurredAt, taskId, parentTaskId,
correlationId, sequence/revision, status, resultRef, causationId
```

CloudEvents requires a producer-scoped unique `source` + `id` pair and explicitly permits consumers to
treat the same pair as a duplicate
([CloudEvents specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#required-attributes)).
AsyncAPI defines correlation IDs for message tracing/matching and an explicit reply address/channel for
request-reply operations
([AsyncAPI 3.0 correlation ID](https://www.asyncapi.com/docs/reference/specification/v3.0.0#correlation-id-object),
[AsyncAPI operation reply](https://www.asyncapi.com/docs/reference/specification/v3.0.0#operation-reply-object)).
These are good models for a future `parentTaskId`/`correlationId` contract.

### 4. Make retries safe

Creation and event delivery cross failure boundaries: a timeout does not prove that no side effect
occurred. A future create API should accept a client-generated idempotency key bound to the exact
logical request, return the same operation identity for a replay, and reject reuse with a different
payload. The IETF HTTPAPI working-group draft describes this use of `Idempotency-Key` for fault-tolerant
`POST`/`PATCH`; it remains an Internet-Draft rather than a final RFC
([Idempotency-Key draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)).

For event delivery, assume at-least-once unless the contract proves otherwise: verify signatures,
deduplicate by stable event ID, process idempotently, acknowledge quickly, and fetch the canonical task
resource before taking consequential action. OpenAI's webhook guidance demonstrates this retry,
deduplication, fast-acknowledgement, and signature-verification model.

## Recommended direction for `delegate-to-thread`

1. Keep the route guard, but phrase it positively: invocation means “create a separate task” once the
   explicit request and readiness gate establish that route.
2. Choose an explicit pre-dispatch commitment: `create-only`, terminal coordination with a supported
   waiter, or bounded-best-effort observation.
3. For coordinated ready Codex tasks, standardize on cursor-aware bounded `wait_threads`; do not use
   repeated `read_thread` polling.
4. State plainly that separate tasks do not automatically report into the creator. Their transcript
   is the source record, and the creator observes it.
5. Treat human desktop notifications as a user convenience, not an orchestration callback.
6. Do not simulate webhooks with visible peer messages or scheduled heartbeats.
7. Keep event subscriptions, parent wake-up, webhooks, and idempotency infrastructure deferred; they
   are not part of this fix.
