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
_ROLE_ENV_VAR, _CHIEF_ROLE = "SKILLS_II_ROLE", "chief"
_DARWIN_SYSTEM_SYMLINKS = frozenset({Path("/tmp"), Path("/var"), Path("/etc")})
_TRUSTED_SCRIPTS_DIR = posixpath.normpath(str(Path(__file__).resolve().parent))
_TRUSTED_BIN_DIRS = frozenset({"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"})

# Category-gated PreToolUse model: _DENIED_TOOLS are always blocked, _WRITE_TOOLS are restricted
# to Chief orchestration/state/brain paths, _SHELL_TOOLS are read-only inspected, and all other tools pass.
_WRITE_TOOLS = frozenset({
    "Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch",
    "write_to_file", "write_file", "edit_file", "create_file",
    "replace_file_content", "multi_replace_file_content",
})
_SHELL_TOOLS = frozenset({"Bash", "bash", "Shell", "shell", "run_command", "exec_command", "shell_command"})
_DENIED_TOOLS = frozenset({
    "write_stdin", "send_command_input", "delete_file", "remove_file", "move_file", "rename_file",
})

_ALLOWED_REPO_ORCH_FILES = frozenset({".agents/orchestration.json", ".agents/orchestration-overlay.md"})
_ALLOWED_CONFIG_NAMESPACES = frozenset({"skills-ii", "chief-of-staff"})
_ALLOWED_GEMINI_PRODUCTS = frozenset({"antigravity", "antigravity-cli", "antigravity-ide"})
_ALLOWED_CHIEF_SCRIPTS = frozenset({"setup_init.py", "briefing_board.py", "redact.py", "chief_guard.py"})

_READONLY_GIT_SUBCOMMANDS = frozenset({
    "blame", "cat-file", "check-ignore", "describe", "diff", "for-each-ref", "grep",
    "log", "ls-files", "ls-tree", "merge-base", "name-rev", "rev-parse", "shortlog",
    "show", "show-ref", "status",
})
_GIT_BRANCH_MUTATING_FLAGS = frozenset({
    "-c", "-C", "-d", "-D", "-f", "-m", "-M", "--copy", "--delete",
    "--force", "--move", "--set-upstream-to", "--unset-upstream",
})
_GIT_BRANCH_READONLY_FLAGS = frozenset({
    "-a", "--all", "-l", "--list", "-r", "--remotes", "-v", "-vv", "--verbose",
    "--show-current", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at",
})
_READONLY_GH_ACTIONS = frozenset({"list", "view", "status", "checks", "diff"})
_GH_API_MUTATING_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field", "--input"})
_READONLY_SHELL_COMMANDS = frozenset({
    "[", "basename", "cat", "cmp", "cut", "date", "diff", "dirname", "echo", "egrep",
    "false", "fgrep", "file", "find", "grep", "head", "id", "jq", "ls", "md5",
    "printf", "pwd", "readlink", "realpath", "rg", "sed", "sha256sum", "shasum",
    "sort", "stat", "tail", "test", "tr", "true", "uname", "uniq", "wc", "which", "whoami",
})

_PATH_KEYS = ("file_path", "path", "Path", "TargetFile", "target_file", "notebook_path", "destination", "filename")
_COMMAND_KEYS = ("command", "CommandLine", "cmd", "script")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_SED_WRITE_EXEC_RE = re.compile(r"(?:^|[;\n])\s*[wW]\b|/[eE](?:[;\n]|$)")


class _QuoteState:
    """Tracks single-quote, double-quote, and backslash-escape state in POSIX shell text."""

    __slots__ = ("in_single", "in_double", "escaped")

    def __init__(self) -> None:
        self.in_single = self.in_double = self.escaped = False

    def step(self, ch: str) -> bool:
        """Advance one character; return True when `ch` is a quote/escape syntax delimiter or escaped."""
        if self.escaped:
            self.escaped = False
            return True
        if ch == "\\" and not self.in_single:
            self.escaped = True
            return True
        if ch == "'" and not self.in_double:
            self.in_single = not self.in_single
            return True
        if ch == '"' and not self.in_single:
            self.in_double = not self.in_double
            return True
        return False

    @property
    def unquoted(self) -> bool:
        return not (self.in_single or self.in_double or self.escaped)

    @property
    def balanced(self) -> bool:
        return not (self.in_single or self.in_double or self.escaped)


def _home_dir(env: Mapping[str, str] | None) -> str:
    home = (env if env is not None else os.environ).get("HOME")
    return (home.rstrip("/") or "/") if home else (str(Path.home()).rstrip("/") or "/")


def _norm_posix(path_text: str) -> str:
    return posixpath.normpath(path_text.replace("\\", "/"))


def _has_traversal(raw_path: str) -> bool:
    return ".." in raw_path.replace("\\", "/").split("/")


def _expand_home(raw_path: str, home: str) -> str:
    return home if raw_path == "~" else (f"{home}/{raw_path[2:]}" if raw_path.startswith("~/") else raw_path)


def _is_under_dir(candidate: str, base_dir: str) -> bool:
    base = base_dir.rstrip("/")
    return bool(base) and (candidate == base or candidate.startswith(base + "/"))


def _has_unsafe_symlink(abs_posix_path: str) -> bool:
    """Return True if leaf or any non-system ancestor component is a symlink."""
    target = Path(abs_posix_path)
    for current in list(reversed(target.parents)) + [target]:
        try:
            if current.is_symlink():
                if (
                    current != target and sys.platform == "darwin"
                    and current in _DARWIN_SYSTEM_SYMLINKS and os.lstat(current).st_uid == 0
                ):
                    continue
                return True
            if current != target and current.exists() and not current.is_dir():
                return True
        except OSError:
            return True
    return False


def _resolve_valid_cwd(cwd: str | None, env: Mapping[str, str] | None) -> str | None:
    if not isinstance(cwd, str) or not cwd.strip() or "\x00" in cwd or _has_traversal(cwd):
        return None
    expanded = _expand_home(cwd.strip(), _home_dir(env))
    return _norm_posix(expanded) if expanded.startswith("/") else None


def _resolve_lexical_path(raw_path: str, cwd: str | None, env: Mapping[str, str] | None) -> str | None:
    """Resolve raw_path against home/cwd without following symlinks; None on traversal or missing cwd."""
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path or _has_traversal(raw_path):
        return None
    expanded = _expand_home(raw_path.strip(), _home_dir(env))
    if expanded.startswith("~"):
        return None
    if expanded.startswith("/"):
        norm = _norm_posix(expanded)
    elif (cwd_norm := _resolve_valid_cwd(cwd, env)) is not None:
        norm = _norm_posix(f"{cwd_norm}/{expanded}")
    else:
        return None
    return None if _has_traversal(norm) else norm


def _chief_writable_user_roots(env: Mapping[str, str] | None) -> tuple[list[str], list[str]]:
    source_env, home = (env if env is not None else os.environ), _home_dir(env)
    cfg_roots, st_roots = [f"{home}/.config"], [f"{home}/.local/state"]
    for var, target in (("XDG_CONFIG_HOME", cfg_roots), ("XDG_STATE_HOME", st_roots)):
        if (val := source_env.get(var)) and not _has_traversal(val):
            target.append(_norm_posix(_expand_home(val, home)))
    user_roots = [f"{root}/{ns}" for root in cfg_roots + st_roots for ns in _ALLOWED_CONFIG_NAMESPACES]
    gemini_roots = [f"{home}/.gemini"]
    for key in ("GEMINI_ROOT", "GEMINI_HOME", "AGY_GEMINI_ROOT"):
        if (val := source_env.get(key)) and not _has_traversal(val):
            g_norm = _norm_posix(_expand_home(val, home))
            gemini_roots.extend((g_norm, f"{g_norm}/.gemini"))
    return user_roots, [f"{g}/{p}/brain" for g in gemini_roots for p in _ALLOWED_GEMINI_PRODUCTS]


def _allowed_chief_path(raw_path: str, cwd: str | None = None, env: Mapping[str, str] | None = None) -> bool:
    """Return True only for Chief orchestration/state/brain paths without traversal or symlinks."""
    norm = _resolve_lexical_path(raw_path, cwd=cwd, env=env)
    if norm is None or _has_unsafe_symlink(norm):
        return False
    cwd_norm = _resolve_valid_cwd(cwd, env)
    if cwd_norm is not None and not _has_unsafe_symlink(cwd_norm) and any(norm == f"{cwd_norm}/{r}" for r in _ALLOWED_REPO_ORCH_FILES):
        return True
    user_roots, brain_roots = _chief_writable_user_roots(env)
    return any(_is_under_dir(norm, root) and norm != root for root in user_roots + brain_roots)


def _extract_target_paths(tool_args: Mapping[str, Any]) -> list[str]:
    containers: list[Mapping[str, Any]] = [tool_args]
    if isinstance(edits := tool_args.get("edits"), list):
        containers.extend(item for item in edits if isinstance(item, Mapping))
    return [val for box in containers for key in _PATH_KEYS if isinstance((val := box.get(key)), str) and val.strip()]


def _scan_balanced_parens(text: str, start: int) -> tuple[str, int] | None:
    """Scan balanced (...) starting at `start` (pointing at '('), respecting quotes/escapes."""
    depth, i, qs = 1, start + 1, _QuoteState()
    while i < len(text):
        ch = text[i]
        if not qs.step(ch) and qs.unquoted:
            depth += 1 if ch == "(" else (-1 if ch == ")" else 0)
            if depth == 0:
                return (text[start + 1 : i], i + 1)
        i += 1
    return None


def _scan_backtick(text: str, start: int) -> tuple[str, int] | None:
    """Scan a `...` command substitution starting at `start` (pointing at '`')."""
    j, escaped, buf = start + 1, False, []
    while j < len(text):
        ch = text[j]
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "`":
            return ("".join(buf), j + 1)
        else:
            buf.append(ch)
        j += 1
    return None


def _extract_substitutions(command: str) -> tuple[bool, list[str]]:
    """Collect commands inside $(...), `...`, <(...), >(...) including inside double quotes."""
    inner_cmds: list[str] = []
    qs, i, n = _QuoteState(), 0, len(command)
    while i < n:
        ch = command[i]
        if not qs.step(ch) and not qs.in_single and not qs.escaped:
            if ch == "`":
                scanned = _scan_backtick(command, i)
            elif (ch == "$" or (not qs.in_double and ch in ("<", ">"))) and i + 1 < n and command[i + 1] == "(":
                scanned = _scan_balanced_parens(command, i + 1)
            else:
                i += 1
                continue
            if scanned is None:
                return (False, [])
            inner, i = scanned
            inner_cmds.append(inner)
            continue
        i += 1
    return (True, inner_cmds) if qs.balanced else (False, [])


def _split_shell_segments(command: str) -> list[str] | None:
    """Split a shell command on ;, &&, ||, |, &, newlines outside quotes; None on syntax error."""
    segments, buf, qs, i, n = [], [], _QuoteState(), 0, len(command)
    while i < n:
        ch = command[i]
        if not qs.step(ch) and qs.unquoted:
            if ch in ("$", "<", ">") and i + 1 < n and command[i + 1] == "(":
                scanned = _scan_balanced_parens(command, i + 1)
                if scanned is None:
                    return None
                buf.append(command[i : scanned[1]])
                i = scanned[1]
                continue
            if ch in (";", "\n", "|") or (
                ch == "&" and (i == 0 or command[i - 1] != ">") and (i + 1 >= n or command[i + 1] != ">")
            ):
                if seg := "".join(buf).strip():
                    segments.append(seg)
                buf.clear()
                i += 2 if (ch in ("|", "&") and i + 1 < n and command[i + 1] == ch) else 1
                continue
        buf.append(ch)
        i += 1
    if not qs.balanced:
        return None
    if tail := "".join(buf).strip():
        segments.append(tail)
    return segments


def _scan_and_strip_redirections(segment: str, cwd: str | None, env: Mapping[str, str] | None) -> str | None:
    """Validate all unquoted output/read-write redirections (`>`, `>>`, `<>`, `&>`) and strip them."""
    out, qs, i, n = [], _QuoteState(), 0, len(segment)
    while i < n:
        ch = segment[i]
        if not qs.step(ch) and qs.unquoted:
            if ch in ("<", ">") and i + 1 < n and segment[i + 1] == "(":
                scanned = _scan_balanced_parens(segment, i + 1)
                if scanned is None:
                    return None
                out.append(segment[i : scanned[1]])
                i = scanned[1]
                continue
            op_len = 3 if segment.startswith("&>>", i) else (
                2 if segment.startswith(("<>", "&>", ">>"), i) else (1 if ch == ">" else 0)
            )
            if op_len:
                fd_chars = 0
                while fd_chars < len(out) and out[-1 - fd_chars].isdigit():
                    fd_chars += 1
                if fd_chars and (fd_chars == len(out) or out[-1 - fd_chars].isspace()):
                    del out[-fd_chars:]
                j = i + op_len
                if j < n and segment[j] == "&" and j + 1 < n and (segment[j + 1].isdigit() or segment[j + 1] == "-"):
                    k = j + 2
                    while k < n and segment[k].isdigit():
                        k += 1
                    out.append(" ")
                    i = k
                    continue
                while j < n and segment[j].isspace():
                    j += 1
                t_buf, t_qs = [], _QuoteState()
                while j < n and not (
                    not t_qs.step(segment[j]) and t_qs.unquoted and (segment[j].isspace() or segment[j] in "<>&();|")
                ):
                    t_buf.append(segment[j])
                    j += 1
                raw_target = "".join(t_buf)
                if not t_qs.balanced or not raw_target or _has_active_expansion(raw_target):
                    return None
                try:
                    unquoted = shlex.split(raw_target)
                except ValueError:
                    return None
                if len(unquoted) != 1:
                    return None
                target = unquoted[0]
                if target.startswith("~") and not (raw_target == "~" or raw_target.startswith("~/")):
                    return None
                if target != "/dev/null" and not _allowed_chief_path(target, cwd=cwd, env=env):
                    return None
                out.append(" ")
                i = j
                continue
        out.append(ch)
        i += 1
    return "".join(out).strip() if qs.balanced else None


def _has_active_expansion(segment: str) -> bool:
    qs = _QuoteState()
    return any(not qs.step(ch) and not qs.in_single and not qs.escaped and ch in ("$", "`") for ch in segment) or not qs.balanced


def _resolve_trusted_executable(raw_exe: str) -> str | None:
    """Accept only bare command names or binaries in trusted system directories."""
    if not raw_exe or "\x00" in raw_exe or "\\" in raw_exe or "$" in raw_exe or "`" in raw_exe:
        return None
    if "/" not in raw_exe:
        return raw_exe
    if _has_traversal(raw_exe):
        return None
    norm = _norm_posix(raw_exe)
    return posixpath.basename(norm) if posixpath.dirname(norm) in _TRUSTED_BIN_DIRS else None


def _check_git_tokens(args: list[str]) -> bool:
    idx = 0
    while idx < len(args):
        tok = args[idx]
        if tok == "-c" or tok.startswith("-c") or tok == "--config-env" or tok.startswith("--config-env="):
            return False
        if tok in ("-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"):
            idx += 2
        elif tok.startswith("-"):
            idx += 1
        else:
            break
    if idx >= len(args):
        return False
    sub, rest = args[idx], args[idx + 1 :]
    if any(item == "--output" or item.startswith("--output=") for item in rest):
        return False
    if sub in _READONLY_GIT_SUBCOMMANDS:
        return True
    if sub == "branch":
        for pos, item in enumerate(rest):
            if item in _GIT_BRANCH_MUTATING_FLAGS or item.startswith("--set-upstream"):
                return False
            if not item.startswith("-") and item not in _GIT_BRANCH_READONLY_FLAGS:
                if (rest[pos - 1] if pos > 0 else "") not in ("--contains", "--no-contains", "--merged", "--no-merged", "--points-at"):
                    return False
        return True
    if sub == "worktree":
        return bool(rest) and rest[0] == "list"
    if sub == "stash":
        return bool(rest) and rest[0] in ("list", "show")
    if sub == "remote":
        return not rest or rest[0] in ("-v", "--verbose", "show")
    return sub == "config" and any(flag in rest for flag in ("--get", "--get-all", "--list", "-l"))


def _check_gh_tokens(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] == "search":
        return True
    if args[0] == "auth":
        return len(args) >= 2 and args[1] == "status"
    if args[0] != "api":
        return len(args) >= 2 and args[1] in _READONLY_GH_ACTIONS
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
        if (tok.startswith("-X") and tok[2:].upper() != "GET") or (
            tok.startswith("--method=") and tok.split("=", 1)[1].upper() != "GET"
        ):
            return False
        idx += 1
    return True


def _is_trusted_chief_script(raw_script: str, cwd: str | None, env: Mapping[str, str] | None) -> tuple[bool, str]:
    resolved = _resolve_lexical_path(raw_script, cwd=cwd, env=env)
    if resolved is None or _has_unsafe_symlink(resolved):
        return (False, "")
    script_name = posixpath.basename(resolved)
    if script_name not in _ALLOWED_CHIEF_SCRIPTS:
        return (False, "")
    user_roots, brain_roots = _chief_writable_user_roots(env)
    if any(_is_under_dir(resolved, p) for p in user_roots + brain_roots + ["/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp"]):
        return (False, "")
    trusted_dirs = {_TRUSTED_SCRIPTS_DIR}
    cwd_norm = _resolve_valid_cwd(cwd, env)
    if cwd_norm is not None and not _has_unsafe_symlink(cwd_norm):
        trusted_dirs.update({f"{cwd_norm}/skills/chief-of-staff/scripts", f"{cwd_norm}/.agents/skills/chief-of-staff/scripts"})
    return (True, script_name) if posixpath.dirname(resolved) in trusted_dirs else (False, "")


def _validate_chief_script_flags(
    script_name: str, script_args: list[str], cwd: str | None, env: Mapping[str, str] | None
) -> bool:
    guarded = (
        ("--snapshot", "--live-bootstrap-file") if script_name == "briefing_board.py"
        else (("--fleet-config",) if script_name == "setup_init.py" else ())
    )
    idx = 0
    while guarded and idx < len(script_args):
        tok = script_args[idx]
        if tok in guarded:
            if idx + 1 >= len(script_args) or not _allowed_chief_path(script_args[idx + 1], cwd=cwd, env=env):
                return False
            idx += 2
        elif any(tok.startswith(f + "=") for f in guarded):
            if not _allowed_chief_path(tok.split("=", 1)[1], cwd=cwd, env=env):
                return False
            idx += 1
        else:
            idx += 1
    return True


def _check_python_tokens(args: list[str], cwd: str | None, env: Mapping[str, str] | None) -> bool:
    idx = 0
    while idx < len(args):
        tok = args[idx]
        if tok == "-c" or tok.startswith("-c") or tok == "-m":
            return False
        if tok in ("-B", "-E", "-I", "-O", "-s", "-S", "-u", "-v"):
            idx += 1
        elif tok.startswith("-"):
            return False
        else:
            break
    if idx >= len(args):
        return False
    ok, script_name = _is_trusted_chief_script(args[idx], cwd=cwd, env=env)
    return ok and _validate_chief_script_flags(script_name, args[idx + 1 :], cwd=cwd, env=env)


def _check_sed_tokens(args: list[str]) -> bool:
    expect_expr = False
    for item in args:
        if expect_expr:
            expect_expr = False
            if _SED_WRITE_EXEC_RE.search(item):
                return False
        elif item == "--":
            continue
        elif item in ("-i", "--in-place", "-f", "--file") or item.startswith(("--in-place=", "--file=", "-f")):
            return False
        elif item in ("-e", "--expression"):
            expect_expr = True
        elif (item.startswith("-") and not item.startswith("--") and "i" in item[1:]) or (
            not item.startswith("-") and _SED_WRITE_EXEC_RE.search(item)
        ):
            return False
    return not expect_expr


def _check_sort_tokens(args: list[str]) -> bool:
    for item in args:
        if item == "--":
            break
        if item in ("-o", "--output") or item.startswith("--output=") or (
            item.startswith("-") and not item.startswith("--") and "o" in item[1:]
        ):
            return False
    return True


def _check_uniq_tokens(args: list[str]) -> bool:
    positional, idx, after_dd = 0, 0, False
    while idx < len(args):
        tok = args[idx]
        if not after_dd and tok == "--":
            after_dd = True
        elif not after_dd and tok in ("-f", "-s", "-w", "--skip-fields", "--skip-chars", "--check-chars"):
            idx += 1
        elif after_dd or not tok.startswith("-") or tok == "-":
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
    return not any(item in ("-delete", "-fls") or item.startswith(("-exec", "-ok", "-fprint")) for item in args)


_SUBCOMMAND_CHECKERS = {
    "git": _check_git_tokens,
    "gh": _check_gh_tokens,
    "sed": _check_sed_tokens,
    "sort": _check_sort_tokens,
    "uniq": _check_uniq_tokens,
    "rg": _check_rg_tokens,
    "find": _check_find_tokens,
}


def _is_tokens_allowed(
    tokens: list[str], cwd: str | None, env: Mapping[str, str] | None, *, has_expansion: bool = False
) -> bool:
    if not tokens:
        return True
    idx = 0
    while idx < len(tokens) and (_ENV_ASSIGN_RE.match(tokens[idx]) or tokens[idx] in ("env", "command")):
        idx += 1
    if idx >= len(tokens):
        return False
    exe = _resolve_trusted_executable(tokens[idx])
    if exe is None or (has_expansion and exe not in ("echo", "printf")):
        return False
    args = tokens[idx + 1 :]
    if exe == "python" or exe.startswith("python3"):
        return _check_python_tokens(args, cwd=cwd, env=env)
    checker = _SUBCOMMAND_CHECKERS.get(exe)
    return checker(args) if checker is not None else exe in _READONLY_SHELL_COMMANDS


def _is_segment_allowed(segment: str, cwd: str | None, env: Mapping[str, str] | None) -> bool:
    if (clean_seg := _scan_and_strip_redirections(segment, cwd=cwd, env=env)) is None:
        return False
    if not clean_seg:
        return True
    try:
        tokens = shlex.split(clean_seg)
    except ValueError:
        return False
    return _is_tokens_allowed(tokens, cwd=cwd, env=env, has_expansion=_has_active_expansion(clean_seg))


def _is_command_allowed(command: str, cwd: str | None, env: Mapping[str, str] | None) -> bool:
    if not isinstance(command, str) or not command.strip():
        return False
    ok_subs, inner_cmds = _extract_substitutions(command)
    if not ok_subs or any(not _is_command_allowed(inner, cwd=cwd, env=env) for inner in inner_cmds):
        return False
    segments = _split_shell_segments(command)
    return bool(segments) and all(_is_segment_allowed(seg, cwd=cwd, env=env) for seg in segments)


def _format_decision(is_agy: bool, allowed: bool, reason: str = REASON) -> tuple[int, str]:
    if is_agy:
        return (0, json.dumps({"decision": "allow"} if allowed else {"decision": "deny", "reason": reason}))
    return (0, "") if allowed else (2, reason)


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
            payload, is_agy = parsed, "toolCall" in parsed

    if role != _CHIEF_ROLE:
        return _format_decision(is_agy, True)
    if payload is None:
        return (2, REASON)

    cwd = val if isinstance((val := payload.get("cwd")), str) and val.strip() else None
    if is_agy:
        if not isinstance((tc := payload.get("toolCall")), Mapping):
            return _format_decision(True, False)
        tool_name, raw_args = str(tc.get("name") or ""), tc.get("args")
    else:
        tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
        raw_args = payload.get("tool_input") or payload.get("toolInput")
    tool_args: Mapping[str, Any] = raw_args if isinstance(raw_args, Mapping) else {}

    if not tool_name or tool_name in _DENIED_TOOLS:
        return _format_decision(is_agy, False)
    if tool_name in _WRITE_TOOLS:
        targets = _extract_target_paths(tool_args)
        return _format_decision(is_agy, bool(targets) and all(_allowed_chief_path(t, cwd=cwd, env=source_env) for t in targets))
    if tool_name in _SHELL_TOOLS:
        for list_key in ("argv", "command"):
            if isinstance((raw_list := tool_args.get(list_key)), list):
                ok = bool(raw_list) and all(isinstance(x, str) and x != "" for x in raw_list)
                return _format_decision(is_agy, ok and _is_tokens_allowed(list(raw_list), cwd=cwd, env=source_env))
        command = next((str(tool_args[k]) for k in _COMMAND_KEYS if isinstance(tool_args.get(k), str) and tool_args[k].strip()), "")
        return _format_decision(is_agy, _is_command_allowed(command, cwd=cwd, env=source_env))
    return _format_decision(is_agy, True)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint reading PreToolUse JSON from stdin."""
    _ = argv
    code, output = evaluate(sys.stdin.read())
    if output:
        (sys.stdout if code == 0 else sys.stderr).write(output + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
