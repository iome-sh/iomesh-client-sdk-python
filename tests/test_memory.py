"""Memory helpers — dual_write OFF default, publish ingest, sync fail-open."""

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
    STREAM_MEMORY_RPC,
    ClientError,
    ConnectOptions,
    MemoryEntityRef,
    MemoryEnvelope,
    MemoryRecallRequest,
    MemoryRetrieveRequest,
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


def test_publish_memory_ingest(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == "/v1/streams/MEMORY_INGEST/publish"
        body = json.loads(rec["body"].decode())
        assert body["subject"] == "dept.research.memory.ingest.turn"
        payload = json.loads(base64.b64decode(body["payload"]))
        assert payload["type"] == "memory_ingest"
        assert payload["content"] == "sdk ingest smoke"
        assert payload["role"] == "assistant"
        assert payload["session_id"] == "sess-1"
        assert payload["event_time"] == "2026-07-13T12:00:00Z"
        assert payload["session_seq"] == 3
        assert payload["entity_refs"] == [{"type": "ticket", "id": "JIRA-100"}]
        return 200, json.dumps(
            {"stream": "MEMORY_INGEST", "seq": 7, "subject": body["subject"]}
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    ack = nc.publish_memory_ingest(
        "dept.research",
        MemoryEnvelope(
            role="assistant",
            content="sdk ingest smoke",
            session_id="sess-1",
            event_time="2026-07-13T12:00:00Z",
            session_seq=3,
            entity_refs=[MemoryEntityRef(type="ticket", id="JIRA-100")],
        ),
    )
    assert ack.seq == 7
    assert ack.stream == "MEMORY_INGEST"


def test_publish_memory_ingest_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.publish_memory_ingest("", MemoryEnvelope(content="x"))
    with pytest.raises(ClientError, match="content required"):
        nc.publish_memory_ingest("dept.x", MemoryEnvelope())


def test_dual_write_default_async_only(broker) -> None:
    published = {"n": 0}
    sync_hits = {"n": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/streams/MEMORY_INGEST/publish":
            published["n"] += 1
            return 200, json.dumps({"stream": "MEMORY_INGEST", "seq": 1}).encode(), {}
        if "memory/ingest" in rec["path"]:
            sync_hits["n"] += 1
            return 200, json.dumps({"status": "ok"}).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    # default sync=False — dual_write OFF
    res = nc.dual_write_memory_turn(
        "dept.x",
        MemoryEnvelope(role="user", content="note", session_id="s1"),
    )
    assert res.async_ack is not None and res.async_ack.seq == 1
    assert res.sync is None
    assert res.sync_err is None
    assert published["n"] == 1
    assert sync_hits["n"] == 0


def test_dual_write_sync_true(broker) -> None:
    async_hits = {"n": 0}
    sync_hits = {"n": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/streams/MEMORY_INGEST/publish":
            async_hits["n"] += 1
            return 200, json.dumps({"stream": "MEMORY_INGEST", "seq": 3}).encode(), {}
        if rec["path"] == "/v1/memory/ingest":
            sync_hits["n"] += 1
            body = json.loads(rec["body"].decode())
            assert body["tenant_id"] == "dept.x"
            assert body["content"] == "dual"
            assert body["type"] == "memory_ingest"
            return 200, json.dumps({"status": "ok", "memory_id": "m1"}).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.dual_write_memory_turn(
        "dept.x",
        MemoryEnvelope(role="assistant", content="dual", session_id="s2"),
        sync=True,
    )
    assert res.async_ack is not None and res.async_ack.seq == 3
    assert res.sync is not None and res.sync.memory_id == "m1"
    assert res.sync_err is None
    assert async_hits["n"] == 1 and sync_hits["n"] == 1


def test_dual_write_sync_fail_open(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/streams/MEMORY_INGEST/publish":
            return 200, json.dumps({"stream": "MEMORY_INGEST", "seq": 2}).encode(), {}
        # no sync ingest routes
        return 404, b"missing", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.dual_write_memory_turn(
        "dept.x",
        MemoryEnvelope(content="x"),
        sync=True,
    )
    assert res.async_ack is not None and res.async_ack.seq == 2
    assert res.sync is None
    assert res.sync_err is not None  # fail-open


def test_ingest_memory_turn_v1_then_v5(broker) -> None:
    paths: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        paths.append(rec["path"])
        if rec["path"] == "/v1/memory/ingest":
            return 404, b"not found", {}
        if rec["path"] == "/v5/memory/ingest":
            body = json.loads(rec["body"].decode())
            assert body["tenant_id"] == "dept.research"
            assert body["event_time"] == "2026-07-13T15:00:00Z"
            assert body["session_seq"] == 4
            return 200, json.dumps(
                {"status": "ok", "memory_id": "mem-99", "tier": 1, "ingested": 1}
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.ingest_memory_turn(
        "dept.research",
        MemoryEnvelope(
            role="assistant",
            content="noted lease rotation",
            session_id="sess-1",
            event_time="2026-07-13T15:00:00Z",
            session_seq=4,
        ),
    )
    assert resp.memory_id == "mem-99"
    assert resp.ingested == 1
    assert resp.note == ""
    assert paths == ["/v1/memory/ingest", "/v5/memory/ingest"]


def test_ingest_memory_turn_keeps_broker_stub_note(broker) -> None:
    """Broker plan-gate stub is not a palace write — keep note, do not invent memory_id."""

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v5/memory/ingest":
            return 202, json.dumps(
                {
                    "status": "accepted",
                    "note": "memory ingest gated; sidecar proxy not configured on broker",
                }
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.ingest_memory_turn(
        "dept.research",
        MemoryEnvelope(role="user", content="lease note"),
    )
    assert resp.status == "accepted"
    assert resp.memory_id == ""
    assert resp.ingested == 0
    assert "sidecar" in resp.note


def test_retrieve_memory_thin(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/memory/retrieve":
            return 404, b"{}", {}
        if rec["path"] == "/v5/memory/retrieve":
            body = json.loads(rec["body"].decode())
            assert body["tenant_id"] == "dept.research"
            assert body["query"] == "lease rotation"
            assert body["type"] == "memory_recall"
            return 200, json.dumps(
                {
                    "memories": [
                        {
                            "id": "mem-1",
                            "summary": "lease rotation",
                            "full": "lease rotation due Q3",
                            "score": 0.91,
                            "session_seq": 3,
                        }
                    ]
                }
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.retrieve_memory(
        MemoryRetrieveRequest(
            tenant_id="dept.research",
            query="lease rotation",
            limit=5,
            session_id="sess-1",
        )
    )
    assert resp.path == "/v5/memory/retrieve"
    assert len(resp.memories) == 1
    assert resp.memories[0].id == "mem-1"
    assert resp.memories[0].score == 0.91


def test_retrieve_memory_related_v1_then_v5(broker) -> None:
    paths: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        paths.append(rec["path"])
        if rec["path"] == "/v1/memory/related":
            return 404, b"{}", {}
        if rec["path"] == "/v5/memory/related":
            body = json.loads(rec["body"].decode())
            assert body["tenant_id"] == "dept.research"
            assert body["seed_entity"] == "person:alice"
            assert body["max_hops"] == 2
            assert body["limit"] == 10
            assert body["prefer_shorter_hops"] is False
            return 200, json.dumps(
                {
                    "memories": [
                        {
                            "id": "mem-r1",
                            "summary": "related note",
                            "score": 0.8,
                            "hop_distance": 1,
                        }
                    ]
                }
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.retrieve_memory_related(
        "dept.research",
        seed_entity="person:alice",
        max_hops=2,
        limit=10,
        prefer_shorter_hops=False,
    )
    assert resp.path == "/v5/memory/related"
    assert len(resp.memories) == 1
    assert resp.memories[0].id == "mem-r1"
    assert resp.memories[0].hop_distance == 1
    assert paths == ["/v1/memory/related", "/v5/memory/related"]


def test_retrieve_memory_related_query_only(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/memory/related":
            body = json.loads(rec["body"].decode())
            assert body["query"] == "lease"
            assert "seed_entity" not in body
            return 200, json.dumps({"memories": []}).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.retrieve_memory_related("dept.x", query="lease")
    assert resp.path == "/v1/memory/related"
    assert resp.memories == []


def test_retrieve_memory_related_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.retrieve_memory_related("")
    with pytest.raises(ClientError, match="seed_entity or query required"):
        nc.retrieve_memory_related("dept.x")


def test_export_ops_digest_v1_then_v5(broker) -> None:
    paths: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        paths.append(rec["path"])
        if rec["path"] == "/v1/memory/ops_digest":
            return 404, b"{}", {}
        if rec["path"] == "/v5/memory/ops_digest":
            body = json.loads(rec["body"].decode())
            assert body["tenant_id"] == "dept.ops"
            assert body["window"] == "week"
            assert body["horizon"] == "ops"
            assert body["as_of"] == "2026-08-01T00:00:00Z"
            return 200, json.dumps(
                {
                    "window": "week",
                    "horizon": "ops",
                    "as_of": "2026-08-01T00:00:00Z",
                    "since": "2026-07-25T00:00:00Z",
                    "honesty": {
                        "ops_pulse": "ga_path",
                        "knowledge": "beta",
                        "analytical": "beta",
                        "never_invent_ga": True,
                        "dual_write_default": "off",
                        "book_demo": "off",
                    },
                    "patterns": [
                        {
                            "id": "p1",
                            "kind": "burst",
                            "subject": "dept.ops.events.>",
                            "count": 12,
                            "summary": "elevated publish rate",
                        }
                    ],
                    "receipts": [
                        {
                            "id": "r1",
                            "event_time": "2026-07-30T12:00:00Z",
                            "summary": "heartbeat",
                        }
                    ],
                    "decision_stub": {
                        "pattern": "p1",
                        "receipts_ref": ["r1"],
                        "product_or_gtm_hypothesis": "scale workers",
                    },
                }
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.export_ops_digest(
        "dept.ops",
        window="week",
        horizon="ops",
        as_of="2026-08-01T00:00:00Z",
    )
    assert resp.path == "/v5/memory/ops_digest"
    assert resp.window == "week"
    assert resp.horizon == "ops"
    assert resp.honesty is not None
    assert resp.honesty.never_invent_ga is True
    assert resp.honesty.dual_write_default == "off"
    assert len(resp.patterns) == 1
    assert resp.patterns[0].id == "p1"
    assert len(resp.receipts) == 1
    assert resp.decision_stub is not None
    assert resp.decision_stub.pattern == "p1"
    assert paths == ["/v1/memory/ops_digest", "/v5/memory/ops_digest"]


def test_export_ops_digest_defaults(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/memory/ops_digest":
            body = json.loads(rec["body"].decode())
            assert body["window"] == "day"
            assert body["horizon"] == "ops"
            return 200, json.dumps(
                {"window": "day", "horizon": "ops", "patterns": [], "receipts": []}
            ).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    resp = nc.export_ops_digest("dept.ops")
    assert resp.path == "/v1/memory/ops_digest"
    assert resp.window == "day"
    assert resp.horizon == "ops"


def test_export_ops_digest_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.export_ops_digest("")


# --- async MEMORY_RPC recall (parity Go RequestMemoryRecall / Full) ---


def test_request_memory_recall_full_session_id(broker) -> None:
    """Parity: Go TestRequestMemoryRecallFullSessionID."""
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == "/v1/streams/MEMORY_RPC/publish"
        body = json.loads(rec["body"].decode())
        captured["subject"] = body["subject"]
        payload = json.loads(base64.b64decode(body["payload"]))
        captured["payload"] = payload
        return 200, json.dumps(
            {"stream": "MEMORY_RPC", "seq": 2, "subject": body["subject"]}
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    ack = nc.request_memory_recall_full(
        MemoryRecallRequest(
            tenant_id="dept.research",
            query="find notes",
            limit=8,
            session_id="dept.research.mesh-dogfood",
        )
    )
    assert ack.seq == 2
    assert ack.stream == STREAM_MEMORY_RPC
    assert captured["subject"] == "dept.research.memory.retrieve.request"
    p = captured["payload"]
    assert p["type"] == "memory_recall"
    assert p["tenant_id"] == "dept.research"
    assert p["query"] == "find notes"
    assert p["limit"] == 8
    assert p["session_id"] == "dept.research.mesh-dogfood"


def test_request_memory_recall_short_form(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == f"/v1/streams/{STREAM_MEMORY_RPC}/publish"
        body = json.loads(rec["body"].decode())
        captured["subject"] = body["subject"]
        payload = json.loads(base64.b64decode(body["payload"]))
        captured["payload"] = payload
        return 200, json.dumps(
            {"stream": "MEMORY_RPC", "seq": 1, "subject": body["subject"]}
        ).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    ack = nc.request_memory_recall("dept.ops", "lease rotation", limit=5)
    assert ack.seq == 1
    assert captured["subject"] == "dept.ops.memory.retrieve.request"
    p = captured["payload"]
    assert p["type"] == "memory_recall"
    assert p["query"] == "lease rotation"
    assert p["limit"] == 5
    assert "session_id" not in p


def test_request_memory_recall_omits_zero_limit(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode())
        captured["payload"] = json.loads(base64.b64decode(body["payload"]))
        return 200, json.dumps({"stream": "MEMORY_RPC", "seq": 1}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.request_memory_recall("dept.x", "q", limit=0)
    assert "limit" not in captured["payload"]


def test_request_memory_recall_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.request_memory_recall("", "q")
    with pytest.raises(ClientError, match="query required"):
        nc.request_memory_recall("dept.x", "")
    with pytest.raises(ClientError, match="query required"):
        nc.request_memory_recall_full(
            MemoryRecallRequest(tenant_id="dept.x", query="  ")
        )
