# Agent workflow skills

## Choose a skill

Choose the skill for the work and ownership needed now; the skills are not a required sequence.

| Situation | Skill | Responsibility |
| --- | --- | --- |
| Coordinate multiple streams, `/setup` & `/briefing` | [chief-of-staff](skills/chief-of-staff/SKILL.md) | Act as the headed executive coordinator across repositories and orchestrators; triage attention without implementing code inline. |
| Coordinate a repository queue or task graph | [orchestrate-agents](skills/orchestrate-agents/SKILL.md) | Own dispatch ordering, concurrency bounds, maker-checker convergence, and integration across `repo-queue` and `thread-graph` modes. |
| Launch one worker, cold reviewer, or fork | [dispatch-workers](skills/dispatch-workers/SKILL.md) | Launch, review, or resume one scoped worker or cold read-only reviewer across Tier-1 native tools and Tier-2 CLI/SSH hosts (or route explicit history forks). |
| Inspect, contact or continue an existing task | [agent-communication](skills/agent-communication/SKILL.md) | Resolve the exact identity; observe, contact or continue through supported provider routes (and start a new Claude session only on explicit request). |
| Investigate a named session and question | [agent-session-investigation](skills/agent-session-investigation/SKILL.md) | Inspect session artifacts read-only and metadata-first; do not contact a live session or mutate state. |

Use each linked entrypoint for its detailed rules. `chief-of-staff` delegates multi-task scopes to `orchestrate-agents` and bounded single slices to `dispatch-workers`, while `orchestrate-agents` composes `dispatch-workers` for authorized new children with `agent-communication` for existing tasks and `agent-session-investigation` for stalled-session forensics. For an internal subtask whose result belongs in the current response, use an available subagent instead of creating a user-visible task.

The skills require the provider capabilities described in their references. Live tool descriptions control supported operations; the Python tests simulate contracts and do not establish real provider delivery.

For message reliability, distinguish transport delivery, receiver receipt, `accepted|held|refused`
disposition, observed execution and verified completion. See the
[ACK/disposition table](skills/agent-communication/references/message-contract.md#receipt-and-acknack),
[bounded observation](skills/agent-communication/references/message-contract.md#bound-the-observation-before-sending),
and [transport selection matrix](skills/agent-communication/references/message-contract.md#transport-selection-matrix).
On live-task surfaces that expose them, `send_message` does not start an idle subagent;
`followup_task` can trigger its next turn. Persisted tasks use their own provider route and authority.

## Two-tier `/setup` and `/briefing`

`chief-of-staff` separates repository policy from private per-user fleet placement:

1. **Bootstrap configuration (`/setup`)**:

   ```sh
   python3 skills/chief-of-staff/scripts/setup_init.py \
     --repo-root /path/to/repo \
     --fleet-config ~/.config/skills-ii/fleet.json
   ```

   - **Committed repo contract** (`.agents/orchestration.json` + optional `.agents/orchestration-overlay.md`): stores `mode` (`"auto"`, `"repo-queue"`, or `"thread-graph"`), `runtime.commandPrefix`, `tracker` / `review` / `merge` `argv` command arrays (`shell=False` only), and repository escalation rules. Read only from a trusted base checkout.
   - **Private user fleet** (`~/.config/skills-ii/fleet.json`, mode `0600`): stores personal local/SSH host topology, detected CLI binaries (`codex`, `claude`, `agy`), per-provider `workerCap`, and optional `observabilityRemoteSinkCommand`. Never commit `fleet.json`.

2. **Executive digest (`/briefing [--live]`)**:
   - `/briefing` renders a secret-scrubbed, XSS-safe `0600` self-contained static HTML snapshot (`briefing_board.py --snapshot ...`) with zero network listeners.
   - `/briefing --live` starts an opt-in `127.0.0.1` `GET`-only SSE cockpit protected by a random capability token written to a `0600` bootstrap URL file (`--live-bootstrap-file`), never passing tokens on the CLI argv.

## Installation and migration

Install all five sibling skill directories together to preserve their relative references. These are
instructions and local helper scripts; installation does not start a background daemon, queue consumer,
or unattended watcher on its own. Changes here do not automatically update external repositories that vendor copies of these skills.

For a shared local checkout, symlink each complete skill package into the provider's skill directory:
`$CODEX_HOME/skills` (default `~/.codex/skills`) or `$CLAUDE_CONFIG_DIR/skills` (default `~/.claude/skills`).
Afterward, verify each entrypoint and sibling reference resolves to the intended checkout, and verify discovery in a fresh conversation.

### Migrating from earlier layouts

- `orchestrate-threads` is now **`orchestrate-agents`** (unifying `repo-queue` and `thread-graph` modes).
- `delegate-to-thread` is now **`dispatch-workers`** (unifying Tier-1 native delegation and Tier-2 CLI/SSH worker and cold-reviewer dispatch).
- Before symlinking `chief-of-staff` (or replacing `orchestrate-threads` / `delegate-to-thread`), **move any pre-existing standalone `~/.claude/skills/chief-of-staff` directory** and retired skill symlinks/backups **outside** `~/.claude/skills/` and `~/.codex/skills/`. A backup directory left inside `skills/` is still scanned during skill discovery and can expose conflicting instructions.

## Offline validation

Run from the repository root with Python 3.14 (the version used by CI):

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q tests skills
python skills/agent-communication/scripts/run_behavioral_evals.py --list
for skill in skills/*/; do
  skillevaluator validate "$skill" --tiers 1 --skip security -r cli
done
```

Dependency installation needs package-source access. Both `pytest` and the `skillevaluator` Tier 1 static gate run without LLM credentials or API spend (`--skip security` omits only the optional `SkillSpector` wheel whose `yara-python` C extension lacks Python 3.14 wheels, while schema, PII, license, Bandit code-risk, Gitleaks secret detection, dead-link integrity, unicode smuggling, quality scoring, script lint, and harness checks all execute). Root-level `unittest discover` does not collect this suite; use the `pytest` command above. GitHub Actions runs both suites with read-only repository permissions.

## Behavioral evaluations

Model-backed evaluations are separate from the offline suite and require a compatible, authenticated Codex CLI. See the [evaluation methodology](skills/agent-communication/references/eval-methodology.md) for commands, feature preflight, safety boundaries, exit codes, and mutation controls. They are not run automatically by CI.

Ordinary sender/receiver behavior follows the [message contract](skills/agent-communication/references/message-contract.md).
The separate [paired evaluations](skills/agent-communication/references/eval-methodology.md#paired-senderreceiver-evaluations)
exercise fresh model exchanges and independently observed scratch effects; the older planned-call
evaluations remain policy simulations. Neither harness establishes native provider delivery reliability. See the
[ownership evaluation](docs/research/thread-ownership-evaluation.md) for retained synthetic results
and reproducible checks.

See the [standards review](docs/research/standards-review.md) for source research, findings, improvement decisions, and verification limits.

## License

This repository's skills, scripts and documentation are licensed under the [MIT License](LICENSE).
Copyright (c) 2026 Ilia Imerlishvili.
Each skill package includes a copy of the license for standalone installation.

## Contributions

By submitting a contribution, you agree to license it under the same [MIT License](LICENSE).
You retain copyright in your original contributions; no copyright assignment is required.
