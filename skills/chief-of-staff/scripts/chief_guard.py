#!/usr/bin/env python3
"""Mechanical PreToolUse guard enforcing Chief of Staff read/coordinate-only boundaries."""
from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping

REASON = (
    "Chief of Staff sessions (SKILLS_II_ROLE=chief) cannot modify project source, "
    "run builds/tests, or mutate git history directly. Delegate implementation and "
    "repository changes via `dispatch-workers` or `orchestrate-agents`."
)

_ROLE_ENV_VAR = "SKILLS_II_ROLE"
_CHIEF_ROLE = "chief"

_FILE_EDIT_TOOLS = frozenset(
    {
        "Edit",
        "Write",
        "MultiEdit",
        "NotebookEdit",
        "apply_patch",
        "write_to_file",
        "write_file",
        "edit_file",
        "replace_file_content",
        "multi_replace_file_content",
    }
)

_SHELL_TOOLS = frozenset({"Bash", "bash", "Shell", "shell", "run_command"})

_READ_ONLY_TOOLS = frozenset(
    {
        "Read",
        "Glob",
        "Grep",
        "LS",
        "WebFetch",
        "WebSearch",
        "read_file",
        "view_file",
        "view_file_outline",
        "view_code_item",
        "grep_search",
        "find_by_name",
        "list_dir",
        "list_resources",
        "read_resource",
        "search_web",
        "ask_question",
        "update_focus",
        "update_steps",
        "send_message",
        "invoke_subagent",
        "define_subagent",
        "manage_subagents",
        "swarm",
        "schedule",
        "manage_task",
    }
)

_ALLOWED_REPO_ORCH_FILES = frozenset(
    {
        ".agents/orchestration.json",
        ".agents/orchestration-overlay.md",
    }
)

_ALLOWED_CONFIG_NAMESPACES = frozenset({"skills-ii", "chief-of-staff"})
_ALLOWED_GEMINI_PRODUCTS = frozenset({"antigravity", "antigravity-cli", "antigravity-ide"})
_ALLOWED_CHIEF_SCRIPTS = frozenset(
    {
        "setup_init.py",
        "briefing_board.py",
        "redact.py",
        "chief_guard.py",
    }
)

_READONLY_GIT_SUBCOMMANDS = frozenset(
    {
        "blame",
        "cat-file",
        "check-ignore",
        "describe",
        "diff",
        "for-each-ref",
        "grep",
        "log",
        "ls-files",
        "ls-tree",
        "merge-base",
        "name-rev",
        "rev-parse",
        "shortlog",
        "show",
        "show-ref",
        "status",
    }
)

_GIT_BRANCH_MUTATING_FLAGS = frozenset(
    {
        "-c",
        "-C",
        "-d",
        "-D",
        "-f",
        "-m",
        "-M",
        "--copy",
        "--delete",
        "--force",
        "--move",
        "--set-upstream-to",
        "--unset-upstream",
    }
)

_GIT_BRANCH_READONLY_FLAGS = frozenset(
    {
        "-a",
        "--all",
        "-l",
        "--list",
        "-r",
        "--remotes",
        "-v",
        "-vv",
        "--verbose",
        "--show-current",
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
    }
)

_READONLY_GH_ACTIONS = frozenset({"list", "view", "status", "checks", "diff"})
_GH_API_MUTATING_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field", "--input"})

_READONLY_SHELL_COMMANDS = frozenset(
    {
        "[",
        "basename",
        "cat",
        "cmp",
        "cut",
        "date",
        "diff",
        "dirname",
        "echo",
        "egrep",
        "false",
        "fgrep",
        "file",
        "find",
        "grep",
        "head",
        "id",
        "jq",
        "ls",
        "md5",
        "printf",
        "pwd",
        "readlink",
        "realpath",
        "rg",
        "sed",
        "sha256sum",
        "shasum",
        "sort",
        "stat",
        "tail",
        "test",
        "tr",
        "true",
        "uname",
        "uniq",
        "wc",
        "which",
        "whoami",
    }
)

_PATH_KEYS = (
    "file_path",
    "path",
    "Path",
    "TargetFile",
    "target_file",
    "notebook_path",
    "destination",
    "filename",
)
_COMMAND_KEYS = ("command", "CommandLine", "cmd", "script")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


def _home_dir(env: Mapping[str, str] | None) -> str:
    source = env if env is not None else os.environ
    home = source.get("HOME")
    if home:
        return home.rstrip("/") or "/"
    return str(Path.home()).rstrip("/") or "/"


def _norm_posix(path_text: str) -> str:
    return posixpath.normpath(path_text.replace("\\", "/"))


def _has_parent_traversal(raw_path: str) -> bool:
    parts = raw_path.replace("\\", "/").split("/")
    return ".." in parts


def _expand_user_prefix(raw_path: str, home: str) -> str:
    if raw_path == "~":
        return home
    if raw_path.startswith("~/"):
        return f"{home}/{raw_path[2:]}"
    return raw_path


def _is_under_dir(candidate: str, base_dir: str) -> bool:
    base = base_dir.rstrip("/")
    if not base:
        return False
    return candidate == base or candidate.startswith(base + "/")


def _allowed_chief_path(
    raw_path: str,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True only for Chief orchestration/state/brain paths without traversal or symlinks."""
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        return False
    if _has_parent_traversal(raw_path):
        return False

    source_env = env if env is not None else os.environ
    home = _home_dir(source_env)
    expanded = _expand_user_prefix(raw_path.strip(), home)
    if expanded.startswith("~"):
        return False

    norm = _norm_posix(expanded)
    if _has_parent_traversal(norm):
        return False

    try:
        if os.path.islink(expanded):
            return False
    except OSError:
        return False

    if norm in _ALLOWED_REPO_ORCH_FILES:
        return True

    if cwd and not _has_parent_traversal(cwd):
        cwd_norm = _norm_posix(_expand_user_prefix(cwd, home))
        for rel in _ALLOWED_REPO_ORCH_FILES:
            if norm == f"{cwd_norm}/{rel}":
                return True
    elif not cwd:
        for rel in _ALLOWED_REPO_ORCH_FILES:
            if norm.endswith(f"/{rel}"):
                return True

    xdg_config = source_env.get("XDG_CONFIG_HOME")
    config_roots = [f"{home}/.config"]
    if xdg_config and not _has_parent_traversal(xdg_config):
        config_roots.append(_norm_posix(_expand_user_prefix(xdg_config, home)))

    xdg_state = source_env.get("XDG_STATE_HOME")
    state_roots = [f"{home}/.local/state"]
    if xdg_state and not _has_parent_traversal(xdg_state):
        state_roots.append(_norm_posix(_expand_user_prefix(xdg_state, home)))

    for root in config_roots + state_roots:
        for ns in _ALLOWED_CONFIG_NAMESPACES:
            if _is_under_dir(norm, f"{root}/{ns}") and norm != f"{root}/{ns}":
                return True

    gemini_roots = [f"{home}/.gemini"]
    for key in ("GEMINI_ROOT", "GEMINI_HOME", "AGY_GEMINI_ROOT"):
        val = source_env.get(key)
        if val and not _has_parent_traversal(val):
            g_norm = _norm_posix(_expand_user_prefix(val, home))
            gemini_roots.append(g_norm)
            gemini_roots.append(f"{g_norm}/.gemini")

    for groot in gemini_roots:
        for product in _ALLOWED_GEMINI_PRODUCTS:
            brain_dir = f"{groot}/{product}/brain"
            if _is_under_dir(norm, brain_dir) and norm != brain_dir:
                return True

    return False


def _extract_target_paths(tool_args: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in _PATH_KEYS:
        val = tool_args.get(key)
        if isinstance(val, str) and val.strip():
            paths.append(val)
    edits = tool_args.get("edits")
    if isinstance(edits, list):
        for item in edits:
            if isinstance(item, Mapping):
                for key in _PATH_KEYS:
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        paths.append(val)
    return paths


def _split_shell_segments(command: str) -> list[str] | None:
    """Split a shell command on ;, &&, ||, |, &, newlines outside quotes; None on syntax error."""
    segments: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(command)

    while i < n:
        ch = command[i]
        if escaped:
            buf.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            buf.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if ch == "`":
                return None
            if ch == "$" and i + 1 < n and command[i + 1] == "(":
                return None
            if ch in (";", "\n", "|"):
                seg = "".join(buf).strip()
                if seg:
                    segments.append(seg)
                buf.clear()
                if ch == "|" and i + 1 < n and command[i + 1] == "|":
                    i += 2
                else:
                    i += 1
                continue
            if ch == "&":
                # Keep stream redirections like 2>&1 or >&2 intact inside the segment.
                prev_ch = command[i - 1] if i > 0 else ""
                next_ch = command[i + 1] if i + 1 < n else ""
                if prev_ch == ">" or next_ch == ">":
                    buf.append(ch)
                    i += 1
                    continue
                seg = "".join(buf).strip()
                if seg:
                    segments.append(seg)
                buf.clear()
                if next_ch == "&":
                    i += 2
                else:
                    i += 1
                continue
        buf.append(ch)
        i += 1

    if in_single or in_double or escaped:
        return None
    tail = "".join(buf).strip()
    if tail:
        segments.append(tail)
    return segments


def _strip_redirections_and_check(
    tokens: list[str],
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> list[str] | None:
    """Validate shell redirections in tokenized segment and return remaining command tokens."""
    clean: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # Handle stream duplicates like 2>&1, >&2, 1>&2
        if re.fullmatch(r"(?:\d+|&)?>>?&(?:\d+|-)", tok):
            i += 1
            continue
        redir_match = re.fullmatch(r"(?:\d+|&)?(>>?)(.*)", tok)
        if redir_match:
            target = redir_match.group(2)
            if not target:
                if i + 1 >= n:
                    return None
                target = tokens[i + 1]
                i += 2
            else:
                i += 1
            if target == "/dev/null":
                continue
            if not _allowed_chief_path(target, cwd=cwd, env=env):
                return None
            continue
        clean.append(tok)
        i += 1
    return clean


def _check_git_tokens(args: list[str]) -> bool:
    idx = 0
    n = len(args)
    while idx < n:
        tok = args[idx]
        if tok in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix"):
            idx += 2
            continue
        if tok.startswith(("--git-dir=", "--work-tree=", "--namespace=", "-C", "-c")):
            idx += 1
            continue
        if tok.startswith("-"):
            idx += 1
            continue
        break

    if idx >= n:
        return False
    sub = args[idx]
    rest = args[idx + 1 :]

    if sub in _READONLY_GIT_SUBCOMMANDS:
        return True
    if sub == "branch":
        for item in rest:
            if item in _GIT_BRANCH_MUTATING_FLAGS or item.startswith("--set-upstream"):
                return False
            if not item.startswith("-") and item not in _GIT_BRANCH_READONLY_FLAGS:
                # Positional branch name without --list/--contains creates a branch.
                prev = rest[rest.index(item) - 1] if rest.index(item) > 0 else ""
                if prev not in ("--contains", "--no-contains", "--merged", "--no-merged", "--points-at"):
                    return False
        return True
    if sub == "worktree":
        return bool(rest) and rest[0] == "list"
    if sub == "stash":
        return bool(rest) and rest[0] in ("list", "show")
    if sub == "remote":
        return not rest or rest[0] in ("-v", "--verbose", "show")
    if sub == "config":
        return any(flag in rest for flag in ("--get", "--get-all", "--list", "-l"))
    return False


def _check_gh_tokens(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] == "search":
        return True
    if args[0] == "auth":
        return len(args) >= 2 and args[1] == "status"
    if args[0] == "api":
        for idx, tok in enumerate(args[1:], start=1):
            if tok in _GH_API_MUTATING_FLAGS or tok.startswith(("--field=", "--raw-field=", "--input=")):
                return False
            if tok in ("-X", "--method") and idx + 1 < len(args):
                if args[idx + 1].upper() != "GET":
                    return False
            if tok.startswith("--method=") and tok.split("=", 1)[1].upper() != "GET":
                return False
        return True
    return len(args) >= 2 and args[1] in _READONLY_GH_ACTIONS


def _check_python_tokens(args: list[str]) -> bool:
    if not args:
        return False
    idx = 0
    while idx < len(args):
        tok = args[idx]
        if tok == "-c" or tok.startswith("-c"):
            return False
        if tok == "-m":
            return False
        if tok in ("-B", "-E", "-I", "-O", "-s", "-S", "-u", "-v"):
            idx += 1
            continue
        if tok.startswith("-"):
            return False
        break
    if idx >= len(args):
        return False
    script_name = posixpath.basename(args[idx].replace("\\", "/"))
    return script_name in _ALLOWED_CHIEF_SCRIPTS


def _is_segment_allowed(
    segment: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False
    if not tokens:
        return True

    stripped = _strip_redirections_and_check(tokens, cwd=cwd, env=env)
    if stripped is None:
        return False
    if not stripped:
        return True

    idx = 0
    while idx < len(stripped):
        tok = stripped[idx]
        if _ENV_ASSIGN_RE.match(tok) or tok in ("env", "command"):
            idx += 1
            continue
        break
    if idx >= len(stripped):
        return False

    cmd_tokens = stripped[idx:]
    exe = posixpath.basename(cmd_tokens[0].replace("\\", "/"))
    args = cmd_tokens[1:]

    if exe == "git":
        return _check_git_tokens(args)
    if exe == "gh":
        return _check_gh_tokens(args)
    if exe == "python" or exe.startswith("python3"):
        return _check_python_tokens(args)
    if exe == "sed":
        for item in args:
            if item == "-i" or item.startswith("-i") or item == "--in-place" or item.startswith("--in-place="):
                return False
        return True
    if exe == "find":
        for item in args:
            if item in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf"):
                return False
        return True
    if exe in _READONLY_SHELL_COMMANDS:
        return True
    return False


def _is_command_allowed(
    command: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if not isinstance(command, str) or not command.strip():
        return False
    segments = _split_shell_segments(command)
    if not segments:
        return False
    return all(_is_segment_allowed(seg, cwd=cwd, env=env) for seg in segments)


def _format_allow(is_agy: bool) -> tuple[int, str]:
    if is_agy:
        return (0, json.dumps({"decision": "allow"}))
    return (0, "")


def _format_deny(is_agy: bool, reason: str = REASON) -> tuple[int, str]:
    if is_agy:
        return (0, json.dumps({"decision": "deny", "reason": reason}))
    return (2, reason)


def evaluate(stdin_text: str, env: Mapping[str, str] | None = None) -> tuple[int, str]:
    """Evaluate a PreToolUse hook stdin payload for Chief of Staff role enforcement."""
    source_env = env if env is not None else os.environ
    role = str(source_env.get(_ROLE_ENV_VAR, "")).strip().lower()

    payload: dict[str, Any] | None = None
    is_agy = False
    if isinstance(stdin_text, str) and stdin_text.strip():
        try:
            parsed = json.loads(stdin_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
            is_agy = "toolCall" in parsed

    if role != _CHIEF_ROLE:
        return _format_allow(is_agy)

    if payload is None:
        return (2, REASON)

    cwd_val = payload.get("cwd")
    cwd = cwd_val if isinstance(cwd_val, str) and cwd_val.strip() else None

    if is_agy:
        tool_call = payload.get("toolCall")
        if not isinstance(tool_call, Mapping):
            return _format_deny(True)
        tool_name = str(tool_call.get("name") or "")
        raw_args = tool_call.get("args")
        tool_args: Mapping[str, Any] = raw_args if isinstance(raw_args, Mapping) else {}
    else:
        tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
        raw_args = payload.get("tool_input") or payload.get("toolInput")
        tool_args = raw_args if isinstance(raw_args, Mapping) else {}

    if not tool_name:
        return _format_deny(is_agy)

    if tool_name in _READ_ONLY_TOOLS:
        return _format_allow(is_agy)

    if tool_name in _FILE_EDIT_TOOLS:
        targets = _extract_target_paths(tool_args)
        if not targets:
            return _format_deny(is_agy)
        if all(_allowed_chief_path(target, cwd=cwd, env=source_env) for target in targets):
            return _format_allow(is_agy)
        return _format_deny(is_agy)

    if tool_name in _SHELL_TOOLS:
        command = ""
        for key in _COMMAND_KEYS:
            val = tool_args.get(key)
            if isinstance(val, str) and val.strip():
                command = val
                break
        if _is_command_allowed(command, cwd=cwd, env=source_env):
            return _format_allow(is_agy)
        return _format_deny(is_agy)

    return _format_allow(is_agy)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint reading PreToolUse JSON from stdin."""
    _ = argv
    stdin_text = sys.stdin.read()
    code, output = evaluate(stdin_text)
    if code == 0:
        if output:
            sys.stdout.write(output + "\n")
        return 0
    if output:
        sys.stderr.write(output + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
