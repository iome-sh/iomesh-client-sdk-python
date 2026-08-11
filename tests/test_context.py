"""Context plane — wire parity with Go QueryContext / ContextSnippet / FormatContextSnippet."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import (
    ConnectOptions,
    ContextResult,
    LineageRef,
    connect,
    format_context_snippet,
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


def test_query_context_text_and_lineage(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v1/context/query"
        body = json.loads(rec["body"].decode("utf-8"))
        assert body["tenant"] == "acme"
        assert body["workspace"] == "ws1"
        assert body["query"] == "incidents"
        assert body["limit"] == 20  # default when limit <= 0
        assert body["include_lineage"] is True
        assert "application/json" in rec["headers"].get("content-type", "")
        assert rec["headers"].get("user-agent", "").startswith("iomesh-client-sdk-python/")
        payload = {
            "text": "ops context for incidents",
            "lineage": [
                {
                    "id": "ops-incidents",
                    "subject": "dept.sre.incidents",
                    "source": "mesh",
                    "freshness": "1m",
                },
                {"product": "crm-contacts", "subject": "dept.sales.contacts"},
            ],
        }
        return 200, json.dumps(payload).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="acme"))
    res = nc.query_context("incidents", workspace="ws1", limit=0, include_lineage=True)
    assert res.ok is True
    assert res.source == "mesh"
    assert res.path == "/v1/context/query"
    assert res.text == "ops context for incidents"
    assert len(res.lineage) == 2
    assert res.lineage[0].id == "ops-incidents"
    assert res.lineage[0].subject == "dept.sre.incidents"
    assert res.lineage[1].product == "crm-contacts"


def test_query_context_items_shape(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        payload = {
            "items": [
                {
                    "text": "first chunk",
                    "lineage": [{"id": "a", "subject": "s.a"}],
                },
                {
                    "text": "second chunk",
                    "lineage": [{"id": "b", "product": "prod-b"}],
                },
            ],
        }
        return 200, json.dumps(payload).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    res = nc.query_context("q")
    assert res.text == "first chunk\nsecond chunk"
    assert len(res.lineage) == 2
    assert res.lineage[0].id == "a"
    assert res.lineage[1].id == "b"
    assert res.ok is True


def test_query_context_fail_open_http(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 500, b"nope", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.query_context("x")
    assert res.text == ""
    assert res.lineage == []
    assert res.ok is False
    assert res.source == "fail-open"
    assert "500" in res.detail


def test_query_context_fail_open_transport() -> None:
    # Unreachable port → ClientError folded to fail-open
    nc = connect(ConnectOptions(url="http://127.0.0.1:1", timeout=0.2))
    res = nc.query_context("x")
    assert res.text == ""
    assert res.lineage == []
    assert res.ok is False
    assert res.source == "fail-open"
    assert res.detail


def test_format_context_snippet_text_only() -> None:
    out = format_context_snippet(ContextResult(text="  hello mesh  "))
    assert out == "hello mesh"


def test_format_context_snippet_lineage_max_12() -> None:
    refs = [
        LineageRef(id=f"p{i}", subject="dept.x", source="mesh", freshness="1m")
        for i in range(14)
    ]
    out = format_context_snippet(ContextResult(text="body", lineage=refs))
    assert "body" in out
    assert "<iomesh-lineage>" in out and "</iomesh-lineage>" in out
    assert "subject=dept.x" in out and "source=mesh" in out
    assert "…" in out
    # Product fallback when ID empty
    out2 = format_context_snippet(
        ContextResult(lineage=[LineageRef(product="only-product", subject="s1")])
    )
    assert "only-product" in out2 and "subject=s1" in out2


def test_context_snippet_integration(broker) -> None:
    include_lineage: list[Any] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode("utf-8"))
        include_lineage.append(body.get("include_lineage"))
        payload = {
            "text": "snippet body",
            "lineage": [
                {"id": "dp1", "subject": "dept.ops", "source": "catalog"},
            ],
        }
        return 200, json.dumps(payload).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    snip = nc.context_snippet("sdk dogfood", workspace=".")
    assert "snippet body" in snip
    assert "<iomesh-lineage>" in snip and "dp1" in snip
    assert include_lineage == [True]

    # Fail-open empty
    def bad(_rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 503, b"down", {}

    broker.set_handler(bad)
    assert nc.context_snippet("q") == ""
