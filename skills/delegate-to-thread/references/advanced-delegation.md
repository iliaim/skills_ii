# Advanced delegation

This annex applies only when an explicitly authorized orchestration permits a direct child to create
a user-visible descendant. It adds no authority to ordinary one-task delegation.

## Bounded descendant-delegation handoff

Hierarchical user-visible task creation is not implied by authority to perform a child objective.
The direct parent must receive a signed or otherwise immutable delegation envelope before it may
create one. The envelope names the root and direct parent identities, logical child key,
destination fingerprint, depth, active and total descendant budgets, allowed actions and outcomes,
writer/resource claims, integration owner, stop rule, and a parent-issued envelope identity or digest
bound to native parent-issuance evidence. Recomputing a digest proves integrity only; it does not
authenticate the issuer.
The direct parent records a pending-create entry before each descendant creation, performs exactly one
creation call, and returns raw provider result, immutable report identity/digest, and registration
evidence to the root coordinator. Without that envelope, or when registration/reconciliation support
is unavailable, descendant creation remains held and the branch stays `indeterminate`/`incomplete`;
title, path, bounded-list absence, or a child-generated replacement never substitutes for the handoff.

When the child may write, its first message also declares a resource claim for every repository or
external shared resource it can mutate:

```text
resource_id
destination_fingerprint
paths_or_scope
access_mode
owner
base_revision
claim_interval
conflict_policy
integration_owner
```

Unknown or overlapping write claims keep dispatch held or serialized. These declarations do not imply
a runtime lock; the parent must report that limitation when no enforcing controller or provider exists.
