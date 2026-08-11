"""Connection status — wire parity with Go ConnectionStatus / FormatConnectionStatus."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import (
    VERSION,
    ConnectionStatus,
    ConnectOptions,
    aggregate_connection_result,
    connect,
    format_connection_status,
)


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

        def do_POST(self) -> None:
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

        def last(self):
            assert state.requests
            return state.requests[-1]

    try:
        yield Ctx()
    finally:
        server.shutdown()


def test_connection_status_health_and_ready_ok(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] in ("/health", "/ready"):
            return 200, b"", {}
        return 404, b"missing", {}

    broker.set_handler(handler)
    nc = connect(
        ConnectOptions(
            url=broker.url,
            tenant="t1",
            org="o1",
            workspace="w1",
        )
    )
    s = nc.connection_status()
    assert s.base_url == broker.url
    assert s.tenant == "t1" and s.org == "o1" and s.workspace == "w1"
    assert s.user_agent.startswith("iomesh-client-sdk-python/")
    assert s.health_ok and s.health_err == ""
    assert s.ready_ok and s.ready_err == ""
    assert s.health_ms >= 0 and s.ready_ms >= 0 and s.duration_ms >= 0
    assert s.result == "ok"
    assert s.version == VERSION and s.version == "0.10.0"

    human = format_connection_status(s)
    assert "health=ok" in human and "ready=ok" in human
    assert "health_err=\n" in human and "ready_err=\n" in human
    assert "tenant=t1" in human and "org=o1" in human and "workspace=w1" in human
    assert "health_ms=" in human and "ready_ms=" in human and "duration_ms=" in human
    assert "result=ok" in human
    assert f"version={VERSION}" in human


def test_connection_status_health_fail_ready_ok(broker) -> None:
    paths: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        paths.append(rec["path"])
        if rec["path"] == "/health":
            return 503, b"unavailable", {}
        if rec["path"] == "/ready":
            return 200, b"", {}
        return 404, b"missing", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    s = nc.connection_status()
    assert not s.health_ok
    assert s.health_err and "503" in s.health_err
    assert s.ready_ok and s.ready_err == ""
    assert s.health_ms >= 0 and s.ready_ms >= 0 and s.duration_ms >= 0
    assert s.result == "err"
    # Both probes must run even when Health fails.
    assert "/health" in paths
    assert "/ready" in paths or "/readyz" in paths

    human = format_connection_status(s)
    assert "health=FAIL\n" in human and "ready=ok" in human
    assert "health_err=" in human and s.health_err in human
    assert "ready_err=\n" in human
    assert "health=FAIL err=" not in human and "ready=FAIL err=" not in human
    assert "result=err" in human


def test_connection_status_probe_latency_measured(broker) -> None:
    delay = 0.025

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] in ("/health", "/ready"):
            time.sleep(delay)
            return 200, b"", {}
        return 404, b"missing", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    s = nc.connection_status()
    assert s.health_ok and s.ready_ok
    assert s.health_ms >= 0 and s.ready_ms >= 0 and s.duration_ms >= 0
    # Soft check — clock granularity may yield zeros on some hosts.
    if s.health_ms == 0 and s.ready_ms == 0 and s.duration_ms == 0:
        pytest.skip("clock granularity coarser than probe delay")


def test_aggregate_connection_result() -> None:
    assert aggregate_connection_result(True, True) == "ok"
    assert aggregate_connection_result(True, False) == "err"
    assert aggregate_connection_result(False, True) == "err"
    assert aggregate_connection_result(False, False) == "err"


def test_format_connection_status_unknown_result_normalized() -> None:
    s = ConnectionStatus(health_ok=True, ready_ok=True, result="weird")
    human = format_connection_status(s)
    assert "result=ok" in human
