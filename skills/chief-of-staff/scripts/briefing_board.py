#!/usr/bin/env python3
"""Portable XSS-safe /briefing HTML snapshot writer and localhost-only SSE cockpit server."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import http.cookies
import http.server
import importlib.util
import json
import os
import queue
import re
import secrets
import stat
import sys
import threading
import urllib.parse
from pathlib import Path
from typing import Any

_REDACT_MODULE_NAME = "chief_of_staff_redact"
_REDACT = sys.modules.get(_REDACT_MODULE_NAME)
if _REDACT is None:
    _REDACT_PATH = Path(__file__).resolve().with_name("redact.py")
    _REDACT_SPEC = importlib.util.spec_from_file_location(_REDACT_MODULE_NAME, _REDACT_PATH)
    if _REDACT_SPEC is None or _REDACT_SPEC.loader is None:
        raise ImportError(f"Unable to load redact module from {_REDACT_PATH}")
    _REDACT = importlib.util.module_from_spec(_REDACT_SPEC)
    sys.modules[_REDACT_MODULE_NAME] = _REDACT
    _REDACT_SPEC.loader.exec_module(_REDACT)

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "briefing-template.html"

_CSP_META_PLACEHOLDER = "<!--CSP_META-->"
_STATE_JSON_PLACEHOLDER = "<!--STATE_JSON-->"
_STATIC_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", flags=re.DOTALL)
_STATIC_STYLE_RE = re.compile(r"<style>(.*?)</style>", flags=re.DOTALL)


def _safe_json_for_html(state: dict[str, Any]) -> str:
    """Redact secrets and escape HTML/JS-breaking characters in single-line JSON."""
    scrubbed = _REDACT.scrub_data(state)
    encoded = json.dumps(scrubbed, separators=(",", ":"))
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _sha256_csp_token(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    encoded = base64.b64encode(digest).decode("ascii")
    return f"'sha256-{encoded}'"


def _static_csp(template_html: str, *, include_frame_ancestors: bool) -> str:
    """Build strict CSP from SHA-256 digests of static <script> and <style> blocks."""
    script_blocks = _STATIC_SCRIPT_RE.findall(template_html)
    style_blocks = _STATIC_STYLE_RE.findall(template_html)
    if not script_blocks:
        raise ValueError("Template is missing a static <script> block")
    if not style_blocks:
        raise ValueError("Template is missing a static <style> block")

    script_hashes = " ".join(_sha256_csp_token(block) for block in script_blocks)
    style_hashes = " ".join(_sha256_csp_token(block) for block in style_blocks)
    directives = [
        "default-src 'none'",
        f"script-src {script_hashes}",
        f"style-src {style_hashes}",
        "connect-src 'self'",
        "img-src 'self' data:",
        "base-uri 'none'",
        "form-action 'none'",
    ]
    if include_frame_ancestors:
        directives.append("frame-ancestors 'none'")
    return "; ".join(directives)


def _load_template(template_path: Path = TEMPLATE_PATH) -> str:
    return template_path.read_text(encoding="utf-8")


def render_html(state: dict[str, Any], *, for_http: bool = False) -> str:
    """Render portable or HTTP-served briefing HTML with strict static CSP and scrubbed state."""
    if not isinstance(state, dict):
        raise ValueError(f"Briefing state must be a dict, got {type(state).__name__}")
    template_html = _load_template()
    if _CSP_META_PLACEHOLDER not in template_html or _STATE_JSON_PLACEHOLDER not in template_html:
        raise ValueError("Briefing template is missing required placeholders")

    if for_http:
        csp_meta = ""
    else:
        snapshot_csp = _static_csp(template_html, include_frame_ancestors=False)
        csp_meta = f'<meta http-equiv="Content-Security-Policy" content="{snapshot_csp}">'

    rendered = template_html.replace(_CSP_META_PLACEHOLDER, csp_meta, 1)
    return rendered.replace(_STATE_JSON_PLACEHOLDER, _safe_json_for_html(state), 1)


def write_snapshot(output_path: Path, state: dict[str, Any]) -> Path:
    """Write a 0600 self-contained briefing HTML snapshot atomically without following symlinks."""
    target = Path(output_path)
    html_text = render_html(state, for_http=False)
    _REDACT.safe_atomic_write_0600(target, html_text)
    return target


def _parse_cookie_value(cookie_header: str, cookie_name: str) -> str | None:
    if not cookie_header:
        return None
    jar = http.cookies.SimpleCookie()
    try:
        jar.load(cookie_header)
    except http.cookies.CookieError:
        jar = http.cookies.SimpleCookie()
    if cookie_name in jar:
        return jar[cookie_name].value
    for chunk in cookie_header.split(";"):
        name, sep, value = chunk.strip().partition("=")
        if sep and name.strip() == cookie_name:
            return value.strip()
    return None


class _BriefingRequestHandler(http.server.BaseHTTPRequestHandler):
    """Hardened localhost-only HTTP + SSE handler for LiveBriefingServer."""

    protocol_version = "HTTP/1.1"
    server: LiveBriefingServer

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging so tokens and paths never leak."""
        return

    def _send_text(
        self,
        status: int,
        body: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
        extra_headers: dict[str, str] | None = None,
        suppress_body: bool = False,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.close_connection = True
        if not suppress_body and encoded:
            self.wfile.write(encoded)

    def _check_origin_guards(self) -> bool:
        expected_host = f"127.0.0.1:{self.server.port}"
        host = self.headers.get("Host", "")
        if host != expected_host:
            self._send_text(403, "Forbidden: invalid Host\n", suppress_body=(self.command == "HEAD"))
            return False

        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        if sec_fetch_site is not None and sec_fetch_site.strip().lower() not in ("same-origin", "none"):
            self._send_text(403, "Forbidden: cross-site request\n", suppress_body=(self.command == "HEAD"))
            return False
        return True

    def _reject_non_get(self) -> None:
        if not self._check_origin_guards():
            return
        self._send_text(
            405,
            "Method Not Allowed\n",
            extra_headers={"Allow": "GET"},
            suppress_body=(self.command == "HEAD"),
        )

    def do_POST(self) -> None:
        self._reject_non_get()

    def do_PUT(self) -> None:
        self._reject_non_get()

    def do_DELETE(self) -> None:
        self._reject_non_get()

    def do_PATCH(self) -> None:
        self._reject_non_get()

    def do_HEAD(self) -> None:
        self._reject_non_get()

    def do_OPTIONS(self) -> None:
        self._reject_non_get()

    def _is_authenticated(self) -> bool:
        cookie_val = _parse_cookie_value(self.headers.get("Cookie", ""), self.server.cookie_name)
        if cookie_val is None:
            return False
        return self.server.verify_cookie(cookie_val)

    def do_GET(self) -> None:
        if not self._check_origin_guards():
            return

        parsed = urllib.parse.urlsplit(self.path)
        base_prefix = f"/b/{self.server.slug}"
        if parsed.path == f"{base_prefix}/auth":
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            tokens = query.get("t", [])
            if len(tokens) == 1 and self.server.consume_bootstrap(tokens[0]):
                cookie_header = (
                    f"{self.server.cookie_name}={self.server.cookie_value}; "
                    f"Path={base_prefix}/; HttpOnly; SameSite=Strict"
                )
                self._send_text(
                    302,
                    "",
                    extra_headers={
                        "Location": f"{base_prefix}/",
                        "Set-Cookie": cookie_header,
                    },
                )
            else:
                self._send_text(401, "Unauthorized\n")
            return

        if not self._is_authenticated():
            self._send_text(401, "Unauthorized\n")
            return

        if parsed.path == f"{base_prefix}/":
            html_body = self.server.render_current_http_html()
            self._send_text(
                200,
                html_body,
                content_type="text/html; charset=utf-8",
                extra_headers={"Content-Security-Policy": self.server.http_csp},
            )
            return

        if parsed.path == f"{base_prefix}/events":
            self._handle_sse()
            return

        self._send_text(404, "Not Found\n")

    def _handle_sse(self) -> None:
        client_queue = self.server.register_sse_client()
        if client_queue is None:
            self._send_text(
                503,
                "Too many concurrent SSE clients\n",
                extra_headers={"Retry-After": "5"},
            )
            return

        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.flush()

            while not self.server.is_shutting_down:
                try:
                    payload = client_queue.get(timeout=self.server.heartbeat_seconds)
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    continue
                if payload is None:
                    break
                frame = f"data: {payload}\n\n".encode("utf-8")
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            self.server.unregister_sse_client(client_queue)


class LiveBriefingServer(http.server.ThreadingHTTPServer):
    """Hardened localhost-only ThreadingHTTPServer serving /briefing HTML and SSE."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        initial_state: dict[str, Any],
        bootstrap_url_path: Path | None = None,
        max_sse_clients: int = 16,
        *,
        idle_timeout_seconds: float = 1800.0,
        heartbeat_seconds: float = 15.0,
    ) -> None:
        if not isinstance(initial_state, dict):
            raise ValueError(f"initial_state must be a dict, got {type(initial_state).__name__}")
        if max_sse_clients < 1:
            raise ValueError("max_sse_clients must be >= 1")
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be > 0")

        self._lock = threading.Lock()
        self._state: dict[str, Any] = copy.deepcopy(initial_state)
        self._latest_payload: str = _safe_json_for_html(self._state)
        self._sse_clients: set[queue.Queue[str | None]] = set()
        self._shutting_down = False
        self._serving = False
        self._idle_timer: threading.Timer | None = None

        self.max_sse_clients = max_sse_clients
        self.heartbeat_seconds = heartbeat_seconds
        self.idle_timeout_seconds = idle_timeout_seconds

        template_html = _load_template()
        self.http_csp = _static_csp(template_html, include_frame_ancestors=True)

        self.slug = secrets.token_urlsafe(12)
        self.cookie_name = f"__skills_ii_{self.slug}"
        self.session_secret = secrets.token_urlsafe(32)
        self._session_id = secrets.token_urlsafe(16)
        self._cookie_mac = hmac.new(
            self.session_secret.encode("utf-8"),
            self._session_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.cookie_value = f"{self._session_id}.{self._cookie_mac}"
        self._bootstrap_token: str | None = secrets.token_urlsafe(24)
        self.bootstrap_url_path: Path | None = Path(bootstrap_url_path) if bootstrap_url_path is not None else None

        super().__init__(("127.0.0.1", 0), _BriefingRequestHandler)
        self.port: int = int(self.server_address[1])
        self.auth_url = f"http://127.0.0.1:{self.port}/b/{self.slug}/auth?t={self._bootstrap_token}"

        try:
            if self.bootstrap_url_path is not None:
                _REDACT.safe_atomic_write_0600(self.bootstrap_url_path, self.auth_url)
            self._reset_idle_timer_locked()
        except Exception:
            super().server_close()
            raise

    @property
    def is_shutting_down(self) -> bool:
        with self._lock:
            return self._shutting_down

    def _unlink_bootstrap_file(self) -> None:
        if self.bootstrap_url_path is None:
            return
        try:
            self.bootstrap_url_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _cancel_idle_timer_locked(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _reset_idle_timer_locked(self) -> None:
        self._cancel_idle_timer_locked()
        if self._shutting_down or self.idle_timeout_seconds <= 0 or self._sse_clients:
            return
        timer = threading.Timer(self.idle_timeout_seconds, self._on_idle_timeout)
        timer.daemon = True
        self._idle_timer = timer
        timer.start()

    def _on_idle_timeout(self) -> None:
        should_shutdown = False
        with self._lock:
            if not self._shutting_down and not self._sse_clients and self._serving:
                should_shutdown = True
        if should_shutdown:
            self.shutdown()

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._serving = True
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            with self._lock:
                self._serving = False

    def verify_cookie(self, cookie_value: str) -> bool:
        return hmac.compare_digest(cookie_value, self.cookie_value)

    def consume_bootstrap(self, token: str) -> bool:
        with self._lock:
            if self._shutting_down or self._bootstrap_token is None:
                return False
            if not hmac.compare_digest(token, self._bootstrap_token):
                return False
            self._bootstrap_token = None
        self._unlink_bootstrap_file()
        return True

    def render_current_http_html(self) -> str:
        with self._lock:
            snapshot = copy.deepcopy(self._state)
        return render_html(snapshot, for_http=True)

    def register_sse_client(self) -> queue.Queue[str | None] | None:
        with self._lock:
            if self._shutting_down or len(self._sse_clients) >= self.max_sse_clients:
                return None
            q: queue.Queue[str | None] = queue.Queue(maxsize=64)
            q.put_nowait(self._latest_payload)
            self._sse_clients.add(q)
            self._cancel_idle_timer_locked()
            return q

    def unregister_sse_client(self, client_queue: queue.Queue[str | None]) -> None:
        with self._lock:
            self._sse_clients.discard(client_queue)
            if not self._sse_clients and not self._shutting_down:
                self._reset_idle_timer_locked()

    def publish_state(self, state: dict[str, Any]) -> None:
        """Scrub and broadcast updated state to all connected SSE clients without blocking."""
        if not isinstance(state, dict):
            raise ValueError(f"state must be a dict, got {type(state).__name__}")
        payload = _safe_json_for_html(state)
        with self._lock:
            if self._shutting_down:
                return
            self._state = copy.deepcopy(state)
            self._latest_payload = payload
            for q in list(self._sse_clients):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    # Drop slow client so publish_state never blocks the server or other clients.
                    self._sse_clients.discard(q)
                    while True:
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            break
                    try:
                        q.put_nowait(None)
                    except queue.Full:
                        pass

    def _wake_all_sse_clients_locked(self) -> None:
        for q in list(self._sse_clients):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
        self._sse_clients.clear()

    def shutdown(self) -> None:
        with self._lock:
            self._shutting_down = True
            self._bootstrap_token = None
            self._cancel_idle_timer_locked()
            self._wake_all_sse_clients_locked()
            serving = self._serving
        self._unlink_bootstrap_file()
        if serving:
            super().shutdown()

    def server_close(self) -> None:
        with self._lock:
            self._shutting_down = True
            self._bootstrap_token = None
            self._cancel_idle_timer_locked()
            self._wake_all_sse_clients_locked()
        self._unlink_bootstrap_file()
        super().server_close()


def _load_state_json(path: Path) -> dict[str, Any]:
    if ".." in path.parts:
        raise ValueError(f"Refusing parent traversal '..' in --state-json: {path}")
    if path.is_symlink():
        raise ValueError(f"Refusing symlink for --state-json: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(f"Refusing symlink for --state-json: {path}") from exc
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"Expected regular file for --state-json: {path}")
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = -1
            raw = handle.read()
    finally:
        if fd != -1:
            os.close(fd)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object in --state-json: {path}")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write a portable 0600 /briefing HTML snapshot and/or serve a live localhost SSE cockpit."
    )
    parser.add_argument(
        "--state-json",
        type=Path,
        default=None,
        help="Path to JSON state object file (symlinks refused).",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Write a 0600 portable HTML snapshot to this path.",
    )
    parser.add_argument(
        "--live-bootstrap-file",
        type=Path,
        default=None,
        help="Start live localhost SSE cockpit and write one-time 0600 auth URL here.",
    )
    parser.add_argument(
        "--max-sse-clients",
        type=int,
        default=16,
        help="Maximum concurrent SSE clients (default: 16).",
    )
    parser.add_argument(
        "--idle-timeout-seconds",
        type=float,
        default=1800.0,
        help="Auto-shutdown idle timeout in seconds when 0 SSE clients are connected.",
    )
    args = parser.parse_args(argv)

    if args.snapshot is None and args.live_bootstrap_file is None:
        sys.stderr.write("Error: specify at least one of --snapshot or --live-bootstrap-file.\n")
        return 2

    try:
        state = _load_state_json(args.state_json) if args.state_json is not None else {}
        if args.snapshot is not None:
            write_snapshot(args.snapshot, state)
        if args.live_bootstrap_file is not None:
            server = LiveBriefingServer(
                initial_state=state,
                bootstrap_url_path=args.live_bootstrap_file,
                max_sse_clients=args.max_sse_clients,
                idle_timeout_seconds=args.idle_timeout_seconds,
            )
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.shutdown()
                server.server_close()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
