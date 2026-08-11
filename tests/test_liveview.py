"""Liveview / v3 registry helpers — register_processor + list_live_views (mock HTTP)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, unquote

import pytest

from iomeshclient import (
    PROCESSOR_TYPE_ENRICH,
    PROCESSOR_TYPE_FILTER,
    PROCESSOR_TYPE_MAP,
    VERSION,
    APIError,
    ClientError,
    ConnectOptions,
    LiveView,
    ProcessorConfig,
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


def test_register_processor_success_wire(broker) -> None:
    captured: dict[str, Any] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v3/registry/processors"
        body = json.loads(rec["body"].decode())
        captured["body"] = body
        captured["tenant_hdr"] = rec["headers"].get("x-iomesh-tenant", "")
        return 200, json.dumps(body).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="dept.ops"))
    nc.register_processor(
        ProcessorConfig(
            id="proc-1",
            source_stream="events.in",
            target_stream="events.out",
            tenant="dept.ops",
            type=PROCESSOR_TYPE_FILTER,
            config_json='{"expr":"true"}',
        )
    )
    b = captured["body"]
    assert b["id"] == "proc-1"
    assert b["source_stream"] == "events.in"
    assert b["target_stream"] == "events.out"
    assert b["tenant"] == "dept.ops"
    assert b["type"] == "filter"
    assert b["config_json"] == '{"expr":"true"}'
    assert captured["tenant_hdr"] == "dept.ops"


def test_register_processor_409_is_success(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 409, b'{"error":"already exists"}', {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    # Must not raise
    nc.register_processor(
        ProcessorConfig(
            id="proc-dup",
            source_stream="s1",
            tenant="t1",
            type=PROCESSOR_TYPE_MAP,
        )
    )


def test_register_processor_500_raises(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 500, b"boom", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(APIError) as ei:
        nc.register_processor(
            ProcessorConfig(
                id="proc-x",
                source_stream="s1",
                tenant="t1",
                type=PROCESSOR_TYPE_ENRICH,
            )
        )
    assert ei.value.status_code == 500


def test_register_processor_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="processor id required"):
        nc.register_processor(ProcessorConfig(source_stream="s", tenant="t", type="filter"))
    with pytest.raises(ClientError, match="source_stream required"):
        nc.register_processor(ProcessorConfig(id="p", tenant="t", type="filter"))
    with pytest.raises(ClientError, match="tenant required"):
        nc.register_processor(ProcessorConfig(id="p", source_stream="s", type="filter"))
    with pytest.raises(ClientError, match="type required"):
        nc.register_processor(ProcessorConfig(id="p", source_stream="s", tenant="t"))


def test_list_live_views_wire_and_decode(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "GET"
        assert rec["path"] == "/v3/registry/liveviews"
        qs = parse_qs(rec["query"])
        assert qs.get("tenant_id") == ["tenant-a"]
        payload = [
            {
                "id": "lv-1",
                "tenant_id": "tenant-a",
                "name": "Orders warm",
                "domain": "commerce",
                "owner": "platform",
                "schema_ref": "schemas/orders",
                "upstream_product_ids": ["dp-orders"],
                "subjects": ["orders.>"],
                "stream_name": "orders.warm",
                "created_at": "2026-01-02T03:04:05Z",
                "processor_ids": ["proc-1", "proc-2"],
                "freshness_slo_sec": 30,
                "materialized_path": "s3://bucket/orders",
            }
        ]
        return 200, json.dumps(payload).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    views = nc.list_live_views("tenant-a")
    assert len(views) == 1
    v = views[0]
    assert isinstance(v, LiveView)
    assert v.id == "lv-1"
    assert v.tenant_id == "tenant-a"
    assert v.name == "Orders warm"
    assert v.domain == "commerce"
    assert v.owner == "platform"
    assert v.schema_ref == "schemas/orders"
    assert v.upstream_product_ids == ["dp-orders"]
    assert v.subjects == ["orders.>"]
    assert v.stream_name == "orders.warm"
    assert v.created_at is not None
    assert v.created_at.year == 2026
    assert v.processor_ids == ["proc-1", "proc-2"]
    assert v.freshness_slo_sec == 30
    assert v.materialized_path == "s3://bucket/orders"


def test_list_live_views_empty_body(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    views = nc.list_live_views("t1")
    assert views == []


def test_list_live_views_empty_array(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, b"[]", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    assert nc.list_live_views("t1") == []


def test_list_live_views_non_2xx_raises(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 503, b"unavailable", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(APIError) as ei:
        nc.list_live_views("t1")
    assert ei.value.status_code == 503


def test_list_live_views_requires_tenant() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.list_live_views("")
    with pytest.raises(ClientError, match="tenant_id required"):
        nc.list_live_views("  ")


def test_list_live_views_unexpected_body(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 200, b'{"not":"a list"}', {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(ClientError, match="unexpected list_live_views body"):
        nc.list_live_views("t1")


def test_version_and_constants() -> None:
    assert VERSION == "0.10.1"
    assert PROCESSOR_TYPE_FILTER == "filter"
    assert PROCESSOR_TYPE_MAP == "map"
    assert PROCESSOR_TYPE_ENRICH == "enrich"
