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
| Claude to Codex | `codex queue`, local sessions only ([Codex](codex-chatgpt.md#sending-from-another-shell-or-host)) | SSH to the owning host, then `codex queue` there | The place the request named, else the rollout ([transcripts](codex-local-transcripts.md#read-the-answer-to-a-message-you-sent)) |
| Codex to Codex | `send_message_to_thread`, else `codex queue` ([Codex](codex-chatgpt.md#find-and-contact-an-existing-task)) | Native tools when they resolve that host, else SSH and `codex queue` | `wait_threads` or `read_thread`, else as for Claude to Codex |
| Codex to Claude | No route: mailbox, read only when that session next starts or polls | Mailbox | The place the request named |
| Any other provider, such as agy | Unsupported until its exact read, inventory and message route are verified ([identity rules](../SKILL.md#establish-identity-before-contact-or-continuation)) | Unsupported | Mailbox |

A message sent with `codex queue` cannot be withdrawn, and nothing wakes a Claude session to read
its mailbox.

## Find out what happened

Check in order and stop at the first step that fails:

1. **Delivered?** Use the route's own result as its provider reference maps it. `not-sent` covers
   that attempt only: fix the cause, or move to the next route below.
2. **Received?** Search the receiver's exact transcript, or its native read, for your label line.
   If a cleanly read transcript lacks it, the message is delivered but not yet received, not lost.
   After `codex queue`, do not send it again: why it waits is not documented, and a second copy
   would also arrive.
3. **Answered?** A later receiver record names your ref or action and gives a disposition or result
   ([contract](message-contract.md#observe-progress-in-the-sender)). Until then it is not answered
   yet; observe liveness as in [exact-ID observations](../SKILL.md#normalize-exact-id-observations).
4. **Readable?** If you cannot decode or parse the receiver's records, report the answer as
   unreadable and keep the last state you proved.

If no answer arrives within the wait your request or project sets, tell the human what is
unconfirmed and where it waits.

## When the receiver cannot be reached

Use one route per message: the pair's native route, then the provider CLI behind feature detection,
then the mailbox. Move down only after `not-sent` or an unavailable route. When none works, record
`contact-unavailable` as
[SKILL.md](../SKILL.md#keep-communication-separate-from-lifecycle-control) requires.
