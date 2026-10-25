# Standards review and implemented improvements

Reviewed 2026-09-30 against baseline `e4e478b19c470431d53fde73b85a39b4eebcbd9a`.
Scope: all three skills, their provider/ownership contracts, Python evaluators, synthetic fixtures,
package structure, research references, and repository validation/delivery setup. This is a
source-grounded engineering review, not certification against a universal agent standard.

## Research and challenge process

The work used five ordered batches: research; repository challenge; improvement planning and
independent plan challenge; implementation; independent review and verification. Nine native
subagents covered packaging, evaluation practices, orchestration practices, three corresponding
repository challenges, planning, plan challenge, and harness implementation. Six research/challenge
agents used Luna. A native agent-thread limit prevented additional native agents or follow-up turns.
Two further independent reviewer roles ran through isolated ephemeral Codex CLI processes: three
harness reviews and two contract/maintenance reviews. Thus the work used eleven agent roles across
fourteen successful agent runs. The CLI account rejected Luna, so those reviewers used its configured
default model. Failed model attempts are excluded from those counts.

Reviewers received source snapshots as untrusted data, had no enabled tool surfaces, and returned
schema-validated findings bound to the snapshot digest. The integration owner reproduced actionable
findings, inspected all diffs, and ran verification independently. Source reviews did not count as
runtime proof. Review repairs stayed in the bounded implementation scope.

Primary-source research and applicability distinctions:

- [Skill format and authoring](skill-standards.md): Agent Skills specification and official OpenAI
  authoring/distribution guidance. Packaging requirements were distinguished from routing advice.
- [Evaluation standards](evaluation-standards.md): Python process/JSON semantics, JSON Schema,
  OpenAI structured output/evaluation guidance, pytest reliability, and GitHub Actions practices.
- [Orchestration standards](orchestration-standards.md): authorization, provenance, untrusted inputs,
  bounded concurrency, observation, and ambiguous side effects. Durable-workflow patterns were used
  as analogies, never as provider guarantees or new policy requirements.

## Findings and dispositions

| Priority | Confirmed opportunity | Implemented result |
| --- | --- | --- |
| P1 | Harness diagnostics could count as mutation proof; another eval's failure could also qualify. | Require the selected eval's valid `BEHAVIOR_FAIL` and named violation. Any harness error takes exit-code priority `2`, including mixed runs. |
| P1 | Malformed event/configuration shapes escaped error classification; prefix-only bounds could crash grading. | Validate JSON roots, event/item shapes, mutation objects, selector/operand types, and report prefix count failures normally. Malformed configuration yields a path-specific harness error before execution. |
| P1 | Misspelled scenario constraints were silently ignored. | Close the existing check, call-rule, argument-condition, and precedence vocabularies; validate operators before preflight. Expected argument data remains arbitrary. |
| P1 | The temporary provider schema did not require every nested object property. | Recursively require and close the current provider object schemas, including nullable `hostId`. The generic schema remains unchanged. This follows [OpenAI's strict schema requirements](https://developers.openai.com/api/docs/guides/structured-outputs). |
| P1 | Coordination evidence and rubric implied authority from skill invocation despite the existing caller-ownership contract. | Bind the coordinated fixture and negative control to explicit typed user coordination intent; retain create-only and orchestrator handoff semantics. |
| P1 | The admission oracle could consume discovery evidence before its release operation. | Check actual operation occurrence, arguments, release-before-admission, and declared partial order. A cloud read explicitly selects its observation/bound evidence; later terminal evidence is checked separately. Invalid dependency IDs fail closed. |
| P2 | A fresh environment lacked declared test dependencies and a reliable root validation command. | Add pinned existing dev dependencies, a README recipe, cache ignores, and an offline Actions job with read-only permissions, finite timeout, verified full-SHA official actions, and no persisted checkout credentials. |
| P2 | Two research links targeted an absent writing-goals package. | Mark the historical reference as external/unbundled and link the included orchestration contract. |

The original safety boundaries were largely strong: exact task identity, separate authorization and
technical capability, ambiguous-creation no-retry rules, writer ownership, bounded fan-out,
observation/acceptance separation, and synthetic right-reason controls. No normative skill entrypoint
or runtime ownership contract needed rewriting.

Recommendations not adopted:

- Shortening discovery descriptions: no demonstrated routing failure; all three packages validate.
- Additional generic taint wording: existing untrusted-source and authority boundaries already cover
  the identified concern. Duplicating the rules would create another normative source.
- Strict duplicate-key/NaN decoding: advisory compatibility work, not needed for the reproduced bugs.
- Runtime locks/controllers, retry infrastructure, arbitrary concurrency numbers, or new providers:
  not justified for an instruction/contract collection.
- Plugin manifests, publication metadata, or license selection: distribution/product choices outside
  the demonstrated repair scope.
- Portable packaging validation in CI: the installed authoring validator was run separately; the
  new repository gate promises offline Python contract coverage only.

## Verification evidence

Baseline: `python3 -m pytest -q -p no:cacheprovider` passed 90 tests and 45 subtests. A fresh venv
without system packages initially lacked pytest; root unittest discovery collected zero tests.

After installing only `requirements-dev.txt` into `/tmp/skills-ii-fresh-venv`:

```sh
/tmp/skills-ii-fresh-venv/bin/python -m pytest -q skills
/tmp/skills-ii-fresh-venv/bin/python skills/agent-communication/scripts/run_behavioral_evals.py --list
git diff --check
```

Results: 108 tests and 95 subtests passed with no skips; the listing returned all 36 eval IDs;
the diff check passed. New regressions were also run against isolated baseline source before repair:
the initial harness regressions produced 29 failing test/subtest instances, the coordination grant
regression failed both false/missing-grant subcases, and review-discovered malformed-input/admission
paths were reproduced before their fixes. The final mixed-null selector regression failed both
subcases before selector validation and passes afterward.

All three packages passed the installed Skill Creator validator separately:

```sh
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/agent-communication
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/delegate-to-thread
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/orchestrate-threads
```

That environment includes PyYAML; it is not an undeclared requirement of the repository's pytest gate.
Workflow triggers, permissions, timeout, action pins, credential settings, README command agreement,
and changed relative Markdown links were checked locally.

Initial remote CI attempts were blocked before execution by GitHub's account payment/spending-limit
restriction on the private repository. At the owner's request, the repository was made public.
The [pull-request CI rerun](https://github.com/iliaim/skills_ii/actions/runs/36651563569) then completed
successfully: `python -m pytest -q skills` passed 108 tests and 95 subtests on the GitHub-hosted Linux
runner with Python 3.14. The earlier infrastructure failures remain historical run records.

The three `SKILL.md` files and generic result schema remain byte-identical to baseline. The generic
schema SHA-256 is `223244b4370dc6e2e2307102be95877cc2e36e1372be57ccd42c7d063bc258dc`.
Delegate catalog populations remain 26 cases/64 controls, 3 observation variants/6 controls, and
12 prompt variants. Case IDs and partial-order ratchets are unchanged; only the deliberately renamed
coordination-control IDs change their control digest. No controls were removed.

Final independent source reviews returned no actionable findings:

- Harness snapshot: `16bec3cd5d4ccbc605c6aaa619deb7db7ff66d22deeb6c38f28404d78e2fcd4e`.
- Contract/maintenance snapshot: `03de447164bd6667bc9ff086073fe2857b119a8663f62955ad63294d944e51bc`.

Limits: the reviews were source-only. Offline tests, schema invariants, and fake-process tests verify
the contract/harness behavior; they do not prove real provider delivery, task creation, or model
stability. No live behavioral evaluation was run. The initial private-repository GitHub plan did not
expose branch protection; no protection settings were changed. Dependency/action installation remains dependent
on ordinary package and GitHub availability.

## Communication reliability and session investigation (2026-10-25)

### Lightweight completion contract

Outcome: make queued-message acknowledgement and recovery explicit, and provide a separately
invocable read-only session investigation workflow that communication and coordination can reuse.
The user authorized research, independent Luna subagents, and applying improvements in this repository.
This is interactive work with one integrated implementation; no unattended controller is needed.

Read first: the message and relevant provider references in `skills/agent-communication/references`,
the existing delegate/orchestration contracts, the installed Hermes `agent-session-forensics` skill
and helper source, current-main FightCard orchestration/dispatch guidance, README, CI and existing tests.

Writable scope: the communication contract/provider diagnostics and their evals, a small
`agent-session-investigation` package, focused routing links in the other skills, README, and this
existing research record. Protected scope: Hermes installation, FightCard checkout/hosts, private
session stores, runtime/controller configuration, and unrelated repository content.

Given a transport-accepted message with no action-bound receiver response, when the sender follows
the revised instructions, then receipt, disposition, execution and completion remain separate;
the sender uses a bounded observation and reports an unresolved queue without blind replay,
takeover or implicit resume. An accepted request begins authorized work without a second handshake;
held/refused responses name their blocker/conflict. No callback is required without authority.
For current-task subagents, distinguish live `send_message` from `followup_task`, which the current
native tool explicitly documents as triggering a turn for an idle existing agent. Feature-detect
that surface; do not promise that a queued message wakes an idle recipient. This does not authorize
persisted-session resume or new task creation. Verify this with fresh native Luna scenario probes.

Given a session investigation, when the new skill is used, then it limits inspection to the named
question/session, begins with metadata, preserves physical provenance and parse/snapshot limits,
and distinguishes historical claims from fresh verification. It sends no messages and changes no
session/controller state. Its helper supports one explicitly selected local Claude/Codex JSONL
file, not corpus inventory or additional provider integrations. The dependency-free metadata
inspector, adapted narrowly from Hermes, emits no transcript text, IDs, paths or arbitrary source
labels. Defaults are 10,000 physical lines, 1 MB per line, and 16 MB total; oversized-line draining
also consumes the total budget. Incomplete/unstable snapshots and parse gaps remain explicit.
Semantic analysis, when needed, uses a separate purpose-authorized, locally redacted and bounded
projection; the metadata helper does not perform it or claim to answer a semantic question.
Here purpose authorization means an explicit human grant covering the named session/file and question;
each excerpt is labelled untrusted before model input and retains physical line/byte provenance.
Exact task identity and provider status remain owned by communication; report/graph acceptance
remains owned by delegation/orchestration. Do not duplicate these contracts or copy FightCard's inbox.

Checks: `python3 -m pytest -q skills`; both communication evaluator `--list` commands;
the installed Skill Creator `quick_validate.py` for each changed/new package; `git diff --check`.
Fresh Luna behavior probes cover queued-but-unconfirmed, received-without-disposition, held/refused,
accepted/action-bound work, generic-ACK/unrelated-turn negative controls, and standalone investigation
routing. Helper tests cover non-disclosure, caps, malformed input, change/replacement, symlinks and
non-regular files. Existing hermetic model evals are used where compatible;
harness failure stays distinct from behavior failure. Synthetic tests do not prove native delivery.

Alternatives: retain only existing wording (does not address the observed usability gap); introduce
a broker/receipt database/retry daemon (unnecessary and outside scope); move all provider references
into forensics (would duplicate/misplace exact-ID contact and live-status ownership). Instead add
one compact ACK/disposition/observation procedure and one independent retrospective workflow,
sharing provider resolution through links. No new provider, runtime service, dependency or ADR.

Documentation: update the message contract, affected routes and README; retain source research,
challenge and exact observed checks here. Delivery uses a focused PR and repository CI.
Stop successfully after all acceptance/checks and normal delivery pass; return for a genuine new
product choice, unavailable authority, irreversible action or expanded objective.

Pre-implementation checkpoint: research complete; baseline `python3 -m pytest -q skills` passed 163 tests and
246 subtests on Python 3.14.3; next gate is independent challenge of this exact contract.

### Research findings and decisions

Five GPT-6 Luna researchers independently examined the existing communication contract, Hermes,
FightCard, primary messaging standards, and scope/complexity. The final pre-implementation plan
received a fresh cooperative read-only challenge with no unresolved findings; its section digest
was `52726568f3c651a5683c88d7a0325bfadf19d879fdd300478c0c1c2c6a1437b3`.
This was a lightweight interactive challenge, not protected host-enforced unattended assurance.
The user had already authorized applying the improvements; no further plan approval was requested.

- **Existing ACK/NACK:** `accepted`, `held` and `refused` already covered action dispositions.
  Transport delivery, execution and completion were already separate. Receipt terminology and
  queued-message follow-through were spread across references. Add one table and bounded observer
  procedure to the existing message contract; retain the vocabulary and ownership instead of
  adding a second protocol or requiring a callback/second handshake.
- **A concrete idle-agent distinction:** this session's native collaboration descriptions say
  `send_message` does not trigger a turn; `followup_task` triggers one for an idle existing agent.
  Add that feature-detected distinction, plus an authorized continuation cue for an already queued
  action. Neither tool's success proves action acceptance/execution. These tools are not the
  persisted `codex queue` route; do not use the subagent cue to evade its no-replay rule.
- **FightCard:** read the clean detached coordinator's guidance, then current-main source rather
  than dispatching from that checkout. The
  [multi-orchestrator inbox](https://github.com/iliaim/fightcardai/blob/42e5f58fdf205396773a85f19179206e4af2f8cb/.agents/skills/orchestrate-agents/references/multi-orchestrator.md)
  uses ACKs with `STARTED`, `QUEUED(when)`, `DECLINED(reason)` and `DONE`, and a separate accepted
  handoff. Its durable inbox/cursor/controller make those receipts meaningful. The
  [worker-host recovery reference](https://github.com/iliaim/fightcardai/blob/42e5f58fdf205396773a85f19179206e4af2f8cb/.agents/skills/orchestrate-agents/references/worker-hosts.md)
  retains whole startup handles and reconciles exact conversation/worktree/registry bindings
  before another launch. Learn from the explicit dispositions and correlation; do not copy its
  inbox, supervisor, resend policy or host controls into generic Codex communication.
- **Hermes:** inspect the installed `agent-session-forensics` skill and helper source, not private
  sessions. Its metadata-first structure, physical provenance, snapshot checks and untrusted-content
  boundary support a useful standalone historical workflow. Adapt only a single-file metadata
  inspector. Exclude corpus inventory, sampled keyword incidents, four-provider expansion,
  FightCard-specific redactors/casebooks and a new session store. Hermes synthetic helper checks
  were reported green by its researcher; parent acceptance relies on this repo's separately run
  tests and inspected diff, not that report. Hermes itself was not changed.
- **Provider diagnostics:** local Codex filename suffix/`session_id` is only a lead; require
  canonical `session_meta.payload.id` and reconcile exact database `threads.id`/`rollout_path`.
  Remove the example that dumped all subsequent assistant content and preserve gaps/conflicts.
  Keep provider resolution in communication, artifact methodology in investigation, and graph/report
  gates in their existing skills; conditional cross-links compose operations without rediscovery.

Primary practice checked on 2026-10-25:

- [RabbitMQ confirms and acknowledgements](https://www.rabbitmq.com/docs/confirms) distinguishes
  publisher/broker confirmation from consumer processing acknowledgement. This supports keeping
  transport acceptance separate from application evidence; it does not give Codex broker guarantees.
- [Temporal message passing](https://docs.temporal.io/encyclopedia/workflow-message-passing)
  distinguishes asynchronous Signals, read-only Queries and tracked Updates. This informs explicit
  observation ownership; it does not imply that Codex has tracked request/reply or durable wake-up.
- [A2A specification](https://a2a-protocol.org/latest/specification/) separates submitted, working,
  input/auth-required, rejected and terminal task states, and makes message idempotency optional.
  Reuse the distinction, not the protocol or assumed exactly-once behavior.

No generic messaging standard can establish the delivery, persistence or wake-up guarantees of a
specific native tool. A running receiver plus an active observer and an authoritative result are
still necessary. These changes make gaps visible and recovery bounded; they do not guarantee
delivery or turn the skill into a runtime service.

### Review and validation observations

Fresh Luna forward probes covered idle-agent follow-up, investigation with a stable-but-capped
transcript and malicious quoted instructions, and held/refused/executing/stale-revision outcomes.
Parent inspection confirmed: held retained the signed-manifest blocker and release-coordinator role;
refused preserved routeability without a bypass; artifact execution remained incomplete without
verification; revision 1 could not complete revision 2. The investigation probe kept the transcript's
resume/secret-disclosure requests as untrusted evidence and did not infer completion from “done”.
These are bounded model behavior probes, not proof of native queue delivery. Actual native
`followup_task` calls in this work also returned later responses from the same existing agents;
that demonstrates this session's route, not a general reliability rate.

Two independent Luna reviews found and prompted repairs: reject `..` before path normalization so
`symlink/../file` cannot select another source, remove the unbounded metadata example, qualify a
generic ACK by native action correlation, and add a superseded-revision negative fixture. Grader
checks cover only structured decisions/calls/facts; human-readable catalog assertions about blocker
wording and unsupported completion claims were checked in the fresh natural-language probes, not
claimed as machine-enforced prose checks.

The parent reproduced a SQLite CLI example failure using synthetic state: `query_only=ON` prevented
temporary parameter initialization, and an all-numeric UUID needed SQL-string-preserving CLI quoting.
The exact revised documented shell block returned the one requested synthetic row with exit 0,
empty stderr and byte-identical provider database. No real provider database was opened.

Initial fresh CLI evaluations exposed real classification/replay failures and two underspecified new
fixtures. The fixtures now supply the exact receiver/route observation required by their routeability
assertions; no existing acceptance/no-contact checks were relaxed. Some runs were invalidated by
pytest updating derived bytecode during the evaluator's full-directory integrity check. Those remain
`HARNESS_ERROR`, not behavior passes; final evaluations run with the skill tree held unchanged.

Installation observation: Codex's three existing skills are symlinked to this checkout. Claude's
separate `agent-communication` installation is an older standalone file with different procedures;
it has not been overwritten or moved. The new investigation package was added as a non-overwriting
symlink alongside Codex's existing three; its resolved entrypoint bytes match this repo. Automatic
catalog activation in a future chat was not exercised. Aligning the independent Claude copy is a separate installation
follow-up, not evidence that modifying this repository updated every agent's runtime.


Final local verification (Python 3.14.3):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q skills
python3 skills/agent-communication/scripts/run_behavioral_evals.py --list
python3 skills/agent-communication/scripts/run_paired_evals.py --list
git diff --check
```

Results: 192 tests and 246 subtests passed; the planned-action catalog listed 46 cases and paired
catalog listed 24; no malformed catalogs or diff whitespace errors. All four packages passed the
installed Skill Creator `quick_validate.py`. Relative Markdown links outside fenced pseudocode were
checked (16 files, no missing targets). The inspector is covered by 22 synthetic tests including
path selection, no value disclosure, physical/byte caps, unsafe file types and unstable snapshots.

Fresh `gpt-6-luna` checks, with the communication skill tree held unchanged during each run:

```sh
python3 skills/agent-communication/scripts/run_behavioral_evals.py --eval 42 --runs 2 --model gpt-6-luna
python3 skills/agent-communication/scripts/run_behavioral_evals.py --eval 45 --eval 46 --eval 47 --eval 48 --eval 49 --eval 50 --runs 1 --model gpt-6-luna
python3 skills/agent-communication/scripts/run_behavioral_evals.py --eval 50 --runs 2 --model gpt-6-luna
python3 skills/agent-communication/scripts/run_paired_evals.py --case nominal --case echo --case unfinished-accepted --model gpt-6-luna
python3 skills/agent-communication/scripts/run_paired_evals.py --case nominal --model gpt-6-luna
python3 skills/agent-communication/scripts/run_behavioral_evals.py --eval 42 --runs 1 --model gpt-6-luna --mutation skills/agent-communication/evals/mutations/042-no-label-means-lost.json --expect-failure
```

The queue case passed twice. Cases 45–49 passed; case 50 initially chose the safe but different
`incomplete` label instead of execution-commitment `pending`. Clarifying the fixture's existing
schema notation (without relaxing its checks) yielded two passes. Paired echo and unfinished-accepted
passed. Initial nominal failed because the receiver miscopied a digest and the sender reconstructed
matching evidence instead of preserving the receiver result. Add the explicit evidence-preservation
rule; its fresh nominal repair check passed. The corrupt queue mutation produced the expected valid
`BEHAVIOR_FAIL` for an extra contact, with no harness error, so `--expect-failure` exited 0.

Retained [synthetic model evidence](communication-reliability-evidence.json) includes earlier failures
and successful bounded repair checks with candidate hashes; the host-specific CLI path is omitted.
Do not read this as a statistical reliability result, a claim that every run passed, or proof of
native delivery. Instruction-following remains probabilistic: independently check exact bindings,
artifacts and required reports instead of trusting an ACK or a model's completion claim.

Final checkpoint: research and implementation verified locally; independent source reviews report
no remaining actionable findings; normal PR/CI delivery is next. The PR is the authoritative delivery
record; no host controllers, private session stores, Hermes or FightCard source were modified.

## Installation reconciliation and bounded I/O follow-up (2026-10-25)

The user authorized completing the remaining setup and iterating on confirmed improvements.
Scope: reconcile the older Claude installation, document shared-checkout installation, and repair
reproduced metadata-inspector I/O/cleanup defects. No provider session, host controller, dependency
or communication transport change is needed. Acceptance is unchanged helper output semantics,
an actual underlying read count within the configured cap, closed file/directory descriptors on
failures, and all four installed packages resolving to this checkout with complete sibling references.

A separate Luna comparison found no unique useful rule in the older Claude skill that the current
packages lack. Do not restore its old mtime/FD/process-absence test as proof of safe continuation,
or its treatment of resume as contact. Preserve the original whole directory as a backup outside
active skill discovery, then link all four full sibling packages to the repository. This avoids
maintaining another instruction copy or building an installer/update service.

The existing Claude file was preserved at
`~/.claude/skill-backups/20261025T171940.961147Z/agent-communication/SKILL.md` with SHA-256
`2fb4d9747fb0baf3b3d6d7c0469188b72e2197ed876e60c7748585f7f06c45e1` before and after the move.
Claude's configured root matched the reconciled default root. Direct verification checked all four
package trees against the repository at both Claude's and Codex's installed paths, plus 58 relative
targets per installation with no missing targets. Installed runtime discovery in a fresh Claude
conversation remains separate from these verified filesystem facts; no session was started to test it.

A fresh Luna audit and parent reproductions found two concrete defects in the new inspector:

- Default Python buffering could read a whole 100,004-byte synthetic file when the logical scan cap
  was one byte. Keep buffered line parsing, but cap the raw `readinto` operation beneath the buffer.
  Making the entire reader unbuffered was rejected because raw `readline` can incur per-byte I/O.
- Scan/read/stat failures closed the file but skipped the opened parent directory descriptor.
  Enclose scanning and snapshot checking in one outer cleanup boundary so both descriptors close.

Six new regression instances failed against the previous implementation: three underlying byte-cap
checks and three read/stat/snapshot error-cleanup checks. All 28 inspector tests then passed after
the focused repair. The public `inspect` arguments and metadata fields are unchanged; the new
parameter belongs only to the private file-opening helper. No communication contract or model
grader change was needed, so settled message-policy evidence was retained rather than rerun.

Final follow-up checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q skills/agent-session-investigation/tests/test_inspect_jsonl.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q skills
python3 /Volumes/MacSSD/Developer/Codex/State/skills/.system/skill-creator/scripts/quick_validate.py skills/agent-session-investigation
git diff --check
```

Results: 28 inspector tests passed; the full suite passed 198 tests and 246 subtests; package and
whitespace validation passed. The helper was also invoked via both installed provider paths on one
synthetic JSONL fixture: both CLI calls exited 0, returned identical metadata and omitted fixture
content. A fresh Luna source reviewer found no remaining actionable defect in raw-read bounds,
descriptor cleanup, regressions or installation documentation. No private transcript was inspected.
The PR holds CI, merge and delivery status; the preserved backup remains available for recovery.
