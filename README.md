# Agent workflow skills

This collection contains three complementary skills:

- [agent-communication](skills/agent-communication/SKILL.md): inspect, contact, or continue existing tasks, process incoming messages with explicit execution ownership, and inspect session evidence.
- [delegate-to-thread](skills/delegate-to-thread/SKILL.md): create one explicitly requested task with defined ownership.
- [orchestrate-threads](skills/orchestrate-threads/SKILL.md): coordinate a bounded graph and verify its cumulative outcome.

The skills require the provider capabilities described in their references. Live tool descriptions control supported operations; the Python tests simulate contracts and do not establish real provider delivery.

## Offline validation

Run from the repository root with Python 3.14 (the version used by CI):

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q skills
python skills/agent-communication/scripts/run_behavioral_evals.py --list
```

Dependency installation needs package-source access. The tests and catalog listing run without credentials or live model/provider calls. Root-level `unittest discover` does not collect this suite; use the pytest command above. GitHub Actions runs that same suite with read-only repository permissions.

Skill package validation is a separate check: use the validator supplied by your skill-authoring environment or the [Agent Skills reference validator](https://agentskills.io/specification#validation). The offline CI gate validates the Python contracts, not every packaging or live-provider behavior.

## Behavioral evaluations

Model-backed evaluations are separate from the offline suite and require a compatible, authenticated Codex CLI. See the [evaluation methodology](skills/agent-communication/references/eval-methodology.md) for commands, feature preflight, safety boundaries, exit codes, and mutation controls. They are not run automatically by CI.

Ordinary sender/receiver behavior follows the [message contract](skills/agent-communication/references/message-contract.md).
The separate [paired evaluations](skills/agent-communication/references/eval-methodology.md#paired-senderreceiver-evaluations)
exercise fresh model exchanges and independently observed scratch effects; the older planned-call
evaluations remain policy simulations. Neither harness establishes native provider delivery reliability. See the
[ownership evaluation](docs/research/thread-ownership-evaluation.md) for retained synthetic results
and reproducible checks.

See the [standards review](docs/research/standards-review.md) for source research, findings, improvement decisions, and verification limits.
