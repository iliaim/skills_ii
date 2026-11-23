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
