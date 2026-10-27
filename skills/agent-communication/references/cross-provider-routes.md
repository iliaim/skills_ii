# Cross-provider and cross-host routes

Read this when sender and receiver are different providers or run on different hosts, or when no
native route links them. Procedures stay in the provider references; the label line and the other
message rules stay in the [message contract](message-contract.md#identify-the-action-and-roles).

Message only a receiver that your task or a project rule lets you message. Otherwise write to the
mailbox or tell the human, and leave widening that rule to the human. Judge routeability from the
sender's side. A mailbox here is a durable, auditable record that the project defines and the
receiver reads; this skill defines no format for it.

## Routes by pair

| Sender to receiver | Same host | Other host | Answer comes back through |
|---|---|---|---|
| Claude to Claude | Desktop session tool, or `ListAgents` then `SendMessage` ([Claude](claude-code-sessions.md#contact-continuation-and-creation-are-different)) | The same, only while both sessions use Remote Control | A reply message, or the place the request named |
| Claude to Codex | `codex queue` ([Codex](codex-chatgpt.md#sending-from-another-shell-or-host)) | SSH to the owning host, then `codex queue` there | The place the request named, else the rollout ([transcripts](codex-local-transcripts.md#read-the-answer-to-a-message-you-sent)) |
| Codex to Codex | `send_message_to_thread`, else `codex queue` ([Codex](codex-chatgpt.md#find-and-contact-an-existing-task)) | Native tools when they resolve that host, else SSH and `codex queue` | `wait_threads` or `read_thread`, else as for Claude to Codex |
| Codex to Claude | Exposed, verified Claude exact-session message tool; otherwise an existing mailbox, read when that session starts or polls | Verified owning-host tool or existing mailbox | The place the request named |
| Any sender to Antigravity (`agy`) | Feature-detect the [Antigravity recipient route](antigravity.md) | Verified owning-host route or existing mailbox | The verified worker output or agreed record |
| Any sender to Grok Build or Grok API | Select the actual [Grok runtime](grok.md) | Verified runtime/API route or existing mailbox | The verified worker output, API result or agreed record |
| Any other provider | Unsupported until its exact read, inventory and message route are verified ([identity rules](../SKILL.md#establish-identity-before-contact-or-continuation)) | Unsupported | Mailbox |

## Other runtimes and model providers

Choose the route by the recipient's hosting runtime and exact session, not the model's brand.
A Grok model behind an existing agent runtime uses that runtime's route. A model API request is
separate from messaging an existing browser or IDE conversation. Keep the same action identity,
disposition and observation contract across transports; verify sending, observation and wake-up
capabilities independently. A shared mailbox requires an existing authorized reader or poller;
writing a record alone neither schedules execution nor confirms receipt.

For Claude Code, the [official peer-messaging documentation](https://code.claude.com/docs/en/cross-session-messaging)
describes `ListAgents` and `SendMessage` inside Claude. Their availability there does not expose
them to a Codex caller. Prefer an actually exposed exact-session tool; without one, use the
authorized mailbox. Starting a relay model turn or resuming a session is separate execution,
with its own scope and authority, not a general shell send operation. Preserve the
[Claude reference's controls](claude-code-sessions.md#contact-continuation-and-creation-are-different).

Load [Antigravity details](antigravity.md) only for that recipient, or [Grok details](grok.md) only
for that runtime. For a worker already under an authorized caller's control, its documented
structured input/output stream is often the smallest adapter. That does not attach to an unrelated
active session, and creating a worker remains separately authorized.

These are documentation-backed leads, not locally verified provider integrations. Add only a thin
adapter for a demonstrated missing route when authorized; retain the existing message contract
instead of adding a second queue, status database or acknowledgement protocol.

## Find out what happened

Check in order and stop at the first step that fails. If you cannot decode or parse the receiver's
records, stop there, report the answer as unreadable and keep the last state you proved.

1. **Delivered?** Use the route's own result as its provider reference maps it. `not-sent` covers
   that attempt only: fix the cause, or move down a route only as the section below allows. After
   `indeterminate`, go on to step 2.
2. **Received?** Prefer the exact receiver's native read. A transcript fallback must find your exact
   label in an incoming user/message record, not in a quotation, tool result or assistant echo.
   After a delivered `codex queue`, a transcript that lacks it leaves receipt unconfirmed (not yet
   observed), not lost; a bounded or unstable read cannot prove absence. After an `indeterminate`
   send, the transport outcome stays `indeterminate`. In either case, do not send it again by any
   route: the first copy may still arrive and a second creates duplicate work risk. After another
   route, the receiver may hold, refuse or drop it with no sign to the sender: report it as unconfirmed.
   For a pending `codex queue` send, reconciliation is read-only: do not use `send_message_to_thread`
   for a status nudge, a “process the queued action” cue, or a reworded work request. Those are still
   additional deliveries. The live-task subagent trigger procedure does not apply to this route.
3. **Answered?** A later receiver record names your ref or action and gives a disposition or result
   ([contract](message-contract.md#observe-progress-in-the-sender)). Until then it is not answered
   yet; observe liveness as in [exact-ID observations](../SKILL.md#normalize-exact-id-observations).

Follow the [bounded observation procedure](message-contract.md#bound-the-observation-before-sending).
If no answer arrives within its bound, report what is unconfirmed and where you sent it. Keep a
previously proved working route `available` unless new route evidence contradicts it. An unanswered
queued message is a pending inspection result, not `contact-unavailable` merely because the receiver
has not acted. State that the work remains pending; reporting the gap does not complete the request.

## When the receiver cannot be reached

Use one route per message: the pair's native route, then the provider CLI behind feature detection,
then the mailbox. Move down only after a technical `not-sent` or a missing route. A refusal by the
human, a permission rule or the receiver's own inbound setting is a decision, not a failure: after
one, try no other route but a mailbox your task or a project rule already allows. When none works or
a refusal stops you, record `contact-unavailable` as
[SKILL.md](../SKILL.md#keep-communication-separate-from-lifecycle-control) requires, and tell the
human.
