"""wait_ready polls ready (+ optional health) until success or timeout."""

from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import ClientError, ConnectOptions, WaitReadyResult, connect


class _BrokerState:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.handler: Optional[Callable[[Any], tuple[int, bytes, dict[str, str]]]] = None


def _make_handler(state: _BrokerState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            headers = {k.lower(): v for k, v in self.headers.items()}
            path_only, _, qs = self.path.partition("?")
            rec = {
                "method": self.command,
                "path": unquote(path_only),
                "query": qs,
                "headers": headers,
                "body": body,
            }
            state.requests.append(rec)
            if state.handler is None:
                self.send_response(404)
                self.end_headers()
                return
            status, payload, extra_headers = state.handler(rec)
            self.send_response(status)
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            if payload is not None and status != 204:
                if "Content-Type" not in (extra_headers or {}):
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload and status != 204:
                self.wfile.write(payload)

        def do_GET(self) -> None:
            self._handle()

    return Handler


@pytest.fixture
def broker():
    state = _BrokerState()
    server = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    class Ctx:
        def set_handler(self, fn):
            state.handler = fn

        @property
        def url(self):
            return base

        @property
        def requests(self):
            return state.requests

    try:
        yield Ctx()
    finally:
        server.shutdown()
        server.server_close()


def test_wait_ready_immediate(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/ready":
            return 200, b"ok", {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, timeout=2.0))
    result = nc.wait_ready(timeout_sec=5.0, interval_sec=0.05)
    assert isinstance(result, WaitReadyResult)
    assert result.attempts == 1
    assert result.elapsed_sec >= 0
    assert result.elapsed_sec < 2.0


def test_wait_ready_fails_n_then_ok(broker) -> None:
    hits = {"ready": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] in ("/ready", "/readyz"):
            hits["ready"] += 1
            # fail first 2 ready probes, then 200
            if hits["ready"] <= 2:
                return 503, b"not ready", {}
            return 200, b"ok", {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, timeout=2.0))
    result = nc.wait_ready(timeout_sec=5.0, interval_sec=0.05)
    assert result.attempts == 3
    assert hits["ready"] >= 3


def test_wait_ready_timeout(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 503, b"down", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, timeout=1.0))
    with pytest.raises(ClientError, match="wait ready: timeout"):
        nc.wait_ready(timeout_sec=0.25, interval_sec=0.05)


def test_wait_ready_require_health(broker) -> None:
    state = {"ready": 0, "health": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] in ("/ready", "/readyz"):
            state["ready"] += 1
            return 200, b"ok", {}
        if rec["path"] == "/health":
            state["health"] += 1
            if state["health"] < 2:
                return 503, b"unhealthy", {}
            return 200, b"ok", {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, timeout=2.0))
    result = nc.wait_ready(
        timeout_sec=5.0, interval_sec=0.05, require_health=True
    )
    assert result.attempts == 2
    assert state["health"] == 2
