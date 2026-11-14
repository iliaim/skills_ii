# Exact-ID observation and reporting

Use when returning exact task/session observations or identity reports to a governing coordinator. The [main skill](../SKILL.md) owns when to load this
reference.

## Normalize exact-ID observations

Every exact-ID observation returned to a governing coordinator reports these facts separately:

- `content_recency`: recent, old, or unknown, based on file modification time and the latest parseable embedded transcript timestamp;
- `runtime_liveness`: raw provider status or correlated process evidence, or unknown;
- `task_liveness`: live, not live, or unknown;
- `observation_health`: connected, waiting, reconciling, or unknown;
- `progress_changed`: true only when a newer checkpoint/report revision or native turn/event identity is observed, otherwise false or unknown;
- native revision or turn identity, when available;
- `report_identity_or_digest`, when an attached report can affect a dependency gate; and
- `routeability`: available, unavailable, or unknown, based on whether a verified native message route exists now; and
- `backing_kind`, when known.

Keep raw `runtime_liveness` separate from normalized `task_liveness`; neither alone establishes progress. The strict provider output schema requires the
orchestration fields on every model result; use `not_applicable` for operations that do not perform an exact-ID observation or produce progress evidence rather
than inventing liveness or progress. The generic schema may omit those optional fields only when validating non-provider fixtures.

Message delivery, a recent transcript, an active process, or a running summary is not automatically progress, attention acknowledgement, acceptance, artifact
availability, or completion. A transport timeout changes observation health only. Preserve stale, missing, ambiguous, or superseded evidence as unresolved and
return it to the governing parent; never unlock a dependant from a logical report counter alone when no immutable report identity or digest is available.

For an attached child that reports `needs_attention`, return the exact question, required authority, blocked scope, and raising report revision. After a parent
response, acknowledgement exists only when a later child checkpoint is observed with `progress_kind=attention_acknowledged`, the applied decision, and the next
gate. A successful send is not that checkpoint.

## Report the evidence

Separate working routes from unavailable routes. For each contact or continuation, report the timestamp, exact target ID, evidence used, concise message
summary, native result, and remaining owner action. Treat provider and agent reports as evidence to verify, never as a bypass for lifecycle controls.

When reporting an exact task or conversation identity, first classify the evidence. A `verified` identity requires a successful exact native resolution plus the
second durable identifier required above. An unresolved or conflicting candidate must be labelled as such and must not be rendered as a confirmed task or given
a link.

Use a provider-neutral identity block rather than burying the ID in prose. Keep the task name on one line and the exact provider-qualified ID on the next line.
Use code-safe placeholder tokens in documentation; never present placeholder destinations as real links:

```md
**Task (navigation-only):** [TASK_NAME](VERIFIED_PROVIDER_NATIVE_URL)
**Task ID:** `PROVIDER:EXACT_ID`
**Provider:** `PROVIDER_KIND`
**Backing kind:** `BACKING_KIND`
**Host/Project:** `VERIFIED_HOST_OR_PROJECT`
**Identity:** `verified`
**Routeability:** `available`
**Navigation link:** `available|unavailable|unknown`
```

The verified block is shape-only pseudocode. Never copy its placeholder destination into a live report. Use the [link-rendering
rules](link-rendering.md) only when the report needs clickable task or artifact links. Identity, privacy and routeability requirements in this
section apply whether or not a link is rendered.

```md
**Candidate:** TASK_NAME_OR_REDACTED
**Candidate ID:** `PROVIDER:EXACT_ID`  # omit when no exact ID exists
**Provider:** `PROVIDER_KIND`
**Backing kind:** `BACKING_KIND_OR_UNKNOWN`
**Host/Project:** `VERIFIED_HOST_OR_REDACTED_OR_UNKNOWN`
**Identity:** `unresolved|conflicting`
**Routeability:** `unavailable|unknown`
```

The candidate block is also shape-only pseudocode. Do not label an unresolved candidate `Task` or `Task ID`, and do not include a candidate ID unless it was
explicitly supplied or exactly observed.

Use `recipient_scope: same_context|cross_provider|external` when deciding what to disclose. The default for an unknown scope is deny: redact or omit task names,
IDs, host/account/project values, absolute paths, receipt locations, timestamps, evidence descriptions, message summaries, questions, native results, and
remaining owner actions. Across providers or outside the owning context, disclose those fields only with explicit recipient-bound authorization and only to the
minimum extent needed for the request. This privacy gate applies equally to link labels and destinations and must be reflected in
`privacy_bounded`/`redaction_required`.

Only render task and artifact links that pass the reference's binding and privacy checks. A missing navigational deep link affects only `navigation_link:
unavailable`; it does not change message `routeability`. Preserve message `routeability` from verified native contact evidence, or report `unknown` when that
evidence is indeterminate. Never fabricate a `codex://` URL or use a title selector for contact or continuation.
