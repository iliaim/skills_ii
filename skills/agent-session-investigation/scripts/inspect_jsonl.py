#!/usr/bin/env python3
"""Bounded, metadata-only inspection of one explicitly selected JSONL file.

Inspired by the Hermes agent-session-forensics skill. This small independent
reimplementation emits only allowlisted structural categories and bounded
scan metadata, never source content or paths.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import stat
import sys
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO

DEFAULT_MAX_RECORDS = 10_000
DEFAULT_MAX_LINE_BYTES = 1_000_000
DEFAULT_MAX_TOTAL_BYTES = 16_000_000
POSITION_LIMIT = 20

# Deliberately finite vocabularies. Source-provided labels outside these sets
# collapse to "other" and are never copied into output. These include the
# observed Codex JSONL event vocabulary and common Claude message/block types.
CATEGORY_FIELDS = {
    "outer_types": ("type", frozenset({"message", "response", "event", "session", "snapshot", "progress", "user", "assistant", "session_meta", "response_item", "event_msg", "turn_context", "compacted"})),
    "payload_types": ("type", frozenset({"message", "tool_use", "tool_result", "text", "thinking", "image", "audio", "task_started", "task_complete", "task_completed", "user_message", "agent_message", "function_call", "function_call_output", "reasoning", "other"})),
    "roles": ("role", frozenset({"user", "assistant", "system", "developer", "tool"})),
    "block_types": ("type", frozenset({"text", "input_text", "output_text", "tool_use", "tool_result", "thinking", "image", "audio", "input_audio", "output_audio", "input_json", "other"})),
    "methods": ("method", frozenset({"update", "snapshot", "message", "session", "tool_call", "tool_result", "other"})),
}


class UnsafeInput(ValueError):
    """Input cannot be safely inspected under the file contract."""


class _BudgetedFile(io.FileIO):
    """Cap raw reads before buffering, including BufferedReader read-ahead."""

    def __init__(self, fd: int, budget: int):
        self.remaining = budget
        super().__init__(fd, mode="rb")

    def readinto(self, buffer):
        count = super().readinto(memoryview(buffer)[:self.remaining])
        self.remaining -= count or 0
        return count


def _positive_limit(value: str) -> int:
    try:
        parsed = int(value, 10)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("must be a positive finite integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite integer")
    return parsed


def _absolute_path(path: Path) -> Path:
    """Return an absolute lexical path without resolving symlinks."""
    # Collapsing symlink/.. can silently select a different file before the
    # no-follow walk sees that symlink. Refuse ambiguous traversal instead.
    if ".." in path.parts:
        raise UnsafeInput("input is unavailable or unsafe")
    absolute = Path(os.path.abspath(os.fspath(path)))
    return absolute


def _open_regular(path: Path, byte_budget: int) -> tuple[BinaryIO, os.stat_result, Path, int, str]:
    """Open via no-follow directory descriptors so parent swaps cannot redirect it."""
    absolute = _absolute_path(path)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(absolute.anchor, directory_flags)
    file_fd: int | None = None
    try:
        for component in absolute.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(absolute.name, file_flags, dir_fd=directory_fd)
        descriptor_stat = os.fstat(file_fd)
        path_stat = os.stat(absolute.name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(descriptor_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
            raise UnsafeInput("input is unavailable or unsafe")
        if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
            raise UnsafeInput("input is unavailable or unsafe")
        raw = _BudgetedFile(file_fd, byte_budget)
        try:
            handle = io.BufferedReader(raw)
        except Exception:
            raw.close()
            file_fd = None
            raise
        file_fd = None
        return handle, descriptor_stat, absolute, directory_fd, absolute.name
    except Exception as exc:
        try:
            if file_fd is not None:
                os.close(file_fd)
        except OSError:
            pass
        os.close(directory_fd)
        if isinstance(exc, OSError):
            raise UnsafeInput("input is unavailable or unsafe") from None
        raise


def _stable(before_fd: os.stat_result, after_fd: os.stat_result, path: Path, parent_fd: int, name: str) -> bool:
    try:
        # Check the current lexical route for symlink components, then compare
        # both that route and the originally opened parent directory entry.
        cursor = Path(path.anchor)
        for component in path.parts[1:]:
            cursor = cursor / component
            if stat.S_ISLNK(os.lstat(cursor).st_mode):
                return False
        after_path = os.stat(path, follow_symlinks=False)
        after_entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return False
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(before_fd, field) == getattr(after_fd, field) == getattr(after_path, field) == getattr(after_entry, field) for field in fields)


def _add_category(counts: dict[str, Counter[str]], bucket: str, value: Any) -> None:
    _, allowed = CATEGORY_FIELDS[bucket]
    label = value if isinstance(value, str) and value in allowed else "other"
    counts[bucket][label] += 1


def _block_types(value: Any, counts: dict[str, Counter[str]]) -> None:
    if isinstance(value, list):
        for block in value:
            if isinstance(block, dict) and "type" in block:
                _add_category(counts, "block_types", block["type"])


def _classify(obj: dict[str, Any], counts: dict[str, Counter[str]]) -> None:
    if "type" in obj:
        _add_category(counts, "outer_types", obj["type"])
    if "method" in obj:
        _add_category(counts, "methods", obj["method"])
    for container_key in ("message", "payload"):
        nested = obj.get(container_key)
        if isinstance(nested, dict):
            if "role" in nested:
                _add_category(counts, "roles", nested["role"])
            if container_key == "payload":
                if "type" in nested:
                    _add_category(counts, "payload_types", nested["type"])
            _block_types(nested.get("content"), counts)
    _block_types(obj.get("content"), counts)


def inspect(
    path: str | os.PathLike[str],
    backend: str = "unknown",
    max_records: int = DEFAULT_MAX_RECORDS,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Inspect one selected file and return a bounded, non-identifying summary."""
    if backend not in {"codex", "claude", "unknown"}:
        raise ValueError("backend must be codex, claude, or unknown")
    if any(type(value) is not int or value <= 0 for value in (max_records, max_line_bytes, max_total_bytes)):
        raise ValueError("limits must be positive finite integers")

    counts = {name: Counter() for name in CATEGORY_FIELDS}
    malformed_positions: list[dict[str, int]] = []
    oversized_positions: list[dict[str, int]] = []
    physical_lines = bytes_scanned = parsed = blank = malformed = oversized = 0
    stopped_reason = "eof"
    complete = False
    after_fd: os.stat_result | None = None

    handle, before_fd, absolute, parent_fd, basename = _open_regular(Path(path), max_total_bytes)
    try:
        with handle:
            while True:
                if physical_lines >= max_records:
                    stopped_reason = "max_records"
                    break
                remaining = max_total_bytes - bytes_scanned
                if remaining == 0:
                    # The initial size is only advisory; final descriptor/path
                    # checks decide whether this was truly EOF or truncation.
                    if bytes_scanned >= before_fd.st_size:
                        complete = True
                        stopped_reason = "eof"
                    else:
                        stopped_reason = "max_total_bytes"
                    break

                line_start = bytes_scanned + 1
                raw = handle.readline(min(max_line_bytes + 1, remaining))
                if not raw:
                    complete = True
                    stopped_reason = "eof"
                    break
                physical_lines += 1
                bytes_scanned += len(raw)
                line_over = len(raw) > max_line_bytes

                # If the bounded read stopped before newline, drain this same
                # physical line in small chunks, consuming the total budget.
                newline_seen = raw.endswith(b"\n")
                if line_over and not newline_seen:
                    while not newline_seen and bytes_scanned < max_total_bytes:
                        part = handle.readline(min(65_536, max_total_bytes - bytes_scanned))
                        if not part:
                            break
                        bytes_scanned += len(part)
                        newline_seen = part.endswith(b"\n")

                if line_over:
                    oversized += 1
                    if len(oversized_positions) < POSITION_LIMIT:
                        oversized_positions.append({"line": physical_lines, "byte": line_start})
                    if not newline_seen:
                        stopped_reason = "max_total_bytes" if bytes_scanned >= max_total_bytes else "truncated_line"
                        break
                    continue

                if not newline_seen and bytes_scanned >= max_total_bytes and bytes_scanned < before_fd.st_size:
                    stopped_reason = "max_total_bytes"
                    break

                if not raw.strip():
                    blank += 1
                    continue
                try:
                    obj = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError, RecursionError, ValueError):
                    malformed += 1
                    if len(malformed_positions) < POSITION_LIMIT:
                        malformed_positions.append({"line": physical_lines, "byte": line_start})
                    continue
                if not isinstance(obj, dict):
                    malformed += 1
                    if len(malformed_positions) < POSITION_LIMIT:
                        malformed_positions.append({"line": physical_lines, "byte": line_start})
                    continue
                parsed += 1
                _classify(obj, counts)

                if bytes_scanned >= max_total_bytes:
                    # A final exact-cap newline can still be complete if stat
                    # confirms that the cap coincides with EOF.
                    stopped_reason = "max_total_bytes"
                    break
            after_fd = os.fstat(handle.fileno())
        stable = after_fd is not None and _stable(before_fd, after_fd, absolute, parent_fd, basename)
    finally:
        try:
            if not handle.closed:
                handle.close()
        finally:
            os.close(parent_fd)
    if stable and not complete and physical_lines >= max_records and bytes_scanned == before_fd.st_size:
        complete = True
        stopped_reason = "eof"
    if stable and not complete and bytes_scanned == before_fd.st_size and stopped_reason in {"max_total_bytes", "truncated_line"}:
        complete = True
        stopped_reason = "eof"
    if stable and complete and (malformed or oversized):
        complete = False
        stopped_reason = "parse_gaps"
    if not stable:
        complete = False

    return {
        "backend": backend,
        "limits": {"max_records": max_records, "max_line_bytes": max_line_bytes, "max_total_bytes": max_total_bytes},
        "scan": {
            "physical_lines": physical_lines,
            "bytes": bytes_scanned,
            "line_range": [1, physical_lines] if physical_lines else [0, 0],
            "byte_range": [1, bytes_scanned] if bytes_scanned else [0, 0],
            "parsed_records": parsed,
            "blank_lines": blank,
            "malformed_count": malformed,
            "malformed_positions": malformed_positions,
            "oversized_count": oversized,
            "oversized_positions": oversized_positions,
            "stopped_reason": stopped_reason,
            "complete": complete,
            "stable": stable,
        },
        "categories": {name: dict(sorted(counter.items())) for name, counter in counts.items() if counter},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="one explicitly selected local JSONL file")
    parser.add_argument("--backend", choices=("codex", "claude", "unknown"), default="unknown")
    parser.add_argument("--max-records", type=_positive_limit, default=DEFAULT_MAX_RECORDS)
    parser.add_argument("--max-line-bytes", type=_positive_limit, default=DEFAULT_MAX_LINE_BYTES)
    parser.add_argument("--max-total-bytes", type=_positive_limit, default=DEFAULT_MAX_TOTAL_BYTES)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.path, args.backend, args.max_records, args.max_line_bytes, args.max_total_bytes)
    except (OSError, ValueError, RecursionError):
        print(json.dumps({"error": "invalid or unsafe input"}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
