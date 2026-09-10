"""Unit tests for iomeshclient HTTP core (stdlib mock broker; no live mesh)."""

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
    VERSION,
    APIError,
    ClientError,
    ConnectOptions,
    CreateConsumerConfig,
    StreamConfig,
    connect,
    connect_from_env,
)
from iomeshclient.client import DEFAULT_USER_AGENT


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
            # Case-insensitive map: urllib/http.server header casing varies by platform.
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

        def do_DELETE(self) -> None:
            self._handle()

        def do_PUT(self) -> None:
            self._handle()

    return Handler


class _BrokerCtx:
    def __init__(self, url: str, state: _BrokerState) -> None:
        self.url = url
        self._state = state

    def set_handler(
        self, fn: Callable[[dict[str, Any]], tuple[int, bytes, dict[str, str]]]
    ) -> None:
        self._state.handler = fn

    def last(self) -> dict[str, Any]:
        assert self._state.requests, "expected at least one request"
        return self._state.requests[-1]

    def json_body(self, rec: Optional[dict[str, Any]] = None) -> Any:
        r = rec or self.last()
        if not r["body"]:
            return None
        return json.loads(r["body"].decode("utf-8"))


@pytest.fixture
def broker():
    state = _BrokerState()
    server = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield _BrokerCtx(base, state)
    finally:
        server.shutdown()
        server.server_close()


# --- connect / URL validation ---


def test_connect_rejects_empty_url() -> None:
    with pytest.raises(ClientError, match="URL required"):
        connect(ConnectOptions(url=""))
    with pytest.raises(ClientError, match="URL required"):
        connect(ConnectOptions(url="   "))


def test_connect_rejects_unsafe_urls() -> None:
    cases = [
        "file:///etc/passwd",
        "ftp://example.com",
        "//no-scheme.example",
        "http://user:pass@127.0.0.1:8422",
        "https://alice:secret@mesh.example.com",
        "not a url",
    ]
    for u in cases:
        with pytest.raises(ClientError):
            connect(ConnectOptions(url=u))


def test_connect_accepts_http_https() -> None:
    for u in ("http://127.0.0.1:8422", "https://mesh.example.com"):
        nc = connect(ConnectOptions(url=u))
        assert nc.base_url == u.rstrip("/")


def test_connect_strips_trailing_slash() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:8422/"))
    assert nc.base_url == "http://127.0.0.1:8422"


def test_connect_no_network_io() -> None:
    # connect must not dial; unreachable port is fine
    nc = connect(ConnectOptions(url="http://127.0.0.1:1"))
    assert nc.base_url == "http://127.0.0.1:1"


# --- connect_from_env ---


def test_connect_from_env_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IOMESH_URL", raising=False)
    with pytest.raises(ClientError, match="IOMESH_URL required"):
        connect_from_env()
    monkeypatch.setenv("IOMESH_URL", "   ")
    with pytest.raises(ClientError, match="IOMESH_URL required"):
        connect_from_env()


def test_connect_from_env_reads_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOMESH_URL", "http://127.0.0.1:8422/")
    monkeypatch.setenv("IOMESH_TENANT", "dept.engineering")
    monkeypatch.setenv("IOMESH_ORG", "acme-org")
    monkeypatch.setenv("IOMESH_WORKSPACE", "ws_default")
    monkeypatch.setenv("IOMESH_DEPARTMENT", "engineering")
    monkeypatch.setenv("IOMESH_BEARER_TOKEN", "secret-token")
    monkeypatch.setenv("IOMESH_TIMEOUT", "12.5")
    nc = connect_from_env()
    assert nc.base_url == "http://127.0.0.1:8422"
    assert nc.tenant == "dept.engineering"
    assert nc.org == "acme-org"
    assert nc.workspace == "ws_default"
    assert nc.department == "engineering"
    assert nc.bearer_token == "secret-token"
    assert nc.timeout == 12.5


def test_connect_from_env_token_alias_and_bearer_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IOMESH_URL", "https://mesh.example.com")
    monkeypatch.delenv("IOMESH_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("IOMESH_TOKEN", "legacy-token")
    nc = connect_from_env()
    assert nc.bearer_token == "legacy-token"

    monkeypatch.setenv("IOMESH_BEARER_TOKEN", "primary")
    monkeypatch.setenv("IOMESH_TOKEN", "legacy-token")
    nc2 = connect_from_env()
    assert nc2.bearer_token == "primary"


def test_connect_from_env_explicit_mapping() -> None:
    nc = connect_from_env(
        {
            "IOMESH_URL": "http://127.0.0.1:9",
            "IOMESH_TENANT": "t1",
        }
    )
    assert nc.base_url == "http://127.0.0.1:9"
    assert nc.tenant == "t1"
    assert nc.org == ""
    assert nc.department == ""
    assert nc.timeout == 30.0


def test_connect_from_env_invalid_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOMESH_URL", "http://127.0.0.1:8422")
    monkeypatch.setenv("IOMESH_TIMEOUT", "not-a-float")
    with pytest.raises(ClientError, match="IOMESH_TIMEOUT invalid"):
        connect_from_env()


# --- auth headers ---


def test_headers_tenant_org_workspace_department_bearer_user_agent(broker) -> None:
    captured: dict[str, str] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        h = rec["headers"]
        captured["tenant"] = h.get("x-iomesh-tenant", "")
        captured["org"] = h.get("x-iomesh-org", "")
        captured["workspace"] = h.get("x-iomesh-workspace", "")
        captured["department"] = h.get("x-iomesh-department", "")
        captured["auth"] = h.get("authorization", "")
        captured["ua"] = h.get("user-agent", "")
        return 200, b"", {}

    broker.set_handler(handler)
    nc = connect(
        ConnectOptions(
            url=broker.url,
            tenant="dept.research",
            org="org_a",
            workspace="ws_1",
            department="engineering",
            bearer_token="test-token",
        )
    )
    nc.health()
    assert captured["tenant"] == "dept.research"
    assert captured["org"] == "org_a"
    assert captured["workspace"] == "ws_1"
    assert captured["department"] == "engineering"
    assert captured["auth"] == "Bearer test-token"
    assert captured["ua"] == f"iomesh-client-sdk-python/{VERSION}"
    assert captured["ua"] == DEFAULT_USER_AGENT
    assert captured["ua"] == "iomesh-client-sdk-python/0.11.1"


def test_headers_department_set_and_omit(broker) -> None:
    captured: list[dict[str, str]] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        captured.append(rec["headers"])
        return 200, b"", {}

    broker.set_handler(handler)
    connect(ConnectOptions(url=broker.url, department="  finance  ")).health()
    connect(ConnectOptions(url=broker.url, department="")).health()
    connect(ConnectOptions(url=broker.url, department="   ")).health()
    assert captured[0].get("x-iomesh-department") == "finance"
    assert "x-iomesh-department" not in captured[1]
    assert "x-iomesh-department" not in captured[2]


def test_headers_omitted_when_unset(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        h = rec["headers"]
        assert "x-iomesh-tenant" not in h
        assert "x-iomesh-org" not in h
        assert "x-iomesh-workspace" not in h
        assert "x-iomesh-department" not in h
        assert "authorization" not in h
        assert h.get("user-agent") == "iomesh-client-sdk-python/0.11.1"
        return 200, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.health()


def test_require_org_fails_closed_on_fetch_without_org(broker) -> None:
    def handler(_rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        raise AssertionError("must not call broker when org is required and empty")

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, require_org=True))
    with pytest.raises(ClientError, match="X-IOMesh-Org required"):
        nc.consumer_fetch("EVENTS", "worker", 1)
    with pytest.raises(ClientError, match="X-IOMesh-Org required"):
        nc.list_streams()


def test_require_org_fetch_sends_header_when_set(broker) -> None:
    got: dict[str, str] = {}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        got["org"] = rec["headers"].get("x-iomesh-org", "")
        return 200, json.dumps({"messages": []}).encode(), {"Content-Type": "application/json"}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, org="org_a", require_org=True))
    assert nc.consumer_fetch("EVENTS", "worker", 1) == []
    assert got["org"] == "org_a"


def test_connect_from_env_require_org_flag() -> None:
    nc = connect_from_env(
        {
            "IOMESH_URL": "http://127.0.0.1:9",
            "IOMESH_REQUIRE_ORG": "1",
        }
    )
    assert nc.require_org is True
    assert nc.org == ""
    nc2 = connect_from_env({"IOMESH_URL": "http://127.0.0.1:9"})
    assert nc2.require_org is False


def test_user_agent_override(broker) -> None:
    got_ua: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        got_ua.append(rec["headers"].get("user-agent", ""))
        return 200, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, user_agent="my-agent/1.0"))
    nc.health()
    assert got_ua == ["my-agent/1.0"]


# --- publish ---


def test_publish_base64_payload_and_puback(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v1/streams/EVENTS/publish"
        body = json.loads(rec["body"].decode("utf-8"))
        assert body["subject"] == "dept.engineering.events.demo"
        assert base64.b64decode(body["payload"]) == b'{"hello":"mesh"}'
        assert body.get("partition_key") == "pk1"
        ack = {
            "stream": "EVENTS",
            "seq": 42,
            "subject": "dept.engineering.events.demo",
            "partition": 3,
            "timestamp": "2026-08-10T12:00:00Z",
        }
        return 200, json.dumps(ack).encode("utf-8"), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    ack = nc.publish(
        "EVENTS",
        "dept.engineering.events.demo",
        b'{"hello":"mesh"}',
        partition_key="pk1",
    )
    assert ack.stream == "EVENTS"
    assert ack.seq == 42
    assert ack.subject == "dept.engineering.events.demo"
    assert ack.partition == 3
    assert ack.timestamp is not None


def test_publish_str_payload_encoded_utf8(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        body = json.loads(rec["body"].decode("utf-8"))
        assert base64.b64decode(body["payload"]) == "café".encode()
        return 200, json.dumps({"stream": "S", "seq": 1, "subject": "s"}).encode(), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    ack = nc.publish("S", "s", "café")
    assert ack.seq == 1


def test_publish_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="stream and subject required"):
        nc.publish("", "subj", b"x")
    with pytest.raises(ClientError, match="stream and subject required"):
        nc.publish("S", "", b"x")


# --- create_stream ---


def test_create_stream_201(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "POST"
        assert rec["path"] == "/v1/streams"
        body = json.loads(rec["body"].decode("utf-8"))
        assert body == {"name": "EVENTS", "subjects": ["dept.events.>"]}
        resp = {
            "name": "EVENTS",
            "subjects": ["dept.events.>"],
            "retention": "limits",
            "partitions": 1,
            "messages": 0,
        }
        return 201, json.dumps(resp).encode("utf-8"), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_stream(StreamConfig(name="EVENTS", subjects=["dept.events.>"]))
    assert info is not None
    assert info.name == "EVENTS"
    assert info.subjects == ["dept.events.>"]
    assert info.retention == "limits"
    assert info.partitions == 1


def test_create_stream_409_then_get(broker) -> None:
    posts = {"n": 0}
    gets = {"n": 0}

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "POST" and rec["path"] == "/v1/streams":
            posts["n"] += 1
            return 409, b'{"error":"stream already exists"}', {}
        if rec["method"] == "GET" and rec["path"] == "/v1/streams/EVENTS":
            gets["n"] += 1
            resp = {
                "name": "EVENTS",
                "subjects": ["dept.events.>"],
                "messages": 5,
                "first_seq": 1,
                "last_seq": 5,
            }
            return 200, json.dumps(resp).encode("utf-8"), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_stream(StreamConfig(name="EVENTS", subjects=["dept.events.>"]))
    assert posts["n"] == 1 and gets["n"] == 1
    assert info is not None
    assert info.name == "EVENTS"
    assert info.last_seq == 5


def test_create_stream_409_get_fails_returns_none(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "POST" and rec["path"] == "/v1/streams":
            return 409, b'{"error":"stream already exists"}', {}
        return 404, b'{"error":"not found"}', {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_stream(StreamConfig(name="EVENTS", subjects=["dept.events.>"]))
    assert info is None


def test_create_stream_validation() -> None:
    nc = connect(ConnectOptions(url="http://127.0.0.1:9"))
    with pytest.raises(ClientError, match="stream name required"):
        nc.create_stream(StreamConfig(name="", subjects=["x.>"]))
    with pytest.raises(ClientError, match="subjects required"):
        nc.create_stream(StreamConfig(name="EVENTS", subjects=[]))


# --- list/get streams (org_id) ---


def test_list_streams_org_id_round_trip_and_shared_persist(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "GET"
        assert rec["path"] == "/v1/streams"
        assert rec["headers"].get("x-iomesh-org") == "org_acme"
        body = [
            {
                "name": "ORG_EVENTS",
                "subjects": ["dept.events.>"],
                "org_id": "org_acme",
                "messages": 3,
                "future_field": "ignored",
            },
            {
                "name": "GITHUB_EVENTS",
                "subjects": ["github.>"],
                "org_id": "",
                "messages": 10,
            },
            {
                "name": "OPERATIONAL_EVENTS",
                "subjects": ["ops.>"],
                "messages": 1,
            },
        ]
        return 200, json.dumps(body).encode("utf-8"), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, org="org_acme"))
    streams = nc.list_streams()
    assert [s.name for s in streams] == [
        "ORG_EVENTS",
        "GITHUB_EVENTS",
        "OPERATIONAL_EVENTS",
    ]
    assert streams[0].org_id == "org_acme"
    assert streams[1].org_id == ""  # empty org_id is shared persist
    assert streams[2].org_id == ""  # omitted org_id is shared persist
    assert streams[0].subjects == ["dept.events.>"]
    assert streams[0].messages == 3


def test_list_streams_envelope_org_id(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == "/v1/streams"
        body = {
            "streams": [
                {"name": "ORG_EVENTS", "org_id": "org_acme"},
                {"name": "GITHUB_EVENTS", "org_id": ""},
            ]
        }
        return 200, json.dumps(body).encode("utf-8"), {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    streams = nc.list_streams()
    assert streams[0].org_id == "org_acme"
    assert streams[1].org_id == ""  # empty org_id is shared persist


def test_get_stream_org_id_round_trip_and_shared_persist(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["method"] == "GET"
        if rec["path"] == "/v1/streams/ORG_EVENTS":
            resp = {
                "name": "ORG_EVENTS",
                "subjects": ["dept.events.>"],
                "org_id": "org_acme",
                "messages": 3,
                "future_field": "ignored",
            }
            return 200, json.dumps(resp).encode("utf-8"), {}
        if rec["path"] == "/v1/streams/GITHUB_EVENTS":
            resp = {"name": "GITHUB_EVENTS", "org_id": "", "subjects": ["github.>"]}
            return 200, json.dumps(resp).encode("utf-8"), {}
        if rec["path"] == "/v1/streams/OPERATIONAL_EVENTS":
            resp = {"name": "OPERATIONAL_EVENTS", "subjects": ["ops.>"]}
            return 200, json.dumps(resp).encode("utf-8"), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, org="org_acme"))
    owned = nc.get_stream("ORG_EVENTS")
    assert owned.name == "ORG_EVENTS"
    assert owned.org_id == "org_acme"
    assert owned.subjects == ["dept.events.>"]
    shared = nc.get_stream("GITHUB_EVENTS")
    assert shared.name == "GITHUB_EVENTS"
    assert shared.org_id == ""  # empty org_id is shared persist
    omitted = nc.get_stream("OPERATIONAL_EVENTS")
    assert omitted.name == "OPERATIONAL_EVENTS"
    assert omitted.org_id == ""  # omitted org_id is shared persist


# --- consumers ---


def test_create_consumer_and_fetch_decode_ack(broker) -> None:
    seqs_acked: list[int] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        path = rec["path"]
        method = rec["method"]
        if method == "POST" and path == "/v1/streams/EVENTS/consumers":
            body = json.loads(rec["body"].decode("utf-8"))
            assert body["name"] == "c1"
            assert body.get("filter_subject") == "dept.events.>"
            return (
                201,
                json.dumps(
                    {
                        "stream": "EVENTS",
                        "name": "c1",
                        "ack_floor": 42,
                        "pending_count": 3,
                        "filter_subject": "dept.events.>",
                    }
                ).encode(),
                {},
            )
        if method == "POST" and path == "/v1/streams/EVENTS/consumers/c1/fetch":
            body = json.loads(rec["body"].decode("utf-8"))
            assert body["batch"] == 2
            payload = base64.b64encode(b"hello-mesh").decode("ascii")
            msgs = {
                "messages": [
                    {
                        "stream": "EVENTS",
                        "seq": 7,
                        "subject": "dept.events.demo",
                        "payload": payload,
                        "partition": 0,
                        "headers": {"x-k": "v"},
                    }
                ]
            }
            return 200, json.dumps(msgs).encode(), {}
        if method == "POST" and path == "/v1/streams/EVENTS/consumers/c1/ack":
            body = json.loads(rec["body"].decode("utf-8"))
            seqs_acked.extend(body["seqs"])
            return 204, b"", {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_consumer(
        CreateConsumerConfig(stream="EVENTS", name="c1", filter_subject="dept.events.>")
    )
    assert info.stream == "EVENTS" and info.name == "c1"
    assert info.ack_floor == 42
    assert info.pending_count == 3
    assert info.filter_subject == "dept.events.>"

    msgs = nc.consumer_fetch("EVENTS", "c1", 2)
    assert len(msgs) == 1
    assert msgs[0].seq == 7
    assert msgs[0].data == b"hello-mesh"
    assert msgs[0].subject == "dept.events.demo"
    assert msgs[0].headers.get("x-k") == "v"

    msgs[0].ack()
    assert seqs_acked == [7]


def test_create_consumer_409_conflict(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "POST" and rec["path"] == "/v1/streams/EVENTS/consumers":
            return 409, b'{"error":"exists"}', {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    info = nc.create_consumer(CreateConsumerConfig(stream="EVENTS", name="c1"))
    assert info.stream == "EVENTS" and info.name == "c1"


def test_consumer_nack(broker) -> None:
    nacked: list[int] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"].endswith("/nack"):
            body = json.loads(rec["body"].decode("utf-8"))
            nacked.extend(body["seqs"])
            return 204, b"", {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.consumer_nack("EVENTS", "c1", 9, 10)
    assert nacked == [9, 10]


def test_pull_subscribe_creates_consumer(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/streams/EVENTS/consumers":
            return 201, json.dumps({"stream": "EVENTS", "name": "puller"}).encode(), {}
        if rec["path"].endswith("/fetch"):
            return 200, json.dumps({"messages": []}).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    from iomeshclient import PullSubscribeConfig

    nc = connect(ConnectOptions(url=broker.url))
    sub = nc.pull_subscribe(
        PullSubscribeConfig(stream="EVENTS", consumer="puller", filter="dept.>")
    )
    assert sub.stream == "EVENTS" and sub.consumer == "puller"
    assert sub.fetch(1) == []


# --- list_stream_messages ---


def test_list_stream_messages_ok(broker) -> None:
    from iomeshclient import ListStreamMessagesOptions

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["method"] == "GET" and rec["path"] == "/v1/streams/EVENTS/messages":
            assert "from_seq=1" in rec["query"]
            assert "to_seq=10" in rec["query"]
            assert "limit=50" in rec["query"]
            body = {
                "messages": [
                    {
                        "stream": "EVENTS",
                        "seq": 1,
                        "subject": "dept.events.created",
                        "partition": 0,
                        "payload": base64.b64encode(b"hello").decode("ascii"),
                        "headers": {"k": "v"},
                        "timestamp": "2026-07-01T12:00:00Z",
                    },
                    {
                        "stream": "EVENTS",
                        "seq": 2,
                        "subject": "dept.events.updated",
                        "partition": 1,
                        "payload": "not-valid-base64!!!",
                        "headers": {},
                    },
                ]
            }
            return 200, json.dumps(body).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url, tenant="demo.tenant"))
    msgs = nc.list_stream_messages(
        "EVENTS",
        ListStreamMessagesOptions(from_seq=1, to_seq=10, limit=50),
    )
    assert len(msgs) == 2
    assert msgs[0].seq == 1
    assert msgs[0].subject == "dept.events.created"
    assert msgs[0].payload == b"hello"
    assert msgs[0].headers.get("k") == "v"
    assert msgs[1].payload == b"not-valid-base64!!!"
    assert msgs[1].partition == 1
    last = broker.last()
    assert last["headers"].get("x-iomesh-tenant") == "demo.tenant"


def test_list_stream_messages_defaults_and_cap(broker) -> None:
    from iomeshclient import ListStreamMessagesOptions

    queries: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/v1/streams/EVENTS/messages":
            queries.append(rec["query"])
            return 200, json.dumps({"messages": []}).encode(), {}
        return 404, b"{}", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    assert nc.list_stream_messages("EVENTS") == []
    assert "from_seq=1" in queries[0]
    assert "to_seq=0" in queries[0]
    assert "limit=100" in queries[0]

    nc.list_stream_messages("EVENTS", ListStreamMessagesOptions(limit=5000))
    assert "limit=1000" in queries[1]


def test_list_stream_messages_validation(broker) -> None:
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(ClientError, match="stream name required"):
        nc.list_stream_messages("  ")


def test_list_stream_messages_403(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 403, b'{"error":"forbidden"}', {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(APIError) as ei:
        nc.list_stream_messages("EVENTS")
    assert ei.value.status_code == 403


# --- health / ready ---


def test_health_ok(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        assert rec["path"] == "/health"
        return 200, b"ok", {"Content-Type": "text/plain"}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.health()


def test_health_non_ok(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 503, b"unavailable", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(APIError) as ei:
        nc.health()
    assert ei.value.status_code == 503


def test_ready_ok(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        if rec["path"] == "/ready":
            return 200, b"", {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.ready()


def test_ready_fallback_readyz(broker) -> None:
    paths: list[str] = []

    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        paths.append(rec["path"])
        if rec["path"] == "/readyz":
            return 200, b"", {}
        return 404, b"", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    nc.ready()
    assert paths[:2] == ["/ready", "/readyz"]


def test_ready_both_missing(broker) -> None:
    def handler(rec: dict[str, Any]) -> tuple[int, bytes, dict[str, str]]:
        return 404, b"missing", {}

    broker.set_handler(handler)
    nc = connect(ConnectOptions(url=broker.url))
    with pytest.raises(APIError) as ei:
        nc.ready()
    assert ei.value.status_code == 404


def test_version_constant() -> None:
    assert VERSION == "0.11.1"
