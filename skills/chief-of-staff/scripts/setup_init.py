#!/usr/bin/env python3
"""Symlink-safe /setup initializer for .agents/orchestration.json and user fleet.json."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Sequence

_REDACT_PATH = Path(__file__).resolve().with_name("redact.py")
_REDACT_SPEC = importlib.util.spec_from_file_location("chief_of_staff_redact", _REDACT_PATH)
if _REDACT_SPEC is None or _REDACT_SPEC.loader is None:
    raise ImportError(f"Unable to load redact module from {_REDACT_PATH}")
_redact = importlib.util.module_from_spec(_REDACT_SPEC)
sys.modules[_REDACT_SPEC.name] = _redact
_REDACT_SPEC.loader.exec_module(_redact)

PROVIDER_NAMES: tuple[str, ...] = ("codex", "claude", "agy")
DEFAULT_WORKER_CAPS: dict[str, int] = {
    "codex": 3,
    "claude": 2,
    "agy": 2,
}


def default_fleet_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else (Path.home() / ".config")
    return base / "chief-of-staff" / "fleet.json"


def _default_extra_bin_dirs() -> list[Path]:
    return [
        Path.home() / ".local" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]


def detect_providers(extra_bin_dirs: Sequence[Path] | None = None) -> dict[str, dict[str, Any]]:
    """Detect installed provider CLIs across PATH + extra_bin_dirs, recording only installed/basename."""
    raw_path = os.environ.get("PATH", "")
    search_dirs: list[str] = [entry for entry in raw_path.split(os.pathsep) if entry]
    extras = _default_extra_bin_dirs() if extra_bin_dirs is None else list(extra_bin_dirs)
    seen = set(search_dirs)
    for directory in extras:
        text = os.fspath(directory)
        if text and text not in seen:
            search_dirs.append(text)
            seen.add(text)
    search_path = os.pathsep.join(search_dirs)

    detected: dict[str, dict[str, Any]] = {}
    for name in PROVIDER_NAMES:
        found = shutil.which(name, path=search_path) if search_path else None
        detected[name] = {
            "installed": found is not None,
            "binary": name,
        }
    return detected


def _default_orchestration_config() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "mode": "auto",
        "runtime": {
            "commandPrefix": [],
        },
        "direction": {
            "anchorIssue": None,
        },
        "tracker": {
            "kind": "github",
            "readyCommand": None,
            "claimCommand": None,
            "closeCommand": None,
        },
        "review": {
            "makerChecker": True,
            "policyCommand": None,
            "maxRepairRounds": 3,
        },
        "merge": {
            "strategy": "--merge",
            "matchHeadCommit": True,
            "autoMergeEnvFlag": None,
            "publishCommand": None,
        },
        "overlayPath": ".agents/orchestration-overlay.md",
    }


def _default_fleet_config(detected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    for name in PROVIDER_NAMES:
        info = detected[name]
        providers[name] = {
            "enabled": bool(info["installed"]),
            "binary": info["binary"],
            "workerCap": DEFAULT_WORKER_CAPS[name],
        }
    return {
        "schemaVersion": 1,
        "hosts": {
            "local": {
                "transport": "local",
            }
        },
        "providers": providers,
        "observabilityRemoteSinkCommand": None,
    }


def _deep_merge_defaults(existing: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(existing)
    for key, default_val in defaults.items():
        if key not in merged:
            merged[key] = copy.deepcopy(default_val)
        elif isinstance(default_val, dict) and isinstance(merged[key], dict):
            merged[key] = _deep_merge_defaults(merged[key], default_val)
    return merged


def _validate_command_fields(obj: Any, path_prefix: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{path_prefix}.{key}" if path_prefix else str(key)
            if isinstance(key, str) and (key == "commandPrefix" or key.endswith("Command")):
                if value is not None and not (
                    isinstance(value, list) and all(isinstance(item, str) for item in value)
                ):
                    raise ValueError(
                        f"Field {full_key!r} must be None or a list[str] argv array, got {type(value).__name__}"
                    )
            else:
                _validate_command_fields(value, full_key)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _validate_command_fields(item, f"{path_prefix}[{idx}]")


def _reject_symlink(path: Path, label: str) -> None:
    if ".." in path.parts:
        raise ValueError(f"Refusing parent traversal '..' in {label}: {path}")
    if path.is_symlink():
        raise ValueError(f"Refusing symlink for {label}: {path}")


def _read_existing_json_object(path: Path, label: str) -> dict[str, Any] | None:
    _reject_symlink(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(f"Refusing symlink for {label}: {path}") from exc
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"Expected regular file for {label}: {path}")
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = -1
            raw = handle.read()
    finally:
        if fd != -1:
            os.close(fd)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object in {label}: {path}")
    return parsed


def initialize_setup(
    repo_root: Path,
    fleet_config_path: Path | None = None,
    extra_bin_dirs: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Initialize or non-destructively update repo orchestration.json and private fleet.json."""
    repo_path = Path(os.path.abspath(os.fspath(repo_root)))
    _reject_symlink(repo_root, "repo_root")
    _reject_symlink(repo_path, "repo_root")
    if not repo_path.exists():
        raise ValueError(f"repo_root does not exist: {repo_path}")
    if not stat.S_ISDIR(os.lstat(repo_path).st_mode):
        raise ValueError(f"repo_root is not a directory: {repo_path}")

    agents_dir = repo_path / ".agents"
    orch_path = agents_dir / "orchestration.json"
    _reject_symlink(agents_dir, ".agents")
    _reject_symlink(orch_path, ".agents/orchestration.json")

    raw_fleet = default_fleet_config_path() if fleet_config_path is None else fleet_config_path
    _reject_symlink(raw_fleet.parent, "fleet_config_path.parent")
    _reject_symlink(raw_fleet, "fleet_config_path")
    fleet_path = Path(os.path.abspath(os.fspath(raw_fleet)))
    _reject_symlink(fleet_path.parent, "fleet_config_path.parent")
    _reject_symlink(fleet_path, "fleet_config_path")

    detected = detect_providers(extra_bin_dirs=extra_bin_dirs)

    orch_defaults = _default_orchestration_config()
    existing_orch = _read_existing_json_object(orch_path, ".agents/orchestration.json")
    merged_orch = orch_defaults if existing_orch is None else _deep_merge_defaults(existing_orch, orch_defaults)
    _validate_command_fields(merged_orch, "orchestration")

    fleet_defaults = _default_fleet_config(detected)
    existing_fleet = _read_existing_json_object(fleet_path, "fleet_config_path")
    merged_fleet = fleet_defaults if existing_fleet is None else _deep_merge_defaults(existing_fleet, fleet_defaults)
    _validate_command_fields(merged_fleet, "fleet")

    _redact.safe_atomic_write(
        orch_path,
        json.dumps(merged_orch, indent=2) + "\n",
        file_mode=0o644,
        dir_mode=0o755,
        chmod_existing_dir=False,
    )
    _redact.safe_atomic_write_0600(
        fleet_path,
        json.dumps(merged_fleet, indent=2) + "\n",
    )

    return {
        "status": "ok",
        "repoConfigPath": str(orch_path),
        "fleetConfigPath": str(fleet_path),
        "providers": detected,
        "orchestration": merged_orch,
        "fleet": merged_fleet,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize repo .agents/orchestration.json and private fleet.json."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root directory (defaults to current working directory).",
    )
    parser.add_argument(
        "--fleet-config",
        type=Path,
        default=None,
        help="Path to private fleet.json (defaults to ~/.config/chief-of-staff/fleet.json).",
    )
    args = parser.parse_args(argv)
    summary = initialize_setup(
        repo_root=args.repo_root,
        fleet_config_path=args.fleet_config,
    )
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
