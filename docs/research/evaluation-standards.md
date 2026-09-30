# Evaluation harness research (Batch 1)

Scope: review of `skills/agent-communication/scripts/run_behavioral_evals.py`, its contract
tests, scenario/result schemas, and `references/eval-methodology.md`. This note is advisory; it
does not prescribe application infrastructure. Sources below are primary documentation/specifications.

## Current implementation against sources

- **Process boundary:** the runner invokes a tokenized command with `subprocess.run`, a timeout,
  captured output, and a temporary working copy. Python documents that `run()` waits for completion,
  raises `TimeoutExpired` on timeout, and does not implicitly invoke a shell for argument sequences
  ([Python `subprocess`](https://docs.python.org/3/library/subprocess.html#subprocess.run)).
  `TemporaryDirectory` is context-managed and automatically cleans up its tree
  ([Python `tempfile`](https://docs.python.org/3/library/tempfile.html#tempfile.TemporaryDirectory)).
- **Structured output:** both schemas close objects with `additionalProperties: false`, enumerate
  required fields and constrain values. The runner validates the returned value locally with
  `jsonschema`, in addition to provider-side structured output. JSON Schema defines `required` and
  `additionalProperties` as validation constraints ([JSON Schema object reference](https://json-schema.org/understanding-json-schema/reference/object)); OpenAI's Structured Outputs examples use
  strict JSON Schema and call out refusal/incomplete-output edge cases
  ([OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)).
- **Behavioral validity:** each catalog request has a synthetic scenario and deterministic checks
  over decision, facts, ordered calls, arguments, call counts, and forbidden actions. Staged
  responses must be reached by planned calls. This tests action selection and evidence handling while
  explicitly not claiming real delivery or integration. OpenAI Evals models criteria, data-source
  schema, and graders separately ([OpenAI Evals API](https://platform.openai.com/docs/api-reference/evals));
  that supports the separation, but the harness's specific scenario DSL is a local design choice.
- **Regression controls:** repeated runs are bounded per case; declarative mutations require an
  expected named violation; current unit tests cover coverage, grading contracts, and mutations.
  Pytest's guidance says uncontrolled shared state causes flaky tests and that retries can mask their
  signal ([pytest flaky tests](https://docs.pytest.org/en/stable/explanation/flaky.html)). Repeats
  therefore measure model variability; they do not make a model call deterministic. Keep pure
  contract checks separate from any live/provider eval when wiring CI (recommendation/inference).
- **CI:** no `.github/` workflow or root test configuration was found in this checkout. GitHub's
  Python Actions guide documents a standard workflow for installing Python/dependencies and running
  tests ([GitHub Actions: Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)).
  A low-scope first gate is the existing offline unittest suite plus schema/catalog coverage; whether
  live model evals belong in CI depends on credentials, cost, and execution policy (team decision).

## Concrete opportunities, ordered by priority

1. **P1 — align documented exit codes with actual result classification.** The methodology says
   `2` means an untrustworthy harness result, but `main()` returns `1` when per-run `HARNESS_ERROR`s
   were accumulated (`return 0 if behavior_failures == 0 and harness_errors == 0 else 1`). Reserve
   `1` for valid behavioral failures and return `2` for harness errors, or document the intended
   contract. This improves CI triage without adding infrastructure.
2. **P1 — reject non-object event JSON cleanly.** `validate_event_stream()` calls `.get()` on each
   decoded JSON value without checking it is an object. A valid JSON scalar/list in the event stream
   raises `AttributeError`, bypassing the explicit `HarnessError`/subprocess error classification.
   Validate event shape and convert malformed shapes to `HarnessError`; add one offline regression
   contract. This is a reliability finding from code inspection, not a specification mandate.
3. **P1 — require mutation proof to be a behavioral failure.** `--expect-failure` currently searches
   failure text across all run statuses. A matching phrase from a `HARNESS_ERROR` can therefore be
   mistaken for the expected policy regression. Count the named violation only in a schema-valid
   `BEHAVIOR_FAIL` grade. This is a code-derived false-positive risk, not an external-standard rule.
4. **P2 — make JSON decoding ambiguity explicit if inputs are treated as untrusted.** Python's
   standard decoder accepts duplicate keys (last value wins) and non-standard NaN/Infinity by
   default ([Python `json`](https://docs.python.org/3/library/json.html)). Consider strict decoding
   for catalog/scenario/result/event inputs if ambiguity could change grades. Applicability is an
   inference: provider output is constrained, but local JSON files and event streams are parsed too.
5. **P2 — keep actionable behavior checks declarative and evidence-bound.** Existing tests already
   show the useful pattern: positive and negative traces, exact identity/argument matching, ordering,
   separate total contact limits, and required facts. Preserve synthetic fixtures and test the grader
   with both an accepted trace and a minimally mutated rejected trace; do not grade explanation prose
   as a substitute for observable decisions/calls. This is consistent with the local methodology and
   OpenAI's separation of data and graders, not a universal mandated eval format.

## Limits of claims

The runner validates the planned trace and safety properties before any proposed action is executed;
it cannot establish that a real provider performed an action or delivered a message. A model repeat
can reveal unstable outcomes but not prove reproducibility. CI integration, live-eval policy, and
which safety invariants block merges remain repository-owner decisions.
