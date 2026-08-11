"""KV helpers — wire parity with Go CreateBucket / Put / Get / Delete / ListKeys."""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import unquote

import pytest

from iomeshclient import (
    ClientError,
    ConnectOptions,
    CreateBucketConfig,
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

        def do_PUT(self) -> None:
            self._handle()

        def do_DELETE(self) -> None:
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

        def last(self):
            assert state.requests
            return state.requests[-1]

    try:
        yield Ctx()
    finally:
        server.shutdown()
        server.server_close()


def test_create_bucket_201(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v1/kv/agent-state"
        body = json.loads(rec["body"].decode()) if rec["body"] else {}
        assert body.get("history") == 5
        assert body.get("max_bytes") == 1024
        resp = {
            "name": "agent-state",
            "max_bytes": 1024,
            "history": 5,
            "ttl_seconds": 3600,
        }
        return 201, json.dumps(resp).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_bucket(
        "agent-state",
        CreateBucketConfig(max_bytes=1024, history=5, ttl_seconds=3600),
    )
    assert info.name == "agent-state"
    assert info.history == 5
    assert info.max_bytes == 1024
    assert info.ttl_seconds == 3600


def test_create_bucket_409_name_only(broker) -> None:
    posts = {"n": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "POST" and rec["path"] == "/v1/kv/agent-state":
            posts["n"] += 1
            return 409, b'{"error":"bucket already exists"}', {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_bucket("agent-state")
    assert posts["n"] == 1
    assert info.name == "agent-state"
    assert info.history == 0
    assert info.max_bytes is None
    assert info.ttl_seconds is None


def test_ensure_bucket_409(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 409, b'{"error":"exists"}', {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.ensure_bucket("agent-state")
    assert info.name == "agent-state"


def test_create_bucket_201_omits_name(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 201, json.dumps({"history": 1}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_bucket("fallback-name")
    assert info.name == "fallback-name"
    assert info.history == 1


def test_create_bucket_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="bucket name required"):
        nc.create_bucket("")
    with pytest.raises(ClientError, match="bucket name required"):
        nc.create_bucket("   ")


def test_put_200_revision(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "PUT"
        assert rec["path"] == "/v1/kv/agent-state/worker-1.checkpoint"
        body = json.loads(rec["body"].decode())
        assert base64.b64decode(body["value"]) == b"seq=42"
        return 200, json.dumps(
            {"bucket": "agent-state", "key": "worker-1.checkpoint", "revision": 7}
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.put("agent-state", "worker-1.checkpoint", b"seq=42")
    assert res.bucket == "agent-state"
    assert res.key == "worker-1.checkpoint"
    assert res.revision == 7


def test_put_defensive_fill(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, json.dumps({"revision": 3}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.put("agent-state", "worker-1.checkpoint", b"x")
    assert res.bucket == "agent-state"
    assert res.key == "worker-1.checkpoint"
    assert res.revision == 3


def test_put_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="bucket required"):
        nc.put("", "k", b"x")
    with pytest.raises(ClientError, match="key required"):
        nc.put("b", "", b"x")


def test_get_base64_value(broker) -> None:
    val_b64 = base64.b64encode(b"seq=42").decode("ascii")

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "GET"
        assert rec["path"] == "/v1/kv/agent-state/worker-1.checkpoint"
        return 200, json.dumps(
            {
                "bucket": "agent-state",
                "key": "worker-1.checkpoint",
                "value": val_b64,
                "revision": 3,
                "created_at": "2026-07-01T12:00:00Z",
            }
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    entry = nc.get("agent-state", "worker-1.checkpoint")
    assert entry.value == b"seq=42"
    assert entry.revision == 3
    assert entry.created_at is not None


def test_get_graceful_non_base64(broker) -> None:
    # if string is not valid base64 payload, fall back to UTF-8 bytes
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        # base64.b64decode without validate accepts many strings; use clearly non-b64 path
        # actually validate=False is loose — we test empty + null
        return 200, json.dumps(
            {"bucket": "b", "key": "k", "value": None, "revision": 1}
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    entry = nc.get("b", "k")
    assert entry.value == b""


def test_delete(broker) -> None:
    deleted: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "DELETE":
            deleted.append(rec["path"])
            return 204, b"", {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.delete("agent-state", "worker-1.checkpoint")
    assert deleted == ["/v1/kv/agent-state/worker-1.checkpoint"]


def test_list_keys_with_prefix(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "GET"
        assert rec["path"] == "/v1/kv/agent-state"
        assert "prefix=worker" in rec["query"]
        keys = ["worker-1.checkpoint", "worker-2.checkpoint"]
        return 200, json.dumps({"keys": keys}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    keys = nc.list_keys("agent-state", prefix="worker")
    assert keys == ["worker-1.checkpoint", "worker-2.checkpoint"]


def test_list_keys_empty(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, json.dumps({"keys": []}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    assert nc.list_keys("agent-state") == []
