from __future__ import annotations

import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]*)(?:#([^)]+))?\)")


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    assert match is not None, "SKILL.md must start with YAML frontmatter"
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        assert sep, f"Invalid frontmatter line: {line!r}"
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _parse_openai_yaml(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.endswith(":"):
            continue
        key, sep, value = stripped.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def _heading_slug(heading: str) -> str:
    slug = heading.strip().lower()
    slug = re.sub(r"[^a-z0-9_\s-]", "", slug)
    return slug.replace(" ", "-")


def _headings_and_anchors(markdown: str) -> dict[str, str]:
    anchors: dict[str, str] = {}
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            anchors[match.group(0)] = _heading_slug(match.group(2))
    return anchors


def test_skill_line_count_and_frontmatter() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    lines = skill_text.splitlines()
    assert 120 <= len(lines) <= 240, f"SKILL.md line count {len(lines)} outside 120..240"

    fm = _parse_frontmatter(skill_text)
    assert fm.get("name") == "dispatch-workers"
    assert fm.get("license") == "MIT"
    description = fm.get("description", "")
    assert 1 <= len(description) <= 1024
    assert "Use " in description
    assert "Not for " in description


def test_openai_yaml_metadata() -> None:
    yaml_text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    fields = _parse_openai_yaml(yaml_text)
    assert fields.get("display_name") == "Dispatch Workers"
    short_desc = fields.get("short_description", "")
    assert 25 <= len(short_desc) <= 64, f"short_description len={len(short_desc)}: {short_desc!r}"
    assert "$dispatch-workers" in yaml_text


def test_canonical_headings_anchors_and_lazy_references() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    anchors = _headings_and_anchors(skill_text)
    expected = {
        "## 1. Pick unclaimed work": "1-pick-unclaimed-work",
        "## 2. Choose host, provider and model": "2-choose-host-provider-and-model",
        "## 3. Write the brief": "3-write-the-brief",
        "## 4. Launch a worker": "4-launch-a-worker",
        "## 5. Launch a cold reviewer": "5-launch-a-cold-reviewer",
        "## 6. Track, message and resume": "6-track-message-and-resume",
        "## 7. Scale": "7-scale",
    }
    for heading, slug in expected.items():
        assert heading in anchors, f"Missing heading {heading!r}"
        assert anchors[heading] == slug

    for token in (
        ".agents/orchestration.json",
        "~/.config/skills-ii/fleet.json",
        ".agents/orchestration-overlay.md",
        "references/providers/codex.md",
        "references/providers/claude.md",
        "references/providers/agy.md",
        "references/providers/grok.md",
        "references/task-contract.md",
        "references/advanced-delegation.md",
    ):
        assert token in skill_text, f"Missing {token!r} in SKILL.md"


def test_tier2_unsets_all_six_metered_api_keys_and_forbids_orphan_worktrees() -> None:
    providers_dir = SKILL_ROOT / "references" / "providers"
    agy_text = (providers_dir / "agy.md").read_text(encoding="utf-8")
    claude_text = (providers_dir / "claude.md").read_text(encoding="utf-8")
    codex_text = (providers_dir / "codex.md").read_text(encoding="utf-8")
    grok_text = (providers_dir / "grok.md").read_text(encoding="utf-8")

    # 1. Antigravity: all 4 Google/Vertex metered keys, hooks.json fail-closed guard, --mode plan, stream-json, resume
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "AGY_ADC_AUTH"):
        assert key in agy_text, f"agy.md missing metered key unset {key}"
    assert ".agents/hooks.json" in agy_text
    assert "--mode plan" in agy_text
    assert "--output-format stream-json" in agy_text
    assert "--conversation" in agy_text

    # 2. Claude: ANTHROPIC_API_KEY, forbids isolation: "worktree" on Reviewer subagents, strict MCP, plan vs worker
    assert "ANTHROPIC_API_KEY" in claude_text
    assert 'isolation: "worktree"' in claude_text
    assert '--strict-mcp-config --mcp-config \'{"mcpServers":{}}\'' in claude_text
    assert "--permission-mode plan" in claude_text

    # 3. Codex: OPENAI_API_KEY, Tier-1 create_thread/fork_thread + clientThreadId gate, Tier-2 CLI + < /dev/null + -s read-only
    assert "OPENAI_API_KEY" in codex_text
    assert "create_thread" in codex_text
    assert "fork_thread" in codex_text
    assert "clientThreadId" in codex_text
    assert "codex exec" in codex_text
    assert "codex -C" in codex_text and "resume" in codex_text
    assert "< /dev/null" in codex_text
    assert "-s read-only" in codex_text

    # 4. Grok: label-queued external/remote bot handoff, zero secrets, outcome-label verification
    assert "grok-bot" in grok_text
    assert "secret" in grok_text.lower()
    assert "label" in grok_text.lower()


def test_no_broken_markdown_links_and_old_dir_removed() -> None:
    assert not (SKILL_ROOT.parent / "delegate-to-thread").exists()

    checked_files = [
        SKILL_ROOT / "SKILL.md",
        *sorted((SKILL_ROOT / "references").rglob("*.md")),
        *sorted((SKILL_ROOT / "evals").glob("*")),
    ]
    for path in checked_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert "delegate-to-thread" not in text.lower(), (
            f"Stale delegate-to-thread reference in {path.relative_to(SKILL_ROOT)}"
        )
        assert "orchestrate-threads" not in text.lower(), (
            f"Stale orchestrate-threads reference in {path.relative_to(SKILL_ROOT)}"
        )

    md_files = sorted(SKILL_ROOT.rglob("*.md"))
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        for target, anchor in MARKDOWN_LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not target and not anchor:
                continue
            resolved = md_path if not target else (md_path.parent / target).resolve()
            assert resolved.exists(), f"Broken link {target!r} in {md_path.relative_to(SKILL_ROOT)}"
            if anchor and resolved.suffix == ".md":
                target_anchors = set(_headings_and_anchors(resolved.read_text(encoding="utf-8")).values())
                assert anchor in target_anchors, (
                    f"Broken anchor #{anchor} for {target or md_path.name} in {md_path.relative_to(SKILL_ROOT)}"
                )
