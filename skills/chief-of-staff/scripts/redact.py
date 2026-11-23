#!/usr/bin/env python3
"""ReDoS-safe pre-JSON secret redactor and O_NOFOLLOW atomic file writer."""
from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import sys
from pathlib import Path
from typing import Any

HTTP_HEADER_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "cf-access-jwt-assertion",
        "x-api-key",
    }
)

SENSITIVE_KEYS: frozenset[str] = HTTP_HEADER_KEYS | frozenset(
    {
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "id_token",
        "api_key",
        "apikey",
        "client_secret",
        "password",
        "secret",
        "token",
    }
)

_HTTP_HEADER_ALT = "|".join(re.escape(key) for key in sorted(HTTP_HEADER_KEYS, key=len, reverse=True))
_INLINE_JSON_KEYS_ALT = "|".join(re.escape(key) for key in sorted(SENSITIVE_KEYS, key=len, reverse=True))

RULES: tuple[tuple[tuple[str, ...], re.Pattern[str], str], ...] = (
    (
        ("gh", "github_pat_"),
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "[REDACTED_GH_TOKEN]",
    ),
    (
        ("sk-",),
        re.compile(r"\bsk-(?:(?:proj|svcacct|admin|ant-[a-z0-9]+)-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        ("akia",),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        ("aiza",),
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "[REDACTED_GOOGLE_KEY]",
    ),
    (
        ("ya29.",),
        re.compile(r"\bya29\.[0-9A-Za-z_.-]{16,}\b"),
        "[REDACTED_OAUTH_TOKEN]",
    ),
    (
        tuple(sorted(HTTP_HEADER_KEYS)),
        re.compile(rf"(?i)\b({_HTTP_HEADER_ALT})[ \t]*:[ \t]*[^\r\n]+"),
        r"\1: [REDACTED]",
    ),
    (
        ("bearer",),
        re.compile(r"(?i)\bbearer[ \t]+[A-Za-z0-9._~+/=-]{8,}"),
        "Bearer [REDACTED]",
    ),
    (
        ("://",),
        re.compile(
            r"(?<![a-zA-Z0-9+.-])([a-zA-Z][a-zA-Z0-9+.-]{0,31}://[^/\s:@\"']{0,256}:)[^@\s/\"']{1,1024}(@)"
        ),
        r"\1[REDACTED]\2",
    ),
)

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (pattern, replacement) for _, pattern, replacement in RULES
)

_DARWIN_SYSTEM_SYMLINKS = frozenset({Path("/tmp"), Path("/var"), Path("/etc")})


def _protected_root_dirs() -> frozenset[Path]:
    roots = {
        Path("/"),
        Path("/tmp"),
        Path("/var"),
        Path("/etc"),
        Path("/private"),
        Path("/private/tmp"),
        Path("/private/var"),
        Path("/private/etc"),
        Path("/Users"),
        Path("/home"),
    }
    home = Path.home()
    roots.add(Path(os.path.abspath(os.fspath(home))))
    try:
        roots.add(home.resolve())
    except OSError:
        pass
    return frozenset(roots)


_PEM_HEADER_RE = re.compile(r"-----BEGIN [A-Z0-9 ]{0,32}PRIVATE KEY-----")
_PEM_BODY_CHARS_RE = re.compile(r"[A-Za-z0-9+/=\r\n \t:,-]*")
_PEM_FOOTER_RE = re.compile(r"-----END [A-Z0-9 ]{0,32}PRIVATE KEY-----")
_PEM_MAX_BODY_CHARS = 16384
_INLINE_JSON_KEY_RE = re.compile(rf'(?i)("(?:{_INLINE_JSON_KEYS_ALT})"\s*:\s*)"')
_INLINE_JSON_MAX_CHARS = 16384


def _scrub_pem_blocks(text: str) -> str:
    """Redact bounded PEM private key blocks in linear C-speed time without lookahead per byte."""
    if "-----BEGIN " not in text:
        return text
    parts: list[str] = []
    pos = 0
    length = len(text)
    while pos < length:
        hdr = _PEM_HEADER_RE.search(text, pos)
        if hdr is None:
            parts.append(text[pos:])
            break
        parts.append(text[pos:hdr.start()])
        body_start = hdr.end()
        stop = min(length, body_start + _PEM_MAX_BODY_CHARS)
        next_begin = text.find("-----BEGIN ", body_start, stop)
        if next_begin != -1:
            stop = next_begin
        next_end = text.find("-----END ", body_start, stop)
        if next_end != -1:
            stop = next_end
        body_end = body_start
        while body_end < stop:
            body_match = _PEM_BODY_CHARS_RE.match(text, body_end, stop)
            if body_match is not None:
                body_end = body_match.end()
            if body_end + 1 < stop and text[body_end] == "\\" and text[body_end + 1] in ("r", "n"):
                body_end += 2
            else:
                break
        footer_match = _PEM_FOOTER_RE.match(text, body_end)
        full_end = footer_match.end() if footer_match is not None else body_end
        parts.append("[REDACTED_PRIVATE_KEY]")
        pos = full_end
    return "".join(parts)


def _scrub_inline_json(text: str) -> str:
    """Redact bounded inline JSON string secret values in linear time without regex backtracking."""
    if '"' not in text:
        return text
    parts: list[str] = []
    pos = 0
    length = len(text)
    while pos < length:
        match = _INLINE_JSON_KEY_RE.search(text, pos)
        if match is None:
            parts.append(text[pos:])
            break
        parts.append(text[pos:match.end()])
        scan = match.end()
        limit = min(length, scan + _INLINE_JSON_MAX_CHARS)
        close_idx = -1
        while scan < limit:
            quote_idx = text.find('"', scan, limit)
            if quote_idx == -1:
                break
            backslashes = 0
            check = quote_idx - 1
            while check >= match.end() and text[check] == "\\":
                backslashes += 1
                check -= 1
            if backslashes % 2 == 0:
                close_idx = quote_idx
                break
            scan = quote_idx + 1
        if close_idx != -1:
            parts.append('[REDACTED]"')
            pos = close_idx + 1
        else:
            pos = match.end()
    return "".join(parts)


def scrub_secrets(text: str) -> str:
    """Redact known credential patterns from plain text in bounded time."""
    if not text:
        return text
    result = _scrub_pem_blocks(text)
    lowered = result.lower()
    for needles, pattern, replacement in RULES:
        if not needles or any(needle in lowered for needle in needles):
            result, count = pattern.subn(replacement, result)
            if count:
                lowered = result.lower()
    return _scrub_inline_json(result)


def scrub_data(value: Any) -> Any:
    """Recursively redact sensitive dict keys and inline secret strings before JSON serialization."""
    if isinstance(value, str):
        return scrub_secrets(value)
    if isinstance(value, dict):
        scrubbed: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.strip().lower() in SENSITIVE_KEYS:
                scrubbed[key] = None if item is None else "[REDACTED]"
            else:
                new_key = scrub_secrets(key) if isinstance(key, str) else key
                scrubbed[new_key] = scrub_data(item)
        return scrubbed
    if isinstance(value, list):
        return [scrub_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_data(item) for item in value)
    return value


def _absolute_lexical_path(path: Path) -> Path:
    if ".." in path.parts:
        raise ValueError(f"Refusing parent traversal '..' in path: {path}")
    return Path(os.path.abspath(os.fspath(path)))


def ensure_directory_no_symlinks(directory: Path, *, mode: int = 0o700, chmod_existing: bool = True) -> Path:
    """Create directory without traversing symlinks; optionally enforce mode on owned non-system dirs."""
    abs_dir = _absolute_lexical_path(directory)
    protected = _protected_root_dirs()
    uid = os.geteuid()

    ancestors = list(reversed(abs_dir.parents)) + [abs_dir]
    for current in ancestors:
        if current.is_symlink():
            if (
                current != abs_dir
                and sys.platform == "darwin"
                and current in _DARWIN_SYSTEM_SYMLINKS
                and os.lstat(current).st_uid == 0
            ):
                continue
            kind = "directory" if current == abs_dir else "ancestor directory"
            raise ValueError(f"Refusing symlink {kind}: {current}")
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, mode)
            if current.is_symlink():
                raise ValueError(f"Refusing symlink created at: {current}")
            os.chmod(current, mode)
            continue
        if not stat.S_ISDIR(st.st_mode):
            raise ValueError(f"Expected directory at {current}")
        if chmod_existing and current == abs_dir and st.st_uid == uid and current not in protected:
            os.chmod(current, mode)
    return abs_dir


def ensure_private_dir(directory: Path) -> None:
    """Ensure directory exists with 0700 permissions and no symlinked target or ancestors."""
    ensure_directory_no_symlinks(directory, mode=0o700, chmod_existing=True)


def safe_atomic_write(
    path: Path,
    data: str,
    *,
    file_mode: int = 0o600,
    dir_mode: int = 0o700,
    chmod_existing_dir: bool = True,
) -> None:
    """Atomically write text to a regular file via O_CREAT|O_EXCL|O_NOFOLLOW temp + os.replace."""
    abs_path = _absolute_lexical_path(path)
    if abs_path.is_symlink():
        raise ValueError(f"Refusing symlink target: {abs_path}")

    parent = ensure_directory_no_symlinks(
        abs_path.parent,
        mode=dir_mode,
        chmod_existing=chmod_existing_dir,
    )

    if abs_path.is_symlink():
        raise ValueError(f"Refusing symlink target: {abs_path}")
    try:
        existing_st = os.lstat(abs_path)
    except FileNotFoundError:
        existing_st = None
    if existing_st is not None and not stat.S_ISREG(existing_st.st_mode):
        raise ValueError(f"Refusing non-regular target file: {abs_path}")

    open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    tmp_path: Path | None = None
    for _ in range(16):
        candidate = parent / f".{abs_path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(candidate, open_flags, file_mode)
            tmp_path = candidate
            break
        except FileExistsError:
            continue
    if fd is None or tmp_path is None:
        raise OSError(f"Failed to allocate unique temporary file in {parent}")

    payload = data.encode("utf-8")
    try:
        os.fchmod(fd, file_mode)
        view = memoryview(payload)
        written = 0
        while written < len(payload):
            written += os.write(fd, view[written:])
        os.fsync(fd)
        os.close(fd)
        fd = None

        if abs_path.is_symlink() or parent.is_symlink() or tmp_path.is_symlink():
            raise ValueError(f"Refusing symlink during atomic replace: {abs_path}")
        os.replace(tmp_path, abs_path)
        tmp_path = None
        try:
            dir_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def safe_atomic_write_0600(path: Path, data: str) -> None:
    """Atomically write data to path with 0700 parent directory and 0600 file mode."""
    safe_atomic_write(path, data, file_mode=0o600, dir_mode=0o700, chmod_existing_dir=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrub secrets from stdin and write to stdout.")
    parser.parse_args(argv)
    sys.stdout.write(scrub_secrets(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
