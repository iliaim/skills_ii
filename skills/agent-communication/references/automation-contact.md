# Automation and unattended-run contact

Read this reference only for scheduled tasks, automations, launchd lanes, unattended runs, or durable automation messaging.

## Route recurring monitoring requests

When the user asks to check, watch, notify, or contact on a recurring cadence, invoke the product's
automation capability. In the Codex app, default to a heartbeat attached to the current task unless
the user explicitly requests standalone per-run work. Preserve the requested cadence and change
condition. Do not replace the recurring request with a series of user-visible tasks, and do not call
`create_thread` merely because future runs are requested.

This route creates or updates the requested automation; it does not authorize interruption, resume,
handoff, cleanup, or any other lifecycle change to the owner being monitored.

## A registry entry is not a message endpoint

Require an exact automation/label ID plus one of:

- a verified provider-native task and route;
- a scheduler-authorized live controller connection;
- a run-scoped durable mailbox; or
- an owner-safe recovery or alert route.

A visible automation name, registry record, receipt, transcript, log, or launchd label does not prove a live receiver. An automation ID is not a per-run task ID. Resolve the current automation config through its native API, then correlate a concrete run/task record.

If no route exists, report `contact-unavailable` with the exact identity tuple and controller/runbook next action. Do not kickstart, flush, reset, delete, resume, create a replacement task, or create another worktree to compensate.

## Provider-native controller routes

For Codex app-server control, an authorized live scheduler uses `turn/steer` only with the exact expected turn ID. An authorized idle persisted task can use `thread/resume` followed by `turn/start`. If the active turn is not steerable or the persisted task/rollout is unresolved, use the scheduler's durable mailbox or recovery route.

For Claude, use native live inventory and a verified Claude-to-Claude message route. Never use a session's inbox socket or token/key directly. Provider-native control is still communication, not authority to publish, clean up, or change lifecycle state.

## Durable mailbox invariants

For an automation-control implementation, allocate the run-scoped mailbox and commit its address with the run record before starting execution or advertising it as active. Bind each message to:

- automation ID;
- provider task/session and run/lifecycle IDs;
- source revision and profile/manifest digest;
- sender identity and request ID;
- creation and expiry time; and
- one durable acknowledgement.

Reject stale, mismatched, or replayed messages. The send endpoint enqueues an auditable advisory message; the automation reads it only at normal safe boundaries. Mailbox availability, unread messages, acknowledgements, or failed enqueue must never alter completion, publication, cleanup, or lifecycle eligibility.

If contact publication is lost after execution starts, keep the run visible as `active` with `contact-unavailable` and a durable owner-safe recovery address. Never hide a running but unreachable automation.

## Report the attempt

Record the timestamp, exact automation/run/provider identity, correlation evidence, route attempted, redacted message summary, result, and remaining controller action. A failed contact is not permission to interfere with the run.
