"""Metering helpers — emit_dept_event / emit_llm_call publish path (mock HTTP)."""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import (
    STREAM_DEPT,
    TYPE_DEPT_AGENT_LLM_CALL,
    VERSION,
    ClientError,
    ConnectOptions,
    DeptEvent,
    LLMCallEvent,
    connect,
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

    try:
        yield Ctx()
    finally:
        server.shutdown()
        server.server_close()


def test_emit_llm_call_publish_wire_and_headers(broker) -> None:
    """Parity: Go TestEmitLLMCall_PublishWireAndHeaders."""
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == "/v1/streams/dept/publish"
        assert rec["method"] == "POST"
        h = rec["headers"]
        captured["org"] = h.get("x-iomesh-org", "")
        captured["ws"] = h.get("x-iomesh-workspace", "")
        captured["tenant"] = h.get("x-iomesh-tenant", "")
        body = json.loads(rec["body"].decode())
        captured["subject"] = body["subject"]
        raw = base64.b64decode(body["payload"])
        captured["decoded"] = json.loads(raw.decode("utf-8"))
        return (
            200,
            json.dumps({"stream": "dept", "seq": 9, "subject": body["subject"]}).encode(),
            {},
        )

    broker.set_handler(handler)
    nc = connect(
        ConnectOptions(
            url=broker.url,
            tenant="dept.research",
            org="org_a",
            workspace="ws_1",
        )
    )
    ack = nc.emit_llm_call(
        LLMCallEvent(
            tenant="dept.research",
            session_id="sess-1",
            model="deepseek-v4-flash",
            model_id="deepseek-v4-flash",
            duration_ms=12,
            attempts=1,
            est_usd=0.001,
            prompt_tokens=5,
            total_tokens=10,
        )
    )
    assert ack.seq == 9
    assert ack.stream == "dept"
    assert ack.subject == TYPE_DEPT_AGENT_LLM_CALL
    assert captured["subject"] == "dept.agent.llm_call"
    assert captured["org"] == "org_a"
    assert captured["ws"] == "ws_1"
    assert captured["tenant"] == "dept.research"

    decoded = captured["decoded"]
    assert decoded["type"] == "dept.agent.llm_call"
    assert decoded["session_id"] == "sess-1"
    assert decoded["tenant"] == "dept.research"
    assert decoded.get("ts")
    payload = decoded["payload"]
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["model_id"] == "deepseek-v4-flash"
    assert payload["duration_ms"] == 12
    assert payload["attempts"] == 1
    assert payload["fallback"] is False
    assert payload["est_usd"] == 0.001
    assert payload["org"] == "org_a"
    assert payload["workspace"] == "ws_1"
    assert payload["tenant"] == "dept.research"
    assert payload["tokens"]["prompt"] == 5
    assert payload["tokens"]["completion"] == 0
    assert payload["tokens"]["total"] == 10


def test_emit_dept_event_requires_type() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="type required"):
        nc.emit_dept_event(DeptEvent())
    with pytest.raises(ClientError, match="type required"):
        nc.emit_dept_event(DeptEvent(type="  "))


def test_emit_dept_event_defaults_tenant_and_ts(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode())
        raw = base64.b64decode(body["payload"])
        captured["decoded"] = json.loads(raw.decode("utf-8"))
        captured["subject"] = body["subject"]
        return (
            200,
            json.dumps({"stream": STREAM_DEPT, "seq": 1, "subject": body["subject"]}).encode(),
            {},
        )

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="dept.ops", org="o1", workspace="w1"))
    ack = nc.emit_dept_event(DeptEvent(type="dept.agent.heartbeat", session_id="s2"))
    assert ack.seq == 1
    assert captured["subject"] == "dept.agent.heartbeat"
    dec = captured["decoded"]
    assert dec["type"] == "dept.agent.heartbeat"
    assert dec["tenant"] == "dept.ops"
    assert dec["session_id"] == "s2"
    assert dec["payload"]["org"] == "o1"
    assert dec["payload"]["workspace"] == "w1"
    assert dec["payload"]["tenant"] == "dept.ops"
    # ts auto-filled
    ts = datetime.fromisoformat(dec["ts"].replace("Z", "+00:00"))
    assert ts.tzinfo is not None


def test_emit_dept_event_does_not_overwrite_payload_keys(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode())
        raw = base64.b64decode(body["payload"])
        captured["decoded"] = json.loads(raw.decode("utf-8"))
        ack = {"stream": "dept", "seq": 2, "subject": body["subject"]}
        return 200, json.dumps(ack).encode(), {}

    broker.set_handler(handler)
    nc = connect(
        ConnectOptions(url=broker.url, tenant="t1", org="client-org", workspace="client-ws")
    )
    nc.emit_dept_event(
        DeptEvent(
            type="dept.custom",
            tenant="explicit-tenant",
            ts=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            payload={
                "org": "payload-org",
                "workspace": "payload-ws",
                "tenant": "payload-tenant",
            },
        )
    )
    p = captured["decoded"]["payload"]
    assert p["org"] == "payload-org"
    assert p["workspace"] == "payload-ws"
    assert p["tenant"] == "payload-tenant"
    assert captured["decoded"]["ts"].startswith("2026-01-02T03:04:05")


def test_emit_llm_call_extra_and_error(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode())
        raw = base64.b64decode(body["payload"])
        captured["decoded"] = json.loads(raw.decode("utf-8"))
        ack = {"stream": "dept", "seq": 3, "subject": body["subject"]}
        return 200, json.dumps(ack).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.emit_llm_call(
        LLMCallEvent(
            model="m",
            error=" redacted ",
            extra={"trace_id": "tr-1", "": "skip-empty-key"},
            org="from-call",
            workspace="ws-call",
        )
    )
    p = captured["decoded"]["payload"]
    assert p["error"] == "redacted"
    assert p["trace_id"] == "tr-1"
    assert "" not in p
    assert p["org"] == "from-call"
    assert p["workspace"] == "ws-call"


def test_version_constants() -> None:
    assert VERSION == "0.8.0"
    assert STREAM_DEPT == "dept"
    assert TYPE_DEPT_AGENT_LLM_CALL == "dept.agent.llm_call"
