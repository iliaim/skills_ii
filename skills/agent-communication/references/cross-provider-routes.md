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
2. **Received?** Search the receiver's exact transcript, or its native read, for your label line.
   After a delivered `codex queue`, a transcript that lacks it means not yet received, not lost;
   after an `indeterminate` one, it stays `indeterminate`. Either way, never send it again by any
   route: why it waits is not documented, and a second copy would also arrive. After another route,
   the message may be held, refused or dropped with no sign to the sender: report it as unconfirmed
   and tell the human.
3. **Answered?** A later receiver record names your ref or action and gives a disposition or result
   ([contract](message-contract.md#observe-progress-in-the-sender)). Until then it is not answered
   yet; observe liveness as in [exact-ID observations](../SKILL.md#normalize-exact-id-observations).

If no answer arrives within the wait your request or project sets, tell the human what is
unconfirmed and where you sent it.

## When the receiver cannot be reached

Use one route per message: the pair's native route, then the provider CLI behind feature detection,
then the mailbox. Move down only after a technical `not-sent` or a missing route. A refusal by the
human, a permission rule or the receiver's own inbound setting is a decision, not a failure: after
one, try no other route but a mailbox your task or a project rule already allows. When none works or
a refusal stops you, record `contact-unavailable` as
[SKILL.md](../SKILL.md#keep-communication-separate-from-lifecycle-control) requires, and tell the
human.
