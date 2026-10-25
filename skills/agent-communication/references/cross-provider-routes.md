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
| Codex to Claude | No route: mailbox, read only when that session next starts or polls | Mailbox | The place the request named |
| Any other provider | Unsupported until its exact read, inventory and message route are verified ([identity rules](../SKILL.md#establish-identity-before-contact-or-continuation)) | Unsupported | Mailbox |

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
