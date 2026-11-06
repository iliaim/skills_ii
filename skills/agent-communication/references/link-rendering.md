# Safe link rendering

Read this reference only when a task or evidence report needs clickable links. The entrypoint owns
identity verification, recipient scope, privacy/redaction and message routeability; those rules apply
whether or not this reference is loaded.

## Task links

A clickable task link requires a successfully resolved exact provider-native URL whose scheme, host,
backing kind, host/account/project and embedded exact ID match the correlated identity evidence.
Keep unresolved or conflicting candidates as plain text. Do not label them `Task` or `Task ID`, and
include a candidate ID only when it was supplied explicitly or exactly observed.

Treat every interpolated value as untrusted, including names, metadata, IDs, summaries, native results,
questions, labels and destinations. Render task names as single-line Markdown/HTML-escaped text only
after verifying the destination. Reject control characters and line breaks; omit fields when safe
serialization is unavailable. Render non-destination fields as escaped plain text with autolinking
disabled, so URL-shaped summaries, questions, evidence descriptions or native results cannot become
links.

Allow only these destinations:

- An exact, verified provider-native route.
- HTTPS to the exact verified GitHub host and repository, with no user information or non-default
  port.
- An absolute local path in the same authorized context.

Canonicalize destinations before checking them. Reject redirects, uncertain parsing or allowlist
validation, and all other schemes or hosts, including `javascript:`, `data:`, `file:`, `blob:` and
`vbscript:`. When the navigation link is `unavailable` or `unknown`, show that status and keep the task
name as escaped plain text. This does not change message `routeability`.

## Evidence and artifact links

Add durable artifact links only when verified and relevant. Each link must be current, visible to the
recipient, non-sensitive and bound to the same exact task tuple, repository identity and immutable
evidence revision or digest. Apply the entrypoint's recipient-scope privacy gate to labels and
destinations.

Mutable locations are navigation aids, not proof. Label them `navigation-only`; use immutable
commit/blob or digest-addressed artifacts when the report must establish evidence:

- **Worktree:** a path is navigation-only unless paired with captured HEAD evidence.
- **Branch:** a branch URL is navigation-only; use an immutable commit URL or captured HEAD as proof.
- **Pull request or issue:** the ordinary object URL is navigation-only; bind it to the exact object
  and immutable head/revision evidence.
- **Receipt:** verify the approved receipt path, revision/digest and exact task binding.

Use clear labels. This block shows the output shape; placeholder tokens are not destinations and must
never be copied into a live report:

```md
**Worktree (navigation-only):** [WORKTREE_PATH](VERIFIED_LOCAL_PATH)
**Branch (navigation-only):** [BRANCH_NAME](VERIFIED_BRANCH_URL)
**PR (navigation-only):** [PR_NUMBER](VERIFIED_PR_URL)
**Issue (navigation-only):** [ISSUE_NUMBER](VERIFIED_ISSUE_URL)
**Receipt:** [RECEIPT_PATH](VERIFIED_RECEIPT_PATH)
```
