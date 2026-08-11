"""Catalog helpers — wire parity with Go ListCatalog / GetCatalogProduct."""

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
    connect,
    format_catalog,
    format_product_detail,
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


def test_list_catalog_products_mesh(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] != "/v1/catalog/data-products":
            return 404, b"not found", {}
        assert "tenant=acme" in rec["query"]
        resp = {
            "products": [
                {
                    "id": "ops-incidents",
                    "layer": "operational",
                    "subject": "dept.sre.incidents",
                    "title": "Incidents",
                },
                {
                    "id": "crm-contacts",
                    "layer": "knowledge",
                    "subject": "dept.sales.contacts",
                    "name": "CRM",
                },
            ]
        }
        return 200, json.dumps(resp).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="acme"))
    res = nc.list_catalog("")
    assert res.source == "mesh"
    assert len(res.products) == 2
    assert res.detail == "/v1/catalog/data-products"
    assert broker.last()["headers"].get("user-agent", "").startswith(
        "iomesh-client-sdk-python/"
    )
    out = format_catalog(res)
    assert "ops-incidents" in out
    assert "operational" in out


def test_list_catalog_fail_open_all_404(broker) -> None:
    broker.set_handler(lambda rec: (404, b"nope", {}))
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.list_catalog("q")
    assert res.source == "fail-open"
    assert res.products == []
    assert "404" in res.detail or "no catalog" in res.detail
    # All four default paths tried
    paths = [r["path"] for r in broker.requests]
    assert "/v1/catalog/data-products" in paths
    assert "/v1/catalog/products" in paths
    assert "/v17/portal/catalog/data-products" in paths
    assert "/v16/portal/catalog/marketing/data-products" in paths


def test_list_catalog_portal_federation(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v17/portal/catalog/data-products":
            resp = {
                "version": "v17-test",
                "products": [
                    {
                        "id": "engineering-github-events",
                        "name": "GitHub Events",
                        "mesh_layer": "operational",
                        "subject_pattern": "dept.engineering.github.>",
                        "summary": "GitHub webhook stream",
                        "sample_subjects": ["dept.engineering.github.push"],
                        "lineage": ["github", "connector", "mesh"],
                        "status": "ga",
                    }
                ],
            }
            return 200, json.dumps(resp).encode(), {}
        return 404, b"not found", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.list_catalog("")
    assert res.source == "portal"
    assert "/v17/" in res.detail
    assert len(res.products) == 1
    p = res.products[0]
    assert p.layer == "operational"
    assert p.subject == "dept.engineering.github.>"
    assert p.description == "GitHub webhook stream"
    assert p.subjects == ["dept.engineering.github.push"]
    out = format_catalog(res)
    assert "engineering-github" in out
    assert "source=portal" in out


def test_list_catalog_query_mesh_layer(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] != "/v1/catalog/data-products":
            return 404, b"", {}
        assert "q=operational" in rec["query"]
        assert "mesh_layer=operational" in rec["query"]
        return 200, json.dumps({"products": []}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="t"))
    res = nc.list_catalog("operational")
    assert res.source == "mesh"
    assert res.products == []


def test_get_catalog_product_detail(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v17/portal/catalog/data-products/engineering-github-events":
            resp = {
                "id": "engineering-github-events",
                "name": "GitHub Events",
                "mesh_layer": "operational",
                "summary": "detail ok",
            }
            return 200, json.dumps(resp).encode(), {}
        return 404, b"not found", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    p, meta = nc.get_catalog_product("engineering-github-events")
    assert meta.source == "portal"
    assert p.id == "engineering-github-events"
    assert p.layer == "operational"
    d = format_product_detail(p, meta)
    assert "detail ok" in d


def test_get_catalog_product_list_filter_fallback(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/catalog/data-products":
            resp = {
                "products": [
                    {"id": "ops-incidents", "name": "Incidents", "layer": "operational"},
                    {"id": "other", "name": "Other"},
                ]
            }
            return 200, json.dumps(resp).encode(), {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    p, meta = nc.get_catalog_product("ops-incidents")
    assert p.id == "ops-incidents"
    assert "list filter" in meta.detail
    assert meta.source == "mesh"


def test_get_catalog_product_empty_id(broker) -> None:
    nc = connect(ConnectOptions(url=broker.url))
    p, meta = nc.get_catalog_product("")
    assert meta.source == "fail-open"
    assert "empty" in meta.detail
    assert p.id == ""


def test_get_catalog_product_not_found(broker) -> None:
    broker.set_handler(lambda rec: (404, b"", {}))
    nc = connect(ConnectOptions(url=broker.url))
    p, meta = nc.get_catalog_product("missing-product")
    assert meta.source == "fail-open"
    assert "not found" in meta.detail
    assert p.id == ""


def test_list_catalog_array_body(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/catalog/data-products":
            return 200, json.dumps([{"id": "a", "name": "A"}]).encode(), {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    res = nc.list_catalog()
    assert len(res.products) == 1
    assert res.products[0].id == "a"


def test_format_catalog_empty() -> None:
    from iomeshclient.catalog import CatalogResult

    out = format_catalog(CatalogResult(source="fail-open", detail="x"))
    assert "source=fail-open" in out
    assert "(no data products)" in out
