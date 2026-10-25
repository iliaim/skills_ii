from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "inspect_jsonl.py"
spec = importlib.util.spec_from_file_location("inspect_jsonl", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = inspector
spec.loader.exec_module(inspector)


def run(path: Path, **kwargs):
    return inspector.inspect(path, **kwargs)


def test_output_contains_only_allowlisted_metadata(tmp_path):
    source = tmp_path / "private-session.jsonl"
    source.write_text(json.dumps({
        "type": "SECRET_AS_TYPE",
        "method": "token_value_method",
        "message": {"role": "PERSONALITY_SECRET_ROLE", "content": [{"type": "secret block label", "text": "TRANSCRIPT SECRET"}]},
        "private-id": "PRIVATE_ID_VALUE",
    }) + "\n")
    result = run(source)
    encoded = json.dumps(result)
    for secret in ("SECRET_AS_TYPE", "token_value_method", "PERSONALITY_SECRET_ROLE", "secret block label", "TRANSCRIPT SECRET", "PRIVATE_ID_VALUE", str(source)):
        assert secret not in encoded
    assert result["backend"] == "unknown"
    assert result["categories"]["outer_types"] == {"other": 1}


def test_blanks_count_against_physical_line_cap_and_bytes(tmp_path):
    source = tmp_path / "sample.jsonl"
    source.write_bytes(b"\n  \n{\"type\":\"message\"}\n")
    result = run(source, max_records=2)
    scan = result["scan"]
    assert scan["physical_lines"] == 2
    assert scan["bytes"] == 4
    assert scan["blank_lines"] == 2
    assert scan["stopped_reason"] == "max_records"
    assert scan["complete"] is False


def test_record_cap_at_stable_eof_is_complete(tmp_path):
    source = tmp_path / "one-record.jsonl"
    source.write_text("{}\n")
    scan = run(source, max_records=1)["scan"]
    assert scan["physical_lines"] == 1
    assert scan["stopped_reason"] == "eof"
    assert scan["complete"]
    assert scan["stable"]


def test_codex_and_claude_vocabulary_is_counted_without_absent_fields(tmp_path):
    codex = tmp_path / "codex.jsonl"
    codex.write_text(json.dumps({"type": "event_msg", "payload": {"type": "task_started"}}) + "\n")
    codex.write_text(codex.read_text() + json.dumps({"type": "response_item", "payload": {"type": "user_message", "content": [{"type": "input_text"}]}}) + "\n")
    codex.write_text(codex.read_text() + json.dumps({"type": "session_meta"}) + "\n")
    codex.write_text(codex.read_text() + json.dumps({"message": {"content": [{"text": "content without a type"}]}}) + "\n")
    codex_categories = run(codex, backend="codex")["categories"]
    assert codex_categories["outer_types"] == {"event_msg": 1, "response_item": 1, "session_meta": 1}
    assert codex_categories["payload_types"] == {"task_started": 1, "user_message": 1}
    assert codex_categories["block_types"] == {"input_text": 1}
    assert "roles" not in codex_categories

    claude = tmp_path / "claude.jsonl"
    claude.write_text(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text"}]}}) + "\n")
    claude_categories = run(claude, backend="claude")["categories"]
    assert claude_categories["outer_types"] == {"assistant": 1}
    assert claude_categories["roles"] == {"assistant": 1}
    assert claude_categories["block_types"] == {"text": 1}


def test_huge_line_drain_stops_at_total_budget(tmp_path):
    source = tmp_path / "huge.jsonl"
    source.write_bytes(b"x" * 100_000 + b"\n{}\n")
    result = run(source, max_line_bytes=64, max_total_bytes=1024)
    scan = result["scan"]
    assert scan["bytes"] == 1024
    assert scan["oversized_count"] == 1
    assert scan["oversized_positions"] == [{"line": 1, "byte": 1}]
    assert scan["stopped_reason"] == "max_total_bytes"
    assert not scan["complete"]


def test_exact_byte_cap_at_eof_is_complete(tmp_path):
    source = tmp_path / "exact.jsonl"
    source.write_bytes(b'{"type":"message"}\n')
    result = run(source, max_total_bytes=source.stat().st_size)
    assert result["scan"]["bytes"] == source.stat().st_size
    assert result["scan"]["complete"]
    assert result["scan"]["stable"]
    assert result["scan"]["stopped_reason"] == "eof"


@pytest.mark.parametrize("data", [b"{bad}\n", b"\xff\n", b"[]\n", b"[" * 5000 + b"]\n"])
def test_malformed_utf8_nonobject_and_deep_json_are_parse_gaps(tmp_path, data):
    source = tmp_path / "bad.jsonl"
    source.write_bytes(data)
    result = run(source)
    scan = result["scan"]
    assert scan["malformed_count"] == 1
    assert scan["malformed_positions"] == [{"line": 1, "byte": 1}]
    assert not scan["complete"]
    assert scan["stopped_reason"] == "parse_gaps"
    assert scan["parsed_records"] == 0


def test_stable_malformed_final_line_is_not_called_truncated(tmp_path):
    source = tmp_path / "tail.jsonl"
    source.write_bytes(b"{}\n{bad")
    scan = run(source)["scan"]
    assert scan["malformed_count"] == 1
    assert scan["malformed_positions"] == [{"line": 2, "byte": 4}]
    assert not scan["complete"]
    assert scan["stopped_reason"] == "parse_gaps"


def test_positions_are_capped(tmp_path):
    source = tmp_path / "many.jsonl"
    source.write_bytes(b"{bad}\n" * 25)
    positions = run(source)["scan"]["malformed_positions"]
    assert len(positions) == 20


@pytest.mark.parametrize("target", ["file", "parent"])
def test_symlink_components_are_rejected(tmp_path, target):
    realdir = tmp_path / "real"
    realdir.mkdir()
    source = realdir / "data.jsonl"
    source.write_text("{}\n")
    if target == "file":
        selected = tmp_path / "link.jsonl"
        selected.symlink_to(source)
    else:
        selected_dir = tmp_path / "linked"
        selected_dir.symlink_to(realdir, target_is_directory=True)
        selected = selected_dir / "data.jsonl"
    with pytest.raises(inspector.UnsafeInput):
        run(selected)


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_non_regular_files_are_rejected_without_blocking(tmp_path, kind):
    path = tmp_path / "nonregular"
    if kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    with pytest.raises(inspector.UnsafeInput):
        run(path)


def test_parent_traversal_cannot_hide_a_symlink_and_select_another_file(tmp_path):
    selected_dir = tmp_path / "selected"
    other_dir = tmp_path / "other" / "nested"
    selected_dir.mkdir()
    other_dir.mkdir(parents=True)
    (selected_dir / "target.jsonl").write_text('{"type":"assistant"}\n')
    (other_dir.parent / "target.jsonl").write_text('{"type":"user"}\n')
    (selected_dir / "link").symlink_to(other_dir, target_is_directory=True)
    supplied = selected_dir / "link" / ".." / "target.jsonl"
    # The chosen source and a lexical normalization have different content.
    assert supplied.read_text() != (selected_dir / "target.jsonl").read_text()
    with pytest.raises(inspector.UnsafeInput):
        run(supplied)


@pytest.mark.parametrize("mutation", ["append", "replace"])
def test_path_change_during_scan_marks_snapshot_unstable(tmp_path, monkeypatch, mutation):
    source = tmp_path / "data.jsonl"
    source.write_text("{}\n")
    real_stat = inspector.os.stat
    checked = 0

    def mocked_stat(path, *args, **kwargs):
        nonlocal checked
        result = real_stat(path, *args, **kwargs)
        if os.fspath(path) == os.fspath(source) and kwargs.get("follow_symlinks") is False:
            checked += 1
        if os.fspath(path) == os.fspath(source) and kwargs.get("follow_symlinks") is False and checked == 1:
            if mutation == "append":
                source.write_text("{}\n{}\n")
            else:
                replacement = tmp_path / "replacement"
                replacement.write_text("{}\n")
                replacement.replace(source)
            result = real_stat(path, *args, **kwargs)
        return result

    monkeypatch.setattr(inspector.os, "stat", mocked_stat)
    scan = run(source)["scan"]
    assert not scan["stable"]
    assert not scan["complete"]


def test_cli_invalid_path_does_not_disclose_path_or_os_error(tmp_path):
    missing = tmp_path / "SECRET_PATH_COMPONENT"
    proc = subprocess.run([sys.executable, str(SCRIPT), str(missing)], capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert json.loads(proc.stderr) == {"error": "invalid or unsafe input"}
    assert str(missing) not in proc.stderr


def test_invalid_limits_are_rejected_by_cli_without_source_echo(tmp_path):
    source = tmp_path / "private.jsonl"
    source.write_text("{}\n")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(source), "--max-records", "0"], capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert str(source) not in proc.stderr


def test_inspection_does_not_mutate_source(tmp_path):
    source = tmp_path / "read-only.jsonl"
    content = b'{"type":"message"}\n'
    source.write_bytes(content)
    before = source.stat()
    run(source)
    after = source.stat()
    assert source.read_bytes() == content
    assert (before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
