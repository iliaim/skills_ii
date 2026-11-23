from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[1]
GUARD_PATH = SKILL_DIR / "scripts" / "chief_guard.py"

_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)")


def _load_guard():
    spec = importlib.util.spec_from_file_location("chief_of_staff_chief_guard_test", GUARD_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_non_chief_session_allows_everything() -> None:
    guard = _load_guard()
    claude_edit = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/repo/src/app.py"},
        }
    )
    claude_bash = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'wip'"},
        }
    )
    agy_edit = json.dumps(
        {
            "conversationId": "conv-1",
            "cwd": "/repo",
            "toolCall": {
                "name": "write_to_file",
                "args": {"TargetFile": "/repo/src/app.py"},
            },
        }
    )

    for env in ({}, {"SKILLS_II_ROLE": "worker"}, {"SKILLS_II_ROLE": "orchestrator"}):
        assert guard.evaluate(claude_edit, env=env) == (0, "")
        assert guard.evaluate(claude_bash, env=env) == (0, "")
        code, out = guard.evaluate(agy_edit, env=env)
        assert code == 0
        assert json.loads(out) == {"decision": "allow"}
        assert guard.evaluate("{not valid json", env=env) == (0, "")


def test_chief_blocks_project_source_edits_across_claude_codex_and_agy() -> None:
    guard = _load_guard()
    env = {"SKILLS_II_ROLE": "chief"}

    for tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        payload = json.dumps(
            {
                "cwd": "/repo",
                "tool_name": tool_name,
                "tool_input": {"file_path": "/repo/src/app.py"},
            }
        )
        code, reason = guard.evaluate(payload, env=env)
        assert code == 2, f"Expected exit code 2 for {tool_name}, got {(code, reason)}"
        assert "dispatch-workers" in reason
        assert "orchestrate-agents" in reason

    patch_code, patch_reason = guard.evaluate(
        json.dumps(
            {
                "cwd": "/repo",
                "tool_name": "apply_patch",
                "tool_input": {"patch": "*** Begin Patch\n*** Update File: src/app.py\n"},
            }
        ),
        env=env,
    )
    assert patch_code == 2
    assert "dispatch-workers" in patch_reason

    agy_payloads = (
        {
            "conversationId": "123",
            "cwd": "/repo",
            "toolCall": {
                "name": "write_to_file",
                "args": {"TargetFile": "/repo/src/app.py"},
            },
        },
        {
            "conversationId": "123",
            "cwd": "/repo",
            "toolCall": {
                "name": "write_file",
                "args": {"Path": "/repo/src/app.py"},
            },
        },
        {
            "conversationId": "123",
            "cwd": "/repo",
            "toolCall": {
                "name": "edit_file",
                "args": {"Path": "/repo/src/app.py"},
            },
        },
    )
    for raw_payload in agy_payloads:
        code, out = guard.evaluate(json.dumps(raw_payload), env=env)
        assert code == 0
        parsed = json.loads(out)
        assert parsed["decision"] == "deny"
        assert "dispatch-workers" in parsed["reason"]
        assert "orchestrate-agents" in parsed["reason"]

    denied_commands = (
        "git commit -m 'test'",
        "git push origin main",
        "git merge feat/x",
        "git rebase main",
        "git reset --hard HEAD~1",
        "git checkout -b feat/new",
        "npm run build",
        "echo 'hack' > /repo/src/app.py",
        "cat src/a.py >> src/b.py",
        "sed -i '' 's/a/b/' src/app.py",
        "git status && git commit -m 'sneaky'",
    )
    for cmd in denied_commands:
        claude_code, claude_reason = guard.evaluate(
            json.dumps({"cwd": "/repo", "tool_name": "Bash", "tool_input": {"command": cmd}}),
            env=env,
        )
        assert claude_code == 2, f"Expected Claude Bash deny for {cmd!r}, got {(claude_code, claude_reason)}"
        assert "dispatch-workers" in claude_reason

        agy_code, agy_out = guard.evaluate(
            json.dumps(
                {
                    "conversationId": "123",
                    "cwd": "/repo",
                    "toolCall": {"name": "run_command", "args": {"CommandLine": cmd}},
                }
            ),
            env=env,
        )
        assert agy_code == 0, f"Expected AGY exit 0 JSON deny for {cmd!r}"
        assert json.loads(agy_out)["decision"] == "deny"

    allowed_commands = (
        "git status",
        "git -C /repo log -n 5 --oneline",
        "gh issue list --state open",
        "python3 skills/chief-of-staff/scripts/briefing_board.py --state-json /tmp/state.json --snapshot /tmp/briefing.html",
        "python3 skills/chief-of-staff/scripts/setup_init.py --repo-root /repo",
        "ls -la src 2>/dev/null",
    )
    for cmd in allowed_commands:
        claude_code, claude_out = guard.evaluate(
            json.dumps({"cwd": "/repo", "tool_name": "Bash", "tool_input": {"command": cmd}}),
            env=env,
        )
        assert (claude_code, claude_out) == (0, ""), f"Expected allow for {cmd!r}, got {(claude_code, claude_out)}"

        agy_code, agy_out = guard.evaluate(
            json.dumps(
                {
                    "conversationId": "123",
                    "cwd": "/repo",
                    "toolCall": {"name": "run_command", "args": {"CommandLine": cmd}},
                }
            ),
            env=env,
        )
        assert agy_code == 0
        assert json.loads(agy_out) == {"decision": "allow"}


def test_chief_allows_orchestration_config_and_fails_closed_on_bad_json(tmp_path: Path) -> None:
    guard = _load_guard()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = {"SKILLS_II_ROLE": "chief", "HOME": str(fake_home)}

    allowed_paths = (
        ".agents/orchestration.json",
        "/repo/.agents/orchestration.json",
        "/repo/.agents/orchestration-overlay.md",
        "~/.config/skills-ii/fleet.json",
        "~/.config/chief-of-staff/fleet.json",
        "~/.local/state/skills-ii/briefing.html",
        "~/.local/state/chief-of-staff/state.json",
        f"{fake_home}/.config/skills-ii/fleet.json",
        f"{fake_home}/.local/state/skills-ii/state.json",
        f"{fake_home}/.gemini/antigravity/brain/conv-1/briefing.md",
        f"{fake_home}/.gemini/antigravity-cli/brain/conv-2/notes.md",
        f"{fake_home}/.gemini/antigravity-ide/brain/conv-3/plan.md",
    )
    for path in allowed_paths:
        assert guard._allowed_chief_path(path, cwd="/repo", env=env) is True, f"Expected allowed: {path}"
        code, out = guard.evaluate(
            json.dumps(
                {
                    "cwd": "/repo",
                    "tool_name": "Write",
                    "tool_input": {"file_path": path},
                }
            ),
            env=env,
        )
        assert (code, out) == (0, ""), f"Expected Write allow for {path}, got {(code, out)}"

    rejected_paths = (
        "/repo/.config/skills-ii/../../src/app.py",
        "~/.config/skills-ii/../../src/app.py",
        ".agents/../src/app.py",
        "/repo/src/app.py",
        "/repo/.agents/hooks.json",
        f"{fake_home}/.gemini/antigravity/settings.json",
    )
    for path in rejected_paths:
        assert guard._allowed_chief_path(path, cwd="/repo", env=env) is False, f"Expected rejected: {path}"

    for bad_input in ("", "{not-json", "[]", "123"):
        code, reason = guard.evaluate(bad_input, env=env)
        assert code == 2
        assert reason != ""


def test_chief_guard_cli_main_stdout_and_stderr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    guard = _load_guard()
    monkeypatch.setenv("SKILLS_II_ROLE", "chief")

    monkeypatch.setattr(
        sys,
        "stdin",
        type("FakeStdin", (), {"read": staticmethod(lambda: json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/app.py"}}))})(),
    )
    assert guard.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "dispatch-workers" in captured.err

    monkeypatch.setattr(
        sys,
        "stdin",
        type(
            "FakeStdin",
            (),
            {
                "read": staticmethod(
                    lambda: json.dumps(
                        {
                            "conversationId": "c1",
                            "cwd": "/repo",
                            "toolCall": {"name": "write_file", "args": {"Path": "/repo/src/app.py"}},
                        }
                    )
                )
            },
        )(),
    )
    assert guard.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["decision"] == "deny"


def test_skill_package_frontmatter_line_budget_and_links() -> None:
    skill_md = SKILL_DIR / "SKILL.md"
    assert skill_md.is_file(), "Missing SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert 120 <= len(lines) <= 240, f"SKILL.md line count {len(lines)} outside [120, 240]"

    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    _, fm_block, _ = text.split("---\n", 2)
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()

    assert fm.get("name") == "chief-of-staff"
    assert fm.get("license") == "MIT"
    desc = fm.get("description", "")
    assert 1 <= len(desc) <= 1024
    assert "Use when " in desc
    assert "Not for " in desc

    license_path = SKILL_DIR / "LICENSE"
    assert license_path.is_file(), "Missing LICENSE"
    assert license_path.read_text(encoding="utf-8") == (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")

    openai_yaml = SKILL_DIR / "agents" / "openai.yaml"
    assert openai_yaml.is_file(), "Missing agents/openai.yaml"
    yaml_text = openai_yaml.read_text(encoding="utf-8")
    for required_key in ("interface:", "display_name:", "short_description:", "default_prompt:"):
        assert required_key in yaml_text

    ref_dir = SKILL_DIR / "references"
    assert (ref_dir / "modes.md").is_file()
    assert (ref_dir / "wake-hooks.md").is_file()

    md_files = [skill_md, *sorted(ref_dir.glob("*.md"))]
    for md_file in md_files:
        md_text = md_file.read_text(encoding="utf-8")
        for match in _MARKDOWN_LINK_RE.finditer(md_text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (md_file.parent / target).resolve()
            assert resolved.exists(), f"Dangling relative link {target!r} in {md_file.relative_to(REPO_ROOT)}"
