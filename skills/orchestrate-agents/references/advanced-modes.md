# Advanced orchestration modes

This annex applies only when its named mode is explicitly in scope. It adds no authority or routine
steps to an ordinary bounded graph.

## Proportionate independent assurance

The parent validates every child against its delegated criteria and remains the acceptance owner.
Ordinary work needs no additional checker when the parent can directly verify sufficient objective
evidence. Add a cold, read-only checker when user or project policy requires one or when independent
review materially improves confidence—for example consequential security, permission, destructive,
integration, deployment, rollback, shared-state, or evidence-ambiguity risk.

Use an authorized subagent when the review can return in the current response. A separate
user-visible checker task still requires explicit task-creation authority. Give the checker the
frozen criteria, exact artifact or revision, and raw evidence needed to judge them, without maker
instructions or suspected conclusions. The checker does not edit, integrate, mutate goals, or own
acceptance.

When checker acceptance is required, risky dependants and integration remain closed until its
revision-bound evidence passes. The checker must identify the exact artifact path and artifact
revision/digest it reviewed; evidence for another revision, a pre-image, or a matching title/path is
rejected. A supported finding returns to the same maker as a bounded in-scope correction; changed
reviewed evidence requires a fresh checker of the exact postimage. For a maker–checker disagreement,
obtain at most one focused evidence response and reassessment within the run's bounds. The parent
resolves from the objective criteria, not votes; unresolved material conflict goes to a pre-authorized
adjudicator or the user.

## Optional nesting

Centralized user-visible task creation is the default. A child may use authorized subagents for
bounded work returning in its current response. When it needs another user-visible task, it raises
`needs_attention`; parallelism alone is not creation authority.

Hierarchical task creation is opt-in and requires explicit acceptance of reduced root visibility.
It is not available from this skill by implication: before a child may create a user-visible
descendant, the direct parent must receive the bounded descendant-delegation envelope defined by the
delegate task contract. That envelope is the creation authority and registration handoff; a child
cannot mint or widen it. If the envelope, immutable identity, or supported registration/recovery
route is missing, hold descendant creation and return the branch incomplete. Before enabling it, set
positive depth, active, and total descendant bounds; allocation rules; permitted outcomes and
destinations; writer isolation; ownership and integration routes; and a terminal escalation rule.
Authority is non-transitive: the direct parent owns descendant observation and acceptance and returns
one integrated branch result plus known descendant identities.

Disclose the orphan window in which a parent can fail before root registration. Preserve known
identity and correlation evidence, keep branch acceptance and root visibility incomplete, and recover
only through exact supported identity or controller mechanisms. If the root requires guaranteed
real-time descendant visibility or recovery, use centralized creation or a separately authorized
controller with atomic registration.

## Optional goals and `writing-goals`

Borrow only one root objective, cumulative acceptance, bounded slices, evidence-bearing checkpoints,
no-progress detection, and proportionate assurance from `writing-goals`; do not copy its protected
roles, receipts, scripts, cursors, or state. When its protected workflow is active, that host remains
lifecycle authority. Use only work it can safely consume rather than creating a second authority.

Native goals are optional completion aids, not verification. A parent goal requires explicit
authorization, inspection of current goal state, preservation of any unrelated unfinished goal, and
at most one goal bound to the complete root outcome and cumulative acceptance.

This user-selected skill policy permits the orchestrator to offer one child-local goal when it is
relevant and helpful for a substantial task. State that permission explicitly in the child contract;
respect any user requirement or prohibition. The child inspects its own goal state, preserves an
unrelated unfinished goal, and binds a new goal only to its delegated outcome and acceptance. Do not
add a goal to a one-shot child as ceremony.

The child owns its goal and still returns required evidence. The parent does not mirror child goal
state and validates independently. Goal completion is child execution evidence; it does not establish
parent acceptance, integration, root blocked state, or root completion. No goal is a ledger,
scheduler, authority grant, callback, or durable runtime.

## Optional durable modes

Skill-only orchestration coordinates while the parent turn remains active. Match any durability
promise to a real mechanism before dispatch:

- **Live-turn:** waits and reads operate only while the coordinator turn is active. If it ends,
  report observation suspended or ownership transferred.
- **Same-thread heartbeat:** requires explicit authorization of cadence, registered scope, bounded
  actions, and a terminal stop. It is periodic polling, not immediate delivery or restart-safe
  orchestration, and never operates on queued or indeterminate identities. Retain the automation
  identity and deactivation owner. At terminal state, pause or delete the exact heartbeat through
  the supported procedure and verify it inactive. Failure leaves the orchestration lifecycle
  incomplete even if root outcome evidence passes; never claim the run fully complete while active.
- **External App Server controller:** required for event wake-up, restart recovery, atomic descendant
  registration, or guaranteed global visibility. It is separately authorized and owns durable state,
  reconciliation, and recovery; this skill contains no controller, broker, or status store.

The current skill/runtime does not itself provide atomic registration, durable wake-up, real locks or
resource leases, guaranteed callbacks, monotonic report revisions, or deduplicated event delivery.
Without the required runtime, stop before dispatch under that durability promise and offer truthful
live-turn, heartbeat, independent create-only, or separately scoped controller alternatives. Preserve
ambiguous side effects and hold dependants; never imply that a transcript, message, or notification
backfills a missing controller guarantee.
