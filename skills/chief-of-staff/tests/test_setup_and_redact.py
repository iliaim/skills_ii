from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_module(name: str, filename: str):
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scrub_data_preserves_valid_json_with_quotes_and_redacts_all_shapes() -> None:
    redact = _load_module("chief_of_staff_redact_test", "redact.py")

    ghs = "ghs_" + ("1" * 25)
    gh_pat = "github_pat_" + ("a" * 25)
    sk_ant = "sk-ant-api03-" + ("a" * 24)
    sk_proj = "sk-proj-" + ("b" * 24)
    sk_generic = "sk-" + ("z" * 24)
    akia = "AKIA" + ("0" * 16)
    aiza = "AIza" + ("B" * 35)
    ya29 = "ya29." + ("c" * 20)
    bearer_val = "tok_" * 4
    db_pass = "p123"
    db_scheme = "post" + "gres://"
    db_url = f"{db_scheme}u:{db_pass}@db/x"
    cookie_val = "sess_" + ("z" * 12)
    set_cookie_val = "sid_" + ("w" * 12)
    x_api_key_val = "xkey_" + ("k" * 12)
    cf_jwt = "jwt_" + ("q" * 20)
    inline_tok = "tokval_" + ("t" * 12)
    pem_line = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA1234\n-----END " + "RSA PRIVATE KEY-----"

    payload = {
        "Cookie": cookie_val,
        "Cf-Access-Jwt-Assertion": cf_jwt,
        "api_key": 'val"with"quotes',
        "safe_slug": "risk-waiver-not-exclusivity",
        "tokens": [ghs, gh_pat, sk_ant, sk_proj, sk_generic, akia, aiza, ya29],
        "nested": {
            "bearer": f"Bearer {bearer_val}",
            "db": db_url,
            "headers": (
                f"Cookie: {cookie_val}\n"
                f"Set-Cookie: {set_cookie_val}\n"
                f"X-Api-Key: {x_api_key_val}\n"
                f"Cf-Access-Jwt-Assertion: {cf_jwt}\n"
                "Authorization: Basic dXNlcjpwYXNz"
            ),
            "inline_json": f'{{"api_key": "val\\"with\\"quotes", "token": "{inline_tok}", "keep": "ok"}}',
            "pem": pem_line,
        },
    }

    scrubbed = redact.scrub_data(payload)
    encoded = json.dumps(scrubbed)
    decoded = json.loads(encoded)

    assert decoded["Cookie"] == "[REDACTED]"
    assert decoded["Cf-Access-Jwt-Assertion"] == "[REDACTED]"
    assert decoded["api_key"] == "[REDACTED]"
    assert decoded["safe_slug"] == "risk-waiver-not-exclusivity"

    for secret in (
        ghs,
        gh_pat,
        sk_ant,
        sk_proj,
        sk_generic,
        akia,
        aiza,
        ya29,
        bearer_val,
        db_pass,
        cookie_val,
        set_cookie_val,
        x_api_key_val,
        cf_jwt,
        inline_tok,
        "dXNlcjpwYXNz",
        'val"with"quotes',
        "MIIEpAIBAAKCAQEA1234",
    ):
        assert secret not in encoded

    assert f"{db_scheme}u:[REDACTED]@db/x" in decoded["nested"]["db"]
    assert "Bearer [REDACTED]" in decoded["nested"]["bearer"]
    assert "Set-Cookie: [REDACTED]" in decoded["nested"]["headers"]
    assert "X-Api-Key: [REDACTED]" in decoded["nested"]["headers"]
    assert "[REDACTED_PRIVATE_KEY]" in decoded["nested"]["pem"]
    inner = json.loads(decoded["nested"]["inline_json"])
    assert inner == {"api_key": "[REDACTED]", "token": "[REDACTED]", "keep": "ok"}

    # Header and Bearer patterns must not cross newlines
    cookie_nl = redact.scrub_secrets("Cookie:\nHost: example.com")
    assert "Host: example.com" in cookie_nl
    bearer_nl = redact.scrub_secrets("Bearer\nNextLineValue")
    assert bearer_nl == "Bearer\nNextLineValue"


def test_truncated_pem_and_redos_bound() -> None:
    redact = _load_module("chief_of_staff_redact_test", "redact.py")

    hdr = "-----BEGIN " + "RSA PRIVATE KEY-----"
    end_hdr = "-----END " + "RSA PRIVATE KEY-----"
    truncated = f"{hdr}\nMIIEpAIBAAKCAQEA1234567890abcdef"
    assert redact.scrub_secrets(truncated) == "[REDACTED_PRIVATE_KEY]"

    escaped_pem_json = '{"stdout": "' + hdr + '\\nMIIEpAIBAAKCAQEA1234\\n' + end_hdr + '"}'
    scrubbed_pem_json = redact.scrub_secrets(escaped_pem_json)
    assert "MIIEpAIBAAKCAQEA1234" not in scrubbed_pem_json
    assert json.loads(scrubbed_pem_json) == {"stdout": "[REDACTED_PRIVATE_KEY]"}

    escaped_crlf_pem_json = '{"stdout": "' + hdr + '\\r\\nMIIEpAIBAAKCAQEA5678\\r\\n' + end_hdr + '"}'
    scrubbed_crlf_json = redact.scrub_secrets(escaped_crlf_pem_json)
    assert "MIIEpAIBAAKCAQEA5678" not in scrubbed_crlf_json
    assert json.loads(scrubbed_crlf_json) == {"stdout": "[REDACTED_PRIVATE_KEY]"}

    big = (hdr + "\n" + ("A" * 1000) + "\n") * 2000
    t0 = time.monotonic()
    result = redact.scrub_secrets(big)
    elapsed = time.monotonic() - t0

    assert elapsed < 0.5, f"scrub_secrets took {elapsed:.3f}s on 2MB PEM input"
    assert "AAAA" not in result
    assert "[REDACTED_PRIVATE_KEY]" in result

    url_run = ("A" * 2_000_000) + " http://localhost:8080/test"
    t1 = time.monotonic()
    url_res = redact.scrub_secrets(url_run)
    url_elapsed = time.monotonic() - t1
    assert url_elapsed < 0.5, f"scrub_secrets took {url_elapsed:.3f}s on 2MB URL run"
    assert url_res.endswith(" http://localhost:8080/test")

    url_at_run = ("A" * 2_000_000) + " http://localhost:8080/test @"
    t2 = time.monotonic()
    url_at_res = redact.scrub_secrets(url_at_run)
    url_at_elapsed = time.monotonic() - t2
    assert url_at_elapsed < 0.5, f"scrub_secrets took {url_at_elapsed:.3f}s on 2MB URL+@ run"
    assert url_at_res.endswith(" http://localhost:8080/test @")

    unclosed_json_run = '"api_key": "' + ("x" * 2_000_000)
    t3 = time.monotonic()
    json_res = redact.scrub_secrets(unclosed_json_run)
    json_elapsed = time.monotonic() - t3
    assert json_elapsed < 0.5, f"scrub_secrets took {json_elapsed:.3f}s on 2MB unclosed JSON run"
    assert json_res == unclosed_json_run


def test_safe_atomic_write_0600_and_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    redact = _load_module("chief_of_staff_redact_test", "redact.py")

    cfg_dir = tmp_path / "private_cfg"
    target = cfg_dir / "fleet.json"
    redact.safe_atomic_write_0600(target, '{"ok": true}\n')

    assert stat.S_IMODE(cfg_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'

    # Atomic overwrite preserves 0600
    redact.safe_atomic_write_0600(target, '{"ok": "updated"}\n')
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text(encoding="utf-8") == '{"ok": "updated"}\n'

    # Refuse symlink target (including dangling)
    real_file = tmp_path / "real.txt"
    real_file.write_text("x", encoding="utf-8")
    sym_target = tmp_path / "sym_target.json"
    sym_target.symlink_to(real_file)
    with pytest.raises(ValueError, match="symlink"):
        redact.safe_atomic_write_0600(sym_target, "{}")

    dangling_target = tmp_path / "dangling_target.json"
    dangling_target.symlink_to(tmp_path / "does_not_exist.json")
    with pytest.raises(ValueError, match="symlink"):
        redact.safe_atomic_write_0600(dangling_target, "{}")

    # Refuse symlinked parent directory
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    sym_dir = tmp_path / "sym_dir"
    sym_dir.symlink_to(real_dir)
    with pytest.raises(ValueError, match="symlink"):
        redact.safe_atomic_write_0600(sym_dir / "child.json", "{}")

    # ensure_private_dir directly: creates 0700 dir and rejects symlink target & symlinked ancestor
    direct_dir = tmp_path / "direct_private" / "nested"
    redact.ensure_private_dir(direct_dir)
    assert stat.S_IMODE(direct_dir.stat().st_mode) == 0o700
    with pytest.raises(ValueError, match="symlink"):
        redact.ensure_private_dir(sym_dir)
    with pytest.raises(ValueError, match="symlink"):
        redact.ensure_private_dir(sym_dir / "sub" / "leaf")

    # CLI scrubs stdin -> stdout
    ghs = "ghs_" + ("9" * 24)
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"token={ghs} slug=risk-waiver-not-exclusivity\n"))
    rc = redact.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert ghs not in out
    assert "[REDACTED_GH_TOKEN]" in out
    assert "risk-waiver-not-exclusivity" in out


def test_setup_init_rejects_symlinks_and_preserves_existing_customizations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_init = _load_module("chief_of_staff_setup_init_test", "setup_init.py")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert setup_init.default_fleet_config_path() == tmp_path / "xdg" / "skills-ii" / "fleet.json"
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert setup_init.default_fleet_config_path() == Path.home() / ".config" / "skills-ii" / "fleet.json"

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    cfg_dir = tmp_path / "user_cfg"
    user_cfg = cfg_dir / "fleet.json"

    # Isolate PATH so detection is deterministic
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    codex_bin = fake_bin / "codex"
    codex_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))

    summary = setup_init.initialize_setup(
        repo_root=repo_dir,
        fleet_config_path=user_cfg,
        extra_bin_dirs=[],
    )
    assert summary["status"] == "ok"

    orch_path = repo_dir / ".agents" / "orchestration.json"
    assert orch_path.is_file()
    assert stat.S_IMODE(orch_path.stat().st_mode) == 0o644
    orch = json.loads(orch_path.read_text(encoding="utf-8"))

    assert orch["schemaVersion"] == 1
    assert orch["mode"] == "auto"
    assert orch["runtime"]["commandPrefix"] == []
    assert isinstance(orch["runtime"]["commandPrefix"], list)
    for cmd_val in (
        orch["tracker"]["readyCommand"],
        orch["tracker"]["claimCommand"],
        orch["tracker"]["closeCommand"],
        orch["review"]["policyCommand"],
        orch["merge"]["publishCommand"],
    ):
        assert cmd_val is None or isinstance(cmd_val, list)
    assert orch["overlayPath"] == ".agents/orchestration-overlay.md"

    assert stat.S_IMODE(cfg_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(user_cfg.stat().st_mode) == 0o600
    fleet = json.loads(user_cfg.read_text(encoding="utf-8"))
    assert fleet["schemaVersion"] == 1
    assert fleet["observabilityRemoteSinkCommand"] is None
    assert set(fleet["providers"]) == {"codex", "claude", "agy"}
    assert fleet["providers"]["codex"]["enabled"] is True
    assert fleet["providers"]["codex"]["binary"] == "codex"
    assert isinstance(fleet["providers"]["codex"]["workerCap"], int)
    assert fleet["providers"]["claude"]["enabled"] is False
    assert fleet["providers"]["claude"]["binary"] == "claude"
    assert fleet["providers"]["agy"]["enabled"] is False
    assert fleet["providers"]["agy"]["binary"] == "agy"

    # Customize fleet.json & loosen permissions, customize orchestration.json, then re-run
    fleet["providers"]["codex"]["workerCap"] = 9
    fleet["observabilityRemoteSinkCommand"] = ["ssh", "desk", "ingest"]
    user_cfg.write_text(json.dumps(fleet, indent=2) + "\n", encoding="utf-8")
    os.chmod(user_cfg, 0o644)

    orch["tracker"]["readyCommand"] = ["gh", "issue", "list"]
    orch_path.write_text(json.dumps(orch, indent=2) + "\n", encoding="utf-8")

    setup_init.initialize_setup(
        repo_root=repo_dir,
        fleet_config_path=user_cfg,
        extra_bin_dirs=[],
    )

    assert stat.S_IMODE(user_cfg.stat().st_mode) == 0o600
    fleet_after = json.loads(user_cfg.read_text(encoding="utf-8"))
    assert fleet_after["providers"]["codex"]["workerCap"] == 9
    assert fleet_after["observabilityRemoteSinkCommand"] == ["ssh", "desk", "ingest"]

    orch_after = json.loads(orch_path.read_text(encoding="utf-8"))
    assert orch_after["tracker"]["readyCommand"] == ["gh", "issue", "list"]

    # Reject string shell commands, empty *Command [], and non-str/empty argv elements
    bad_orch = dict(orch_after)
    bad_orch["tracker"] = dict(orch_after["tracker"], claimCommand="gh issue edit --add-assignee @me")
    orch_path.write_text(json.dumps(bad_orch) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="argv"):
        setup_init.initialize_setup(repo_root=repo_dir, fleet_config_path=user_cfg, extra_bin_dirs=[])

    bad_orch["tracker"] = dict(orch_after["tracker"], readyCommand=[])
    orch_path.write_text(json.dumps(bad_orch) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty list"):
        setup_init.initialize_setup(repo_root=repo_dir, fleet_config_path=user_cfg, extra_bin_dirs=[])

    bad_orch["tracker"] = dict(orch_after["tracker"], readyCommand=[""])
    orch_path.write_text(json.dumps(bad_orch) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty str"):
        setup_init.initialize_setup(repo_root=repo_dir, fleet_config_path=user_cfg, extra_bin_dirs=[])

    bad_orch["tracker"] = dict(orch_after["tracker"])
    bad_orch["runtime"] = {"commandPrefix": [123]}
    orch_path.write_text(json.dumps(bad_orch) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty str"):
        setup_init.initialize_setup(repo_root=repo_dir, fleet_config_path=user_cfg, extra_bin_dirs=[])

    # Restore valid orchestration.json
    orch_path.write_text(json.dumps(orch_after) + "\n", encoding="utf-8")

    # Reject symlinks on repo_root (live and dangling), .agents, .agents/orchestration.json, fleet_config_path.parent, fleet_config_path
    # 0a. live symlinked repo_root
    sym_repo_live = tmp_path / "sym_repo_live"
    sym_repo_live.symlink_to(repo_dir)
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(repo_root=sym_repo_live, fleet_config_path=user_cfg, extra_bin_dirs=[])

    # 0b. dangling symlinked repo_root
    sym_repo_dangling = tmp_path / "sym_repo_dangling"
    sym_repo_dangling.symlink_to(tmp_path / "nonexistent_repo_target")
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(repo_root=sym_repo_dangling, fleet_config_path=user_cfg, extra_bin_dirs=[])

    # 1. symlinked .agents (dangling)
    bad_repo_1 = tmp_path / "bad_repo_1"
    bad_repo_1.mkdir()
    (bad_repo_1 / ".agents").symlink_to(tmp_path / "nonexistent_agents")
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(repo_root=bad_repo_1, fleet_config_path=user_cfg, extra_bin_dirs=[])

    # 2. symlinked .agents/orchestration.json (dangling)
    bad_repo_2 = tmp_path / "bad_repo_2"
    (bad_repo_2 / ".agents").mkdir(parents=True)
    (bad_repo_2 / ".agents" / "orchestration.json").symlink_to(tmp_path / "nonexistent_orch.json")
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(repo_root=bad_repo_2, fleet_config_path=user_cfg, extra_bin_dirs=[])

    # 3. symlinked fleet_config_path.parent
    sym_cfg_dir = tmp_path / "sym_cfg_dir"
    sym_cfg_dir.symlink_to(tmp_path / "nonexistent_cfg_dir")
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(
            repo_root=repo_dir,
            fleet_config_path=sym_cfg_dir / "fleet.json",
            extra_bin_dirs=[],
        )

    # 4. symlinked fleet_config_path (dangling)
    dangling_fleet = cfg_dir / "dangling_fleet.json"
    dangling_fleet.symlink_to(tmp_path / "nonexistent_fleet.json")
    with pytest.raises(ValueError, match="symlink"):
        setup_init.initialize_setup(
            repo_root=repo_dir,
            fleet_config_path=dangling_fleet,
            extra_bin_dirs=[],
        )

    # CLI test (and verify stdout summary is scrubbed of custom secrets in fleet.json)
    secret_note = "ghs_" + ("5" * 25)
    fleet_with_secret = dict(fleet_after, customNote=secret_note)
    user_cfg.write_text(json.dumps(fleet_with_secret, indent=2) + "\n", encoding="utf-8")
    capsys.readouterr()
    rc = setup_init.main(["--repo-root", str(repo_dir), "--fleet-config", str(user_cfg)])
    assert rc == 0
    raw_cli_out = capsys.readouterr().out
    assert secret_note not in raw_cli_out
    cli_out = json.loads(raw_cli_out)
    assert cli_out["status"] == "ok"
    assert cli_out["providers"]["codex"]["installed"] is True
    assert cli_out["fleet"]["customNote"] == "[REDACTED_GH_TOKEN]"
