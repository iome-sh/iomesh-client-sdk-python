"""Policy evaluate — wire parity with Go EvaluatePolicy / ShouldBlockTool."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import (
    POLICY_ADVISORY,
    POLICY_ENFORCE,
    POLICY_OFF,
    ConnectOptions,
    PolicyInput,
    connect,
    normalize_policy_mode,
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
        server.server_close()


def test_normalize_policy_mode() -> None:
    assert normalize_policy_mode("") == POLICY_OFF
    assert normalize_policy_mode("OFF") == POLICY_OFF
    assert normalize_policy_mode(" Advisory ") == POLICY_ADVISORY
    assert normalize_policy_mode("ENFORCE") == POLICY_ENFORCE
    assert normalize_policy_mode("bogus") == POLICY_OFF


def test_evaluate_policy_mode_off_no_network(broker) -> None:
    # No handler needed — mode off short-circuits.
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    dec = nc.evaluate_policy(PolicyInput(tool="run_shell", mode=POLICY_OFF))
    assert dec.allow
    assert dec.source == "off"
    assert dec.mode == POLICY_OFF
    assert not dec.should_block_tool()
    assert broker.requests == []

    # Empty mode normalizes to off.
    dec2 = nc.evaluate_policy(PolicyInput(tool="x"))
    assert dec2.allow and dec2.source == "off"
    assert broker.requests == []


def test_evaluate_policy_enforce_deny_mesh(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v1/policy/evaluate"
        body = json.loads(rec["body"].decode())
        assert body["tool"] == "run_shell"
        assert body["action"] == "tool.run_shell"  # auto action
        assert body["tenant"] == "t"
        assert body["mode"] == "enforce"
        assert rec["headers"].get("user-agent", "").startswith(
            "iomesh-client-sdk-python/"
        )
        return (
            200,
            json.dumps(
                {"allow": False, "reasons": ["rego: shell blocked"]}
            ).encode(),
            {},
        )

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    dec = nc.evaluate_policy(
        PolicyInput(tool="run_shell", mode=POLICY_ENFORCE)
    )
    assert not dec.allow
    assert dec.source == "mesh"
    assert dec.should_block_tool()
    assert "deny" in dec.summary()
    assert "shell blocked" in dec.summary()


def test_evaluate_policy_advisory_deny_does_not_block(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, json.dumps({"allow": False, "reason": "nope"}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    dec = nc.evaluate_policy(
        PolicyInput(tool="write_file", mode=POLICY_ADVISORY)
    )
    assert not dec.allow
    assert dec.source == "mesh"
    assert not dec.should_block_tool()
    assert "nope" in dec.reasons


def test_evaluate_policy_404_unavailable(broker) -> None:
    broker.set_handler(lambda rec: (404, b"missing", {}))
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    dec = nc.evaluate_policy(PolicyInput(tool="x", mode=POLICY_ENFORCE))
    assert dec.allow
    assert dec.source == "unavailable"
    assert not dec.should_block_tool()


def test_evaluate_policy_unreachable_fail_open() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:1", tenant="t"))
    dec = nc.evaluate_policy(
        PolicyInput(
            action="tool.run_shell",
            tool="run_shell",
            mode=POLICY_ENFORCE,
        )
    )
    assert dec.allow
    assert dec.source == "fail-open"
    assert not dec.should_block_tool()


def test_evaluate_policy_http_500_fail_open(broker) -> None:
    broker.set_handler(lambda rec: (500, b"boom", {}))
    nc = connect(ConnectOptions(url=broker.url))
    dec = nc.evaluate_policy(PolicyInput(tool="x", mode=POLICY_ENFORCE))
    assert dec.allow
    assert dec.source == "fail-open"
    assert any("500" in r for r in dec.reasons)


def test_evaluate_policy_allowed_alias_and_deny_flag(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, json.dumps({"allowed": True}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    dec = nc.evaluate_policy(PolicyInput(action="read", mode=POLICY_ADVISORY))
    assert dec.allow and dec.source == "mesh"
    assert "allow" in dec.summary()

    def deny_handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, json.dumps({"deny": True}).encode(), {}

    broker.set_handler(deny_handler)
    dec2 = nc.evaluate_policy(PolicyInput(action="write", mode=POLICY_ENFORCE))
    assert not dec2.allow
    assert dec2.should_block_tool()


def test_evaluate_policy_attributes_pass_through(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode())
        assert body["attributes"] == {"risk": "high"}
        assert body["resource"] == "file:///tmp/x"
        return 200, json.dumps({"allow": True}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="eng"))
    dec = nc.evaluate_policy(
        PolicyInput(
            tool="run_shell",
            resource="file:///tmp/x",
            attributes={"risk": "high"},
            mode=POLICY_ADVISORY,
        )
    )
    assert dec.allow and dec.source == "mesh"
