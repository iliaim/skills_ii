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
_DARWIN_SYSTEM_SYMLINKS = frozenset({Path("/tmp"), Path("/var"), Path("/etc")})
_TRUSTED_SCRIPTS_DIR = posixpath.normpath(str(Path(__file__).resolve().parent))

_WRITE_TOOLS = frozenset(
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

_SHELL_TOOLS = frozenset(
    {
        "Bash",
        "bash",
        "Shell",
        "shell",
        "run_command",
        "exec_command",
        "shell_command",
    }
)

_DENIED_TOOLS = frozenset({"write_stdin", "send_command_input"})

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


def _has_unsafe_symlink(abs_posix_path: str) -> bool:
    """Return True if leaf or any non-system ancestor component is a symlink."""
    target = Path(abs_posix_path)
    chain = list(reversed(target.parents)) + [target]
    for current in chain:
        try:
            if current.is_symlink():
                if (
                    current != target
                    and sys.platform == "darwin"
                    and current in _DARWIN_SYSTEM_SYMLINKS
                    and os.lstat(current).st_uid == 0
                ):
                    continue
                return True
            if current != target and current.exists() and not current.is_dir():
                return True
        except OSError:
            return True
    return False


def _resolve_lexical_path(
    raw_path: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> str | None:
    """Resolve raw_path against home/cwd without following symlinks; None on traversal or missing cwd."""
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        return None
    if _has_parent_traversal(raw_path):
        return None

    home = _home_dir(env)
    expanded = _expand_user_prefix(raw_path.strip(), home)
    if expanded.startswith("~"):
        return None

    if expanded.startswith("/"):
        norm = _norm_posix(expanded)
    else:
        if not isinstance(cwd, str) or not cwd.strip() or "\x00" in cwd or _has_parent_traversal(cwd):
            return None
        cwd_expanded = _expand_user_prefix(cwd.strip(), home)
        if not cwd_expanded.startswith("/"):
            return None
        cwd_norm = _norm_posix(cwd_expanded)
        norm = _norm_posix(f"{cwd_norm}/{expanded}")

    if _has_parent_traversal(norm):
        return None
    return norm


def _chief_writable_user_roots(env: Mapping[str, str] | None) -> tuple[list[str], list[str]]:
    source_env = env if env is not None else os.environ
    home = _home_dir(source_env)

    xdg_config = source_env.get("XDG_CONFIG_HOME")
    config_roots = [f"{home}/.config"]
    if xdg_config and not _has_parent_traversal(xdg_config):
        config_roots.append(_norm_posix(_expand_user_prefix(xdg_config, home)))

    xdg_state = source_env.get("XDG_STATE_HOME")
    state_roots = [f"{home}/.local/state"]
    if xdg_state and not _has_parent_traversal(xdg_state):
        state_roots.append(_norm_posix(_expand_user_prefix(xdg_state, home)))

    user_roots: list[str] = []
    for root in config_roots + state_roots:
        for ns in _ALLOWED_CONFIG_NAMESPACES:
            user_roots.append(f"{root}/{ns}")

    gemini_roots = [f"{home}/.gemini"]
    for key in ("GEMINI_ROOT", "GEMINI_HOME", "AGY_GEMINI_ROOT"):
        val = source_env.get(key)
        if val and not _has_parent_traversal(val):
            g_norm = _norm_posix(_expand_user_prefix(val, home))
            gemini_roots.append(g_norm)
            gemini_roots.append(f"{g_norm}/.gemini")

    brain_roots: list[str] = []
    for groot in gemini_roots:
        for product in _ALLOWED_GEMINI_PRODUCTS:
            brain_roots.append(f"{groot}/{product}/brain")

    return user_roots, brain_roots


def _allowed_chief_path(
    raw_path: str,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True only for Chief orchestration/state/brain paths without traversal or symlinks."""
    norm = _resolve_lexical_path(raw_path, cwd=cwd, env=env)
    if norm is None:
        return False
    if _has_unsafe_symlink(norm):
        return False

    home = _home_dir(env)
    if isinstance(cwd, str) and cwd.strip() and not _has_parent_traversal(cwd):
        cwd_expanded = _expand_user_prefix(cwd.strip(), home)
        if cwd_expanded.startswith("/"):
            cwd_norm = _norm_posix(cwd_expanded)
            if _has_unsafe_symlink(cwd_norm):
                return False
            for rel in _ALLOWED_REPO_ORCH_FILES:
                if norm == f"{cwd_norm}/{rel}":
                    return True
    elif cwd is None:
        for rel in _ALLOWED_REPO_ORCH_FILES:
            if norm.endswith(f"/{rel}"):
                return True

    user_roots, brain_roots = _chief_writable_user_roots(env)
    for root in user_roots + brain_roots:
        if _is_under_dir(norm, root) and norm != root:
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


def _scan_balanced_parens(text: str, start: int) -> tuple[str, int] | None:
    """Scan balanced (...) starting at index `start` (pointing at '('), respecting quotes/escapes."""
    depth = 1
    i = start + 1
    n = len(text)
    in_single = False
    in_double = False
    escaped = False
    while i < n:
        ch = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return (text[start + 1 : i], i + 1)
        i += 1
    return None


def _extract_substitutions(command: str) -> tuple[bool, list[str]]:
    """Collect commands inside $(...), `...`, <(...), >(...) including inside double quotes."""
    inner_cmds: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(command)

    while i < n:
        ch = command[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single:
            if ch == "`":
                j = i + 1
                inner_buf: list[str] = []
                bt_escaped = False
                closed = False
                while j < n:
                    bch = command[j]
                    if bt_escaped:
                        inner_buf.append(bch)
                        bt_escaped = False
                        j += 1
                        continue
                    if bch == "\\":
                        bt_escaped = True
                        j += 1
                        continue
                    if bch == "`":
                        closed = True
                        j += 1
                        break
                    inner_buf.append(bch)
                    j += 1
                if not closed:
                    return (False, [])
                inner_cmds.append("".join(inner_buf))
                i = j
                continue
            if ch == "$" and i + 1 < n and command[i + 1] == "(":
                if i + 2 < n and command[i + 2] == "(":
                    # Arithmetic expansion $(( ... )) — still inspect inner text just in case.
                    pass
                scanned = _scan_balanced_parens(command, i + 1)
                if scanned is None:
                    return (False, [])
                inner, next_idx = scanned
                inner_cmds.append(inner)
                i = next_idx
                continue
            if not in_double and ch in ("<", ">") and i + 1 < n and command[i + 1] == "(":
                scanned = _scan_balanced_parens(command, i + 1)
                if scanned is None:
                    return (False, [])
                inner, next_idx = scanned
                inner_cmds.append(inner)
                i = next_idx
                continue
        i += 1

    if in_single or in_double or escaped:
        return (False, [])
    return (True, inner_cmds)


def _split_shell_segments(command: str) -> list[str] | None:
    """Split a shell command on ;, &&, ||, |, &, newlines outside quotes; None on syntax error."""
    segments: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    paren_depth = 0
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
            if ch == "(" and (i == 0 or command[i - 1] in ("$", "<", ">")):
                paren_depth += 1
                buf.append(ch)
                i += 1
                continue
            if ch == ")" and paren_depth > 0:
                paren_depth -= 1
                buf.append(ch)
                i += 1
                continue
            if paren_depth == 0:
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

    if in_single or in_double or escaped or paren_depth != 0:
        return None
    tail = "".join(buf).strip()
    if tail:
        segments.append(tail)
    return segments


def _scan_and_strip_redirections(
    segment: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> str | None:
    """Validate all unquoted output/read-write redirections (`>`, `>>`, `<>`, `&>`) and strip them."""
    out: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(segment)

    while i < n:
        ch = segment[i]
        if escaped:
            out.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            out.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue

        if not in_single and not in_double:
            # Skip process substitutions <(...) and >(...) — checked separately.
            if ch in ("<", ">") and i + 1 < n and segment[i + 1] == "(":
                scanned = _scan_balanced_parens(segment, i + 1)
                if scanned is None:
                    return None
                _, next_idx = scanned
                out.append(segment[i:next_idx])
                i = next_idx
                continue

            is_redir = False
            op_len = 0
            if segment.startswith("<>", i):
                is_redir = True
                op_len = 2
            elif segment.startswith("&>>", i):
                is_redir = True
                op_len = 3
            elif segment.startswith("&>", i):
                is_redir = True
                op_len = 2
            elif segment.startswith(">>", i):
                is_redir = True
                op_len = 2
            elif ch == ">":
                is_redir = True
                op_len = 1

            if is_redir:
                # Strip optional preceding fd digits (e.g. `2>`).
                while out and out[-1].isdigit():
                    prev_idx = len(out) - 2
                    if prev_idx < 0 or out[prev_idx].isspace():
                        out.pop()
                        break
                    # multi-digit fd only if preceded by whitespace/start
                    if all(c.isdigit() for c in "".join(out[prev_idx:])):
                        out.pop()
                    else:
                        break

                j = i + op_len
                # Stream duplication: >&1, >&2, >&-
                if j < n and segment[j] == "&":
                    k = j + 1
                    if k < n and (segment[k].isdigit() or segment[k] == "-"):
                        while k < n and segment[k].isdigit():
                            k += 1
                        out.append(" ")
                        i = k
                        continue

                while j < n and segment[j].isspace():
                    j += 1
                if j >= n:
                    return None

                # Parse target word up to unquoted whitespace.
                t_buf: list[str] = []
                t_sq = False
                t_dq = False
                t_esc = False
                while j < n:
                    tch = segment[j]
                    if t_esc:
                        t_buf.append(tch)
                        t_esc = False
                        j += 1
                        continue
                    if tch == "\\" and not t_sq:
                        t_esc = True
                        j += 1
                        continue
                    if tch == "'" and not t_dq:
                        t_sq = not t_sq
                        j += 1
                        continue
                    if tch == '"' and not t_sq:
                        t_dq = not t_dq
                        j += 1
                        continue
                    if not t_sq and not t_dq and tch.isspace():
                        break
                    t_buf.append(tch)
                    j += 1

                if t_sq or t_dq or t_esc or not t_buf:
                    return None
                target = "".join(t_buf)
                if target != "/dev/null" and not _allowed_chief_path(target, cwd=cwd, env=env):
                    return None
                out.append(" ")
                i = j
                continue

        out.append(ch)
        i += 1

    if in_single or in_double or escaped:
        return None
    return "".join(out).strip()


def _check_git_tokens(args: list[str]) -> bool:
    idx = 0
    n = len(args)
    while idx < n:
        tok = args[idx]
        if tok == "-c" or tok.startswith("-c") or tok == "--config-env" or tok.startswith("--config-env="):
            return False
        if tok in ("-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"):
            idx += 2
            continue
        if tok.startswith(("--git-dir=", "--work-tree=", "--namespace=", "-C")):
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

    for item in rest:
        if item == "--output" or item.startswith("--output="):
            return False

    if sub in _READONLY_GIT_SUBCOMMANDS:
        return True
    if sub == "branch":
        for pos, item in enumerate(rest):
            if item in _GIT_BRANCH_MUTATING_FLAGS or item.startswith("--set-upstream"):
                return False
            if not item.startswith("-") and item not in _GIT_BRANCH_READONLY_FLAGS:
                prev = rest[pos - 1] if pos > 0 else ""
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
        idx = 1
        while idx < len(args):
            tok = args[idx]
            if tok in _GH_API_MUTATING_FLAGS or tok.startswith(("-f", "-F", "--field", "--raw-field", "--input")):
                return False
            if tok in ("-X", "--method"):
                if idx + 1 >= len(args) or args[idx + 1].upper() != "GET":
                    return False
                idx += 2
                continue
            if tok.startswith("-X"):
                if tok[2:].upper() != "GET":
                    return False
            if tok.startswith("--method="):
                if tok.split("=", 1)[1].upper() != "GET":
                    return False
            idx += 1
        return True
    return len(args) >= 2 and args[1] in _READONLY_GH_ACTIONS


def _is_trusted_chief_script(
    raw_script: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> tuple[bool, str]:
    resolved = _resolve_lexical_path(raw_script, cwd=cwd, env=env)
    if resolved is None:
        return (False, "")
    if _has_unsafe_symlink(resolved):
        return (False, "")

    script_name = posixpath.basename(resolved)
    if script_name not in _ALLOWED_CHIEF_SCRIPTS:
        return (False, "")

    user_roots, brain_roots = _chief_writable_user_roots(env)
    blocked_prefixes = list(user_roots) + list(brain_roots) + ["/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp"]
    for prefix in blocked_prefixes:
        if _is_under_dir(resolved, prefix):
            return (False, "")

    parent = posixpath.dirname(resolved)
    if parent == _TRUSTED_SCRIPTS_DIR or parent.endswith("/chief-of-staff/scripts"):
        return (True, script_name)
    return (False, "")


def _validate_chief_script_flags(
    script_name: str,
    script_args: list[str],
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if script_name == "briefing_board.py":
        guarded_flags = ("--snapshot", "--live-bootstrap-file")
    elif script_name == "setup_init.py":
        guarded_flags = ("--fleet-config",)
    else:
        guarded_flags = ()

    if not guarded_flags:
        return True

    idx = 0
    while idx < len(script_args):
        tok = script_args[idx]
        matched = False
        for flag in guarded_flags:
            if tok == flag:
                if idx + 1 >= len(script_args):
                    return False
                if not _allowed_chief_path(script_args[idx + 1], cwd=cwd, env=env):
                    return False
                idx += 2
                matched = True
                break
            if tok.startswith(flag + "="):
                val = tok.split("=", 1)[1]
                if not _allowed_chief_path(val, cwd=cwd, env=env):
                    return False
                idx += 1
                matched = True
                break
        if not matched:
            idx += 1
    return True


def _check_python_tokens(
    args: list[str],
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if not args:
        return False
    idx = 0
    while idx < len(args):
        tok = args[idx]
        if tok == "-c" or tok.startswith("-c") or tok == "-m":
            return False
        if tok in ("-B", "-E", "-I", "-O", "-s", "-S", "-u", "-v"):
            idx += 1
            continue
        if tok.startswith("-"):
            return False
        break
    if idx >= len(args):
        return False

    ok, script_name = _is_trusted_chief_script(args[idx], cwd=cwd, env=env)
    if not ok:
        return False
    return _validate_chief_script_flags(script_name, args[idx + 1 :], cwd=cwd, env=env)


def _check_sed_tokens(args: list[str]) -> bool:
    expect_expr = False
    for item in args:
        if expect_expr:
            expect_expr = False
            if re.search(r"(?:^|[;\n])\s*[wW]\b|/[eE](?:[;\n]|$)", item):
                return False
            continue
        if item == "--":
            continue
        if item == "-i" or item == "--in-place" or item.startswith("--in-place="):
            return False
        if item in ("-f", "--file") or item.startswith("--file=") or (item.startswith("-f") and len(item) > 2):
            return False
        if item in ("-e", "--expression"):
            expect_expr = True
            continue
        if item.startswith("-") and not item.startswith("--") and "i" in item[1:]:
            return False
        if not item.startswith("-"):
            if re.search(r"(?:^|[;\n])\s*[wW]\b|/[eE](?:[;\n]|$)", item):
                return False
    return not expect_expr


def _check_sort_tokens(args: list[str]) -> bool:
    for item in args:
        if item == "--":
            break
        if item == "-o" or item == "--output" or item.startswith("--output="):
            return False
        if item.startswith("-") and not item.startswith("--") and "o" in item[1:]:
            return False
    return True


def _check_uniq_tokens(args: list[str]) -> bool:
    positional = 0
    idx = 0
    after_double_dash = False
    while idx < len(args):
        tok = args[idx]
        if not after_double_dash and tok == "--":
            after_double_dash = True
            idx += 1
            continue
        if not after_double_dash and tok in ("-f", "-s", "-w", "--skip-fields", "--skip-chars", "--check-chars"):
            idx += 2
            continue
        if not after_double_dash and tok.startswith("-") and tok != "-":
            idx += 1
            continue
        positional += 1
        if positional > 1:
            return False
        idx += 1
    return True


def _check_rg_tokens(args: list[str]) -> bool:
    for item in args:
        if item == "--":
            break
        if item == "--pre" or item.startswith("--pre="):
            return False
    return True


def _check_find_tokens(args: list[str]) -> bool:
    for item in args:
        if item in ("-delete", "-fls") or item.startswith(("-exec", "-ok", "-fprint")):
            return False
    return True


def _is_tokens_allowed(
    tokens: list[str],
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if not tokens:
        return True

    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if _ENV_ASSIGN_RE.match(tok) or tok in ("env", "command"):
            idx += 1
            continue
        break
    if idx >= len(tokens):
        return False

    cmd_tokens = tokens[idx:]
    exe = posixpath.basename(cmd_tokens[0].replace("\\", "/"))
    args = cmd_tokens[1:]

    if exe == "git":
        return _check_git_tokens(args)
    if exe == "gh":
        return _check_gh_tokens(args)
    if exe == "python" or exe.startswith("python3"):
        return _check_python_tokens(args, cwd=cwd, env=env)
    if exe == "sed":
        return _check_sed_tokens(args)
    if exe == "sort":
        return _check_sort_tokens(args)
    if exe == "uniq":
        return _check_uniq_tokens(args)
    if exe == "rg":
        return _check_rg_tokens(args)
    if exe == "find":
        return _check_find_tokens(args)
    if exe in _READONLY_SHELL_COMMANDS:
        return True
    return False


def _is_segment_allowed(
    segment: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    clean_seg = _scan_and_strip_redirections(segment, cwd=cwd, env=env)
    if clean_seg is None:
        return False
    if not clean_seg:
        return True
    try:
        tokens = shlex.split(clean_seg)
    except ValueError:
        return False
    return _is_tokens_allowed(tokens, cwd=cwd, env=env)


def _is_command_allowed(
    command: str,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if not isinstance(command, str) or not command.strip():
        return False
    ok_subs, inner_cmds = _extract_substitutions(command)
    if not ok_subs:
        return False
    for inner in inner_cmds:
        if not _is_command_allowed(inner, cwd=cwd, env=env):
            return False
    segments = _split_shell_segments(command)
    if not segments:
        return False
    return all(_is_segment_allowed(seg, cwd=cwd, env=env) for seg in segments)


def _is_argv_allowed(
    argv: list[Any],
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> bool:
    if not argv or not all(isinstance(item, str) and item != "" for item in argv):
        return False
    return _is_tokens_allowed(list(argv), cwd=cwd, env=env)


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

    if tool_name in _DENIED_TOOLS:
        return _format_deny(is_agy)

    if tool_name in _READ_ONLY_TOOLS:
        return _format_allow(is_agy)

    if tool_name in _WRITE_TOOLS:
        targets = _extract_target_paths(tool_args)
        if not targets:
            return _format_deny(is_agy)
        if all(_allowed_chief_path(target, cwd=cwd, env=source_env) for target in targets):
            return _format_allow(is_agy)
        return _format_deny(is_agy)

    if tool_name in _SHELL_TOOLS:
        raw_argv = tool_args.get("argv")
        if isinstance(raw_argv, list):
            if _is_argv_allowed(raw_argv, cwd=cwd, env=source_env):
                return _format_allow(is_agy)
            return _format_deny(is_agy)

        raw_cmd = tool_args.get("command")
        if isinstance(raw_cmd, list):
            if _is_argv_allowed(raw_cmd, cwd=cwd, env=source_env):
                return _format_allow(is_agy)
            return _format_deny(is_agy)

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
