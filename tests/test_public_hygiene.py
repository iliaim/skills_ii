from __future__ import annotations
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_brand_or_host_token",
        re.compile(r"\b(?:fightcard|fightcardai|fightcardiq|macssd|fcauto|fcdrain|fcworkers|hermes)\b", re.IGNORECASE),
    ),
    (
        "private_host_path",
        re.compile(r"(?:/Volumes/[A-Za-z0-9._-]+|/Users/(?!example\b)[A-Za-z0-9._-]+(?:[\"'/\s]|$)|/home/(?!example\b)[A-Za-z0-9._-]+(?:[\"'/\s]|$))"),
    ),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "api_secret_key",
        re.compile(r"\bsk-(?:(?:proj|svcacct|admin|ant-[a-z0-9]+)-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})\b"),
    ),
    (
        "cloud_or_pem_credential",
        re.compile(r"(?:\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{35}\b|\bya29\.[0-9A-Za-z_.-]{16,}\b|-----BEGIN [A-Z0-9 ]{0,32}PRIVATE KEY-----)"),
    ),
)


def repo_candidate_files() -> list[Path]:
    raw = (
        subprocess.check_output(["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--recurse-submodules"], text=False)
        + subprocess.check_output(["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--others", "--exclude-standard"], text=False)
    )
    paths: list[Path] = []
    for entry in dict.fromkeys(raw.split(b"\x00")):
        if not entry:
            continue
        rel = entry.decode("utf-8", errors="surrogateescape")
        if rel == "tests/test_public_hygiene.py":
            continue
        paths.append(REPO_ROOT / rel)
    return paths


def test_zero_private_brands_paths_symlinks_or_secrets() -> None:
    violations: list[str] = []
    root_resolved = REPO_ROOT.resolve()
    for path in repo_candidate_files():
        if path.is_symlink():
            target = path.resolve()
            if not target.is_relative_to(root_resolved):
                violations.append(f"{path.relative_to(REPO_ROOT)}: symlink_escapes_repo")
            continue
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule_name, pattern in RULES:
                if pattern.search(line):
                    # Never echo matched line content so accidentally staged secrets never print to CI logs.
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: matched {rule_name}")
    assert not violations, "Public hygiene violations:\n" + "\n".join(violations)


_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_INLINE_CODE_RE = re.compile(r"(`+)([^`]|(?!\1)`)*?\1")
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>\s]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "#", "codex://", "conversation://", "file://")


def _strip_fenced_and_inline_code(markdown_text: str) -> str:
    kept_lines: list[str] = []
    active_fence: str | None = None
    for line in markdown_text.splitlines():
        if active_fence is None:
            m = _FENCE_OPEN_RE.match(line)
            if m:
                active_fence = m.group(1)
                kept_lines.append("")
                continue
            kept_lines.append(line)
        else:
            fence_char = active_fence[0]
            if re.match(rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{len(active_fence)},}}[ \t]*$", line):
                active_fence = None
            kept_lines.append("")
    joined = "\n".join(kept_lines)
    return _INLINE_CODE_RE.sub(lambda match: " " * len(match.group(0)), joined)


def collect_broken_markdown_links(root: Path) -> list[str]:
    root_resolved = root.resolve()
    md_files: list[Path] = []
    readme = root / "README.md"
    if readme.is_file():
        md_files.append(readme)
    for folder in ("docs", "skills"):
        base = root / folder
        if base.is_dir():
            md_files.extend(sorted(base.rglob("*.md")))

    broken: list[str] = []
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        scrubbed = _strip_fenced_and_inline_code(text)
        for match in _MARKDOWN_LINK_RE.finditer(scrubbed):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(_EXTERNAL_SCHEMES):
                continue
            rel_part = raw_target.split("#", 1)[0].split("?", 1)[0]
            if not rel_part:
                continue
            lineno = scrubbed.count("\n", 0, match.start()) + 1
            candidate = md_path.parent / rel_part
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root_resolved):
                broken.append(f"{md_path.relative_to(root)}:{lineno}: link escapes repo ({raw_target})")
            elif not resolved.exists():
                broken.append(f"{md_path.relative_to(root)}:{lineno}: missing link target ({raw_target})")
    return broken


def test_all_relative_markdown_links_resolve_on_disk(tmp_path: Path) -> None:
    # Verify the guard catches broken relative links while ignoring fenced code blocks.
    sample_doc = tmp_path / "docs" / "note.md"
    sample_doc.parent.mkdir(parents=True)
    sample_doc.write_text(
        "```markdown\n[ignored](missing-in-fence.md)\n```\n"
        "Inline `[ignored](missing-inline.md)` and [multiline\nlabel](../missing-real.md#sec).\n",
        encoding="utf-8",
    )
    sample_failures = collect_broken_markdown_links(tmp_path)
    assert len(sample_failures) == 1
    assert "../missing-real.md#sec" in sample_failures[0]

    broken = collect_broken_markdown_links(REPO_ROOT)
    assert not broken, "Broken relative markdown links:\n" + "\n".join(broken)
