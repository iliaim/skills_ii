from __future__ import annotations

import base64
import hashlib
import http.client
import importlib.util
import json
import re
import stat
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


def _load_board():
    path = SCRIPTS_DIR / "briefing_board.py"
    spec = importlib.util.spec_from_file_location("chief_of_staff_briefing_board_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_sse_data_frame(resp: http.client.HTTPResponse) -> dict[str, Any]:
    data_lines: list[str] = []
    while True:
        raw_line = resp.readline()
        assert raw_line, "SSE stream closed unexpectedly before delivering a data frame"
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line == "":
            if data_lines:
                return json.loads("\n".join(data_lines))
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))


def test_snapshot_0600_escapes_script_and_matches_exact_static_csp_hashes(tmp_path: Path) -> None:
    board = _load_board()
    fake_tok = "sk-ant-api03-" + ("z" * 24)
    state = {
        "goal": "</script><script>alert(1)</script>&\u2028\u2029",
        "attention": [{"title": f'Leak "quoted" {fake_tok}'}],
        "tree": {
            "name": "Chief",
            "role": "chief",
            "children": [
                {
                    "name": "Orchestrator-1",
                    "role": "orchestrator",
                    "children": [{"name": "Worker-A", "role": "worker", "status": "running"}],
                }
            ],
        },
        "quotas": {"codex": {"remaining": 3, "cap": 3}},
    }

    out = tmp_path / "briefing.html"
    board.write_snapshot(out, state)

    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    html_text = out.read_text(encoding="utf-8")

    assert "</script><script>" not in html_text
    assert "\\u003c/script\\u003e" in html_text
    assert "\\u0026" in html_text
    assert "\u2028" not in html_text
    assert "\u2029" not in html_text
    assert fake_tok[:10] not in html_text
    assert "[REDACTED_API_KEY]" in html_text
    assert "frame-ancestors" not in html_text
    assert "innerHTML" not in html_text

    meta_match = re.search(
        r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]+)"\s*/?>',
        html_text,
    )
    assert meta_match is not None, "Missing Content-Security-Policy meta tag in snapshot"
    csp = meta_match.group(1)

    style_blocks = re.findall(r"<style>(.*?)</style>", html_text, flags=re.DOTALL)
    script_blocks = re.findall(r"<script>(.*?)</script>", html_text, flags=re.DOTALL)
    assert style_blocks, "Expected at least one static <style> block"
    assert script_blocks, "Expected at least one static <script> block"

    for block in style_blocks:
        digest = base64.b64encode(hashlib.sha256(block.encode("utf-8")).digest()).decode("ascii")
        assert f"'sha256-{digest}'" in csp

    for block in script_blocks:
        digest = base64.b64encode(hashlib.sha256(block.encode("utf-8")).digest()).decode("ascii")
        assert f"'sha256-{digest}'" in csp

    state_match = re.search(
        r'<script id="briefing-state" type="application/json">(.*?)</script>',
        html_text,
        flags=re.DOTALL,
    )
    assert state_match is not None
    embedded = json.loads(state_match.group(1))
    assert embedded["goal"] == "</script><script>alert(1)</script>&\u2028\u2029"
    assert embedded["attention"][0]["title"] == 'Leak "quoted" [REDACTED_API_KEY]'


def test_live_server_security_sse_concurrency_and_clean_shutdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    board = _load_board()
    url_file = tmp_path / "bootstrap.url"
    initial_tok = "ghp_" + ("a" * 24)
    initial_state = {
        "goal": f"Initial Goal {initial_tok}",
        "attention": [{"title": "Review PR #42", "severity": "high"}],
        "tree": {"name": "Chief", "role": "chief", "children": []},
        "quotas": {"codex": {"remaining": 2, "cap": 3}},
    }

    srv = board.LiveBriefingServer(
        initial_state=initial_state,
        bootstrap_url_path=url_file,
        max_sse_clients=2,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    sse_conns: list[http.client.HTTPConnection] = []
    try:
        assert url_file.is_file()
        assert stat.S_IMODE(url_file.stat().st_mode) == 0o600
        auth_url = url_file.read_text(encoding="utf-8").strip()
        expected_prefix = f"http://127.0.0.1:{srv.port}/b/{srv.slug}/auth?t="
        assert auth_url.startswith(expected_prefix)
        parsed_auth = urllib.parse.urlsplit(auth_url)

        # 1. DNS rebinding Host header -> 403
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        conn.putrequest("GET", f"/b/{srv.slug}/", skip_host=True)
        conn.putheader("Host", "evil.example")
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 403

        # 2. Cross-site Sec-Fetch-Site -> 403
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        conn.request("GET", f"/b/{srv.slug}/", headers={"Sec-Fetch-Site": "cross-site"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 403

        # 3. Non-GET methods -> 405
        for method in ("POST", "HEAD", "PUT", "DELETE", "PATCH"):
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
            conn.request(method, f"/b/{srv.slug}/")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            assert resp.status == 405

        # 4. Unauthenticated GET /b/<slug>/ and /b/<slug>/events -> 401
        for path in (f"/b/{srv.slug}/", f"/b/{srv.slug}/events"):
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            conn.close()
            assert resp.status == 401

        # 5. First GET to auth_url -> 302 + Set-Cookie + immediate unlink of bootstrap.url
        opener = urllib.request.build_opener(_NoRedirect())
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            opener.open(auth_url, timeout=5)
        auth_err = exc_info.value
        assert auth_err.code == 302
        assert auth_err.headers.get("Location") == f"/b/{srv.slug}/"
        set_cookie = auth_err.headers.get("Set-Cookie", "")
        assert set_cookie.startswith(f"__skills_ii_{srv.slug}=")
        assert f"Path=/b/{srv.slug}/" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=Strict" in set_cookie
        assert not url_file.exists()

        cookie_pair = set_cookie.split(";", 1)[0]

        # 6. Replay of auth_url -> 401
        with pytest.raises(urllib.error.HTTPError) as replay_exc:
            opener.open(auth_url, timeout=5)
        assert replay_exc.value.code == 401

        # 7. Open SSE stream #1 and read initial frame
        sse1 = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        sse_conns.append(sse1)
        sse1.request(
            "GET",
            f"/b/{srv.slug}/events",
            headers={"Cookie": cookie_pair, "Sec-Fetch-Site": "same-origin"},
        )
        sse1_resp = sse1.getresponse()
        assert sse1_resp.status == 200
        assert "text/event-stream" in sse1_resp.headers.get("Content-Type", "")
        frame1 = _read_sse_data_frame(sse1_resp)
        assert initial_tok not in json.dumps(frame1)
        assert "[REDACTED_GH_TOKEN]" in frame1["goal"]

        # 8. Concurrent GET /b/<slug>/ while SSE stream #1 stays open
        page_conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        page_conn.request(
            "GET",
            f"/b/{srv.slug}/",
            headers={"Cookie": cookie_pair, "Sec-Fetch-Site": "none"},
        )
        page_resp = page_conn.getresponse()
        page_body = page_resp.read().decode("utf-8")
        page_conn.close()
        assert page_resp.status == 200
        http_csp = page_resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in http_csp
        assert '<meta http-equiv="Content-Security-Policy"' not in page_body

        # 9. Publish updated state and read pushed SSE frame
        srv.publish_state(
            {
                "goal": "Updated",
                "attention": [],
                "tree": {"name": "Chief", "role": "chief", "children": []},
                "quotas": {"codex": {"remaining": 1, "cap": 3}},
            }
        )
        pushed = _read_sse_data_frame(sse1_resp)
        assert pushed["goal"] == "Updated"

        # 10. Open SSE stream #2, then 3rd client hits max_sse_clients cap -> 503
        sse2 = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        sse_conns.append(sse2)
        sse2.request("GET", f"/b/{srv.slug}/events", headers={"Cookie": cookie_pair})
        sse2_resp = sse2.getresponse()
        assert sse2_resp.status == 200
        frame2 = _read_sse_data_frame(sse2_resp)
        assert frame2["goal"] == "Updated"

        sse3 = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        sse3.request("GET", f"/b/{srv.slug}/events", headers={"Cookie": cookie_pair})
        sse3_resp = sse3.getresponse()
        sse3_resp.read()
        sse3.close()
        assert sse3_resp.status == 503
    finally:
        for c in sse_conns:
            try:
                c.close()
            except OSError:
                pass
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert not url_file.exists()
        captured = capsys.readouterr()
        assert captured.err == ""


def test_live_server_heartbeat_slow_client_drop_and_idle_shutdown(tmp_path: Path) -> None:
    board = _load_board()
    url_file = tmp_path / "idle-bootstrap.url"
    srv = board.LiveBriefingServer(
        initial_state={"goal": "Heartbeat check"},
        bootstrap_url_path=url_file,
        max_sse_clients=2,
        idle_timeout_seconds=0.15,
        heartbeat_seconds=0.05,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        auth_url = url_file.read_text(encoding="utf-8").strip()
        opener = urllib.request.build_opener(_NoRedirect())
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            opener.open(auth_url, timeout=5)
        cookie_pair = exc_info.value.headers.get("Set-Cookie", "").split(";", 1)[0]

        sse = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        sse.request("GET", f"/b/{srv.slug}/events", headers={"Cookie": cookie_pair})
        resp = sse.getresponse()
        assert resp.status == 200
        _ = _read_sse_data_frame(resp)

        # Confirm heartbeat comment frame arrives
        saw_heartbeat = False
        for _ in range(10):
            line = resp.readline().decode("utf-8")
            if line.startswith(": heartbeat"):
                saw_heartbeat = True
                break
        assert saw_heartbeat

        # Publish >64 frames without reading from SSE to verify non-blocking slow-client drop
        for idx in range(70):
            srv.publish_state({"goal": f"Update {idx}"})
        sse.close()

        # With 0 connected SSE clients, idle_timeout_seconds=0.15 cleanly terminates serve_forever
        thread.join(timeout=3)
        assert not thread.is_alive()
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=3)
        assert not url_file.exists()


def test_cli_snapshot_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    board = _load_board()
    state_path = tmp_path / "state.json"
    snap_path = tmp_path / "out" / "briefing.html"
    state_path.write_text(
        json.dumps(
            {
                "goal": "Ship unified orchestration",
                "attention": [],
                "tree": {"name": "Chief", "children": []},
                "quotas": {},
            }
        ),
        encoding="utf-8",
    )

    rc = board.main(["--state-json", str(state_path), "--snapshot", str(snap_path)])
    assert rc == 0
    assert stat.S_IMODE(snap_path.stat().st_mode) == 0o600
    assert "Ship unified orchestration" in snap_path.read_text(encoding="utf-8")

    # Symlinked --state-json and non-dict JSON are rejected cleanly
    sym_state = tmp_path / "sym-state.json"
    sym_state.symlink_to(state_path)
    bad_snap = tmp_path / "bad.html"
    assert board.main(["--state-json", str(sym_state), "--snapshot", str(bad_snap)]) != 0
    assert not bad_snap.exists()

    list_state = tmp_path / "list-state.json"
    list_state.write_text('["not", "a", "dict"]', encoding="utf-8")
    assert board.main(["--state-json", str(list_state), "--snapshot", str(bad_snap)]) != 0
    assert not bad_snap.exists()
    capsys.readouterr()
