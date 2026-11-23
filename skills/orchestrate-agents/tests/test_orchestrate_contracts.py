from __future__ import annotations

import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#([^)]+))?\)")


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
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug


def _headings_and_anchors(markdown: str) -> dict[str, str]:
    anchors: dict[str, str] = {}
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            title = match.group(0)
            anchors[title] = _heading_slug(match.group(2))
    return anchors


def test_skill_line_count_and_frontmatter() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    lines = skill_text.splitlines()
    assert 120 <= len(lines) <= 240, f"SKILL.md line count {len(lines)} outside 120..240"

    fm = _parse_frontmatter(skill_text)
    assert fm.get("name") == "orchestrate-agents"
    assert fm.get("license") == "MIT"
    description = fm.get("description", "")
    assert 1 <= len(description) <= 1024
    assert "Use " in description
    assert "Not for " in description


def test_openai_yaml_metadata() -> None:
    yaml_text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    fields = _parse_openai_yaml(yaml_text)
    assert fields.get("display_name") == "Orchestrate Agents"
    short_desc = fields.get("short_description", "")
    assert 25 <= len(short_desc) <= 64, f"short_description len={len(short_desc)}: {short_desc!r}"
    assert "$orchestrate-agents" in yaml_text
    assert "$dispatch-workers" in yaml_text


def test_canonical_headings_anchors_and_precedence_links() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    anchors = _headings_and_anchors(skill_text)
    expected = {
        "## Start here": "start-here",
        "## 1. The tick": "1-the-tick",
        "## 2. Decision rights": "2-decision-rights",
        "## 3. Worker brief": "3-worker-brief",
        "## 3a. Maker and checker": "3a-maker-and-checker",
        "## 4. Delivered is the only done": "4-delivered-is-the-only-done",
        "## 5. Never stuck": "5-never-stuck",
    }
    for heading, slug in expected.items():
        assert heading in anchors, f"Missing heading {heading!r}"
        assert anchors[heading] == slug

    assert "`queued/unmonitorable`" in skill_text
    assert ".agents/orchestration.json" in skill_text
    assert ".agents/orchestration-overlay.md" in skill_text
    for rel in (
        "references/modes/repo-queue.md",
        "references/modes/thread-graph.md",
        "references/orchestration-contract.md",
        "references/advanced-modes.md",
    ):
        assert rel in skill_text, f"Missing link to {rel}"


def test_mode_references_exist_and_cover_required_contracts() -> None:
    repo_queue_path = SKILL_ROOT / "references" / "modes" / "repo-queue.md"
    thread_graph_path = SKILL_ROOT / "references" / "modes" / "thread-graph.md"
    assert repo_queue_path.is_file()
    assert thread_graph_path.is_file()

    repo_queue = repo_queue_path.read_text(encoding="utf-8")
    thread_graph = thread_graph_path.read_text(encoding="utf-8")
    combined = repo_queue + "\n" + thread_graph

    assert "--match-head-commit" in repo_queue
    assert "git range-diff" in repo_queue
    assert "Decide:" in combined
    assert "Waiting: <who> | ends when <condition> | re-check <UTC>" in combined
    assert "`queued/unmonitorable`" in thread_graph


def test_no_broken_internal_links_and_old_dir_removed() -> None:
    assert not (SKILL_ROOT.parent / "orchestrate-threads").exists()

    md_files = [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "references").rglob("*.md"))]
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        for target, anchor in MARKDOWN_LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (md_path.parent / target).resolve()
            assert resolved.exists(), f"Broken link {target!r} in {md_path.relative_to(SKILL_ROOT)}"
            if anchor and resolved.suffix == ".md":
                target_anchors = set(_headings_and_anchors(resolved.read_text(encoding="utf-8")).values())
                assert anchor in target_anchors, (
                    f"Broken anchor #{anchor} for {target} in {md_path.relative_to(SKILL_ROOT)}"
                )
