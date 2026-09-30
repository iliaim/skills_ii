# Skill packaging and instruction guidance

Research checked 2026-09-30. This note separates format requirements from authoring advice and local audit suggestions. Standards evolve; consult the linked source before changing packaging rules.

## Standards and product-specific requirements

- **Agent Skills format:** a skill is a directory with `SKILL.md`; the file has YAML frontmatter followed by Markdown. `name` and `description` are required. The spec sets name syntax/length (1–64 lowercase letters, digits, hyphens; no edge or repeated hyphens; match parent directory) and description length (1–1024 characters). Optional fields include `license`, `compatibility`, `metadata`, and experimental `allowed-tools`. [Agent Skills specification](https://agentskills.io/specification)
- **Resources:** `scripts/`, `references/`, and `assets/` are conventional optional directories, not required scaffolding. A skill may include other files. Relative paths from the skill root are the portable reference form. [Agent Skills specification](https://agentskills.io/specification)
- **OpenAI Skills support:** OpenAI says Skills are compatible with the Agent Skills standard. Its API guide describes the required directory manifest, frontmatter and instructions; references, scripts and assets are optional. API upload has additional bundle limits and validation rules, so those limits apply only when distributing through that API. [OpenAI API Skills guide](https://developers.openai.com/api/docs/guides/tools-skills)
- **OpenAI plugin submission:** plugin imports have additional packaging checks (for example, each skill is a directory under `skills/` with a readable `SKILL.md`; interface settings belong in `agents/openai.yaml`, not frontmatter `metadata`). Treat these as plugin-publishing constraints, not universal Agent Skills constraints. [Submission errors](https://developers.openai.com/plugins/deploy/submission-errors)
- **Portable plugin packaging:** current plugin docs use root `plugin.json` and discover skill folders under root `skills/`; Codex-specific overlay fields/files are separate. This matters only if this repository is packaged as a plugin. [Package your plugin](https://developers.openai.com/plugins/build/plugins)

## Authoring advice (not format mandates)

- Discovery exposes `name` and `description` before the body is loaded; descriptions should clearly state the capability and relevant trigger. OpenAI recommends short, discriminating descriptions because long or overlapping descriptions can be shortened in context and cause poor routing. [OpenAI skills guide](https://developers.openai.com/api/docs/guides/tools-skills), [OpenAI Codex guidance, 2026-09-11](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
- Progressive disclosure: keep shared purpose and essential routing in `SKILL.md`; link conditional detail to focused references/scripts/assets. The Agent Skills spec recommends the main file stay under 500 lines and the body under 5,000 tokens; these are recommendations, not format validation limits. Avoid splitting a short self-contained skill just to meet a target. [Agent Skills specification](https://agentskills.io/specification)
- OpenAI's creator guidance says to retain only non-obvious guidance that changes decisions, avoid generic/repeated advice and speculative edge cases, preserve user intent and authorization boundaries, and scale specificity to risk. It recommends conditional references for mode-specific detail. [OpenAI Codex skill-creator sample](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md)
- Instruction authority is runtime-specific. The OpenAI API guide says skill instructions are user-prompt input and have the same priority as other user-provided instructions. Do not describe a skill as overriding higher-priority system/developer policy or the user's explicit scope. [OpenAI API Skills guide](https://developers.openai.com/api/docs/guides/tools-skills)
- For skills exposed to API agents, OpenAI advises reviewing their instructions as potentially untrusted because they can influence tool use and execution; high-impact workflows should use explicit approval/policy checks. This is product security advice, not a universal frontmatter requirement. [OpenAI API Skills guide](https://developers.openai.com/api/docs/guides/tools-skills)

## Concrete opportunities in this repository

Priority here is an audit recommendation, not a compliance finding.

1. **P1 — sharpen discovery descriptions.** The three current descriptions identify useful capabilities, but `agent-communication` covers several provider/task evidence cases and `delegate-to-thread` is long. Review descriptions against actual trigger boundaries and neighboring skills; shorten only where this improves routing. Do not treat brevity as a character-limit mandate. [Current skills](../../skills/agent-communication/SKILL.md), [delegate](../../skills/delegate-to-thread/SKILL.md), [orchestrate](../../skills/orchestrate-threads/SKILL.md)
2. **P1 — preserve the existing disclosure shape.** `agent-communication` is 253 lines and has provider-specific references; the other entrypoints are 97 and 106 lines and route to contracts/advanced modes. This already follows the spec's advice. During edits, keep conditional provider and advanced-mode detail in the focused files and ensure links name when to read them.
3. **P2 — validate format only against the intended target.** If portable Agent Skills conformance is a goal, use `skills-ref validate` and check directory-name matching. If OpenAI plugin submission is a goal, additionally apply its importer rules. The repo is currently nested under `skills/<name>/`, so its layout matches common skill collections; plugin packaging would require checking the expected plugin root and manifest rather than assuming this repository root is itself a plugin.
4. **P2 — keep instruction contracts evidential.** These skills contain operational boundaries and detailed procedure. Retain strict wording where it protects a demonstrated invariant, authorization boundary, or documented tool contract; consider simplifying duplicated/general instructions after tracing their source. This is an audit heuristic inferred from OpenAI authoring guidance, not an external standard.

## Source index

- [Agent Skills specification](https://agentskills.io/specification) — format and recommendations.
- [OpenAI API Skills guide](https://developers.openai.com/api/docs/guides/tools-skills) — discovery, loading, API-specific behavior, authority and safety.
- [OpenAI plugin build skills](https://developers.openai.com/plugins/build/skills) and [submission errors](https://developers.openai.com/plugins/deploy/submission-errors) — plugin authoring/import behavior.
- [OpenAI skill-creator source](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md) — current creator guidance.
- [OpenAI Codex skills and prompts guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) — dated product advice, not a stable format specification.
