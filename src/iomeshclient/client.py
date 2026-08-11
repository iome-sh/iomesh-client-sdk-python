"""HTTP client for the I/O Mesh broker (/v1 API).

Wire headers: X-IOMesh-Tenant, X-IOMesh-Org, X-IOMesh-Workspace.
Default User-Agent: iomesh-client-sdk-python/<VERSION>.
Connect performs no network I/O.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .errors import APIError, ClientError
from .kv import KVClientMethods
from .memory import MemoryClientMethods

VERSION = "0.2.0"
DEFAULT_FETCH_MAX_WAIT_MS = 5000
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_USER_AGENT = f"iomesh-client-sdk-python/{VERSION}"

TENANT_HEADER = "X-IOMesh-Tenant"
ORG_HEADER = "X-IOMesh-Org"
WORKSPACE_HEADER = "X-IOMesh-Workspace"


@dataclass
class ConnectOptions:
    """Broker connection options. URL required (absolute http/https)."""

    url: str
    timeout: float = DEFAULT_TIMEOUT_SEC
    tenant: str = ""
    org: str = ""
    workspace: str = ""
    bearer_token: str = ""
    user_agent: str = ""


@dataclass
class PubAck:
    stream: str = ""
    seq: int = 0
    subject: str = ""
    partition: int = 0
    timestamp: Optional[datetime] = None


@dataclass
class StreamConfig:
    name: str
    subjects: list[str]
    retention: str = ""
    partitions: int = 0
    description: str = ""


@dataclass
class StreamInfo:
    name: str = ""
    subjects: list[str] = field(default_factory=list)
    retention: str = ""
    partitions: int = 0
    messages: int = 0
    first_seq: int = 0
    last_seq: int = 0
    description: str = ""


@dataclass
class CreateConsumerConfig:
    stream: str
    name: str
    filter_subject: str = ""
    ack_wait_sec: int = 0
    max_deliver: int = 0


@dataclass
class ConsumerInfo:
    stream: str = ""
    name: str = ""


@dataclass
class PullSubscribeConfig:
    stream: str
    consumer: str
    filter: str = ""
    ack_wait_sec: int = 0
    max_deliver: int = 0


@dataclass
class Msg:
    """Fetched message. payload is decoded bytes (broker stores base64)."""

    stream: str
    seq: int
    subject: str
    data: bytes
    partition: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    _sub: Optional[Subscription] = field(default=None, repr=False)

    def ack(self) -> None:
        if self._sub is None:
            raise ClientError("iomeshclient: message has no subscription for ack")
        self._sub.ack(self.seq)

    def nack(self) -> None:
        if self._sub is None:
            raise ClientError("iomeshclient: message has no subscription for nack")
        self._sub.nack(self.seq)


class Client(KVClientMethods, MemoryClientMethods):
    """Talks to an I/O Mesh broker over HTTP (streams, KV, memory helpers)."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        tenant: str = "",
        org: str = "",
        workspace: str = "",
        bearer_token: str = "",
        user_agent: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout if timeout > 0 else DEFAULT_TIMEOUT_SEC
        self.tenant = tenant.strip()
        self.org = org.strip()
        self.workspace = workspace.strip()
        self.bearer_token = bearer_token.strip()
        self.user_agent = (user_agent or DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT

    # --- health ---

    def health(self) -> None:
        """GET /health — raises APIError/ClientError on failure."""
        self._get_status("/health")

    def ready(self) -> None:
        """GET /ready then /readyz — first 2xx wins; both 404 is error."""
        last_404: Optional[Exception] = None
        for path in ("/ready", "/readyz"):
            try:
                self._get_status(path)
                return
            except APIError as e:
                if e.status_code == 404:
                    last_404 = e
                    continue
                raise
        if last_404 is not None:
            raise last_404
        raise ClientError("iomeshclient: ready: http 404")

    # --- streams ---

    def create_stream(self, cfg: StreamConfig) -> Optional[StreamInfo]:
        if not cfg.name:
            raise ClientError("iomeshclient: stream name required")
        if not cfg.subjects:
            raise ClientError("iomeshclient: subjects required")
        body: dict[str, Any] = {"name": cfg.name, "subjects": list(cfg.subjects)}
        if cfg.retention:
            body["retention"] = cfg.retention
        if cfg.partitions:
            body["partitions"] = cfg.partitions
        if cfg.description:
            body["description"] = cfg.description
        try:
            raw = self._do_json("POST", "/v1/streams", body)
            info = (
                _stream_info_from(raw)
                if raw
                else StreamInfo(name=cfg.name, subjects=list(cfg.subjects))
            )
            if not info.name:
                info.name = cfg.name
            return info
        except APIError as e:
            if e.status_code == 409:
                try:
                    return self.get_stream(cfg.name)
                except (APIError, ClientError):
                    return None
            raise

    def ensure_stream(self, cfg: StreamConfig) -> Optional[StreamInfo]:
        return self.create_stream(cfg)

    def get_stream(self, name: str) -> StreamInfo:
        name = name.strip()
        if not name:
            raise ClientError("iomeshclient: stream name required")
        path = f"/v1/streams/{urllib.parse.quote(name, safe='')}"
        raw = self._do_json("GET", path, None)
        if not raw:
            raise ClientError("iomeshclient: empty stream response")
        info = _stream_info_from(raw)
        if not info.name:
            info.name = name
        return info

    def list_streams(self) -> list[StreamInfo]:
        raw = self._do_json("GET", "/v1/streams", None)
        if raw is None:
            return []
        if isinstance(raw, list):
            return [_stream_info_from(x) for x in raw]
        if isinstance(raw, dict) and isinstance(raw.get("streams"), list):
            return [_stream_info_from(x) for x in raw["streams"]]
        raise ClientError("iomeshclient: unexpected list_streams body")

    def delete_stream(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ClientError("iomeshclient: stream name required")
        path = f"/v1/streams/{urllib.parse.quote(name, safe='')}"
        self._do_json("DELETE", path, None)

    # --- publish ---

    def publish(
        self,
        stream: str,
        subject: str,
        payload: bytes | str,
        *,
        partition_key: str = "",
        partition: Optional[int] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> PubAck:
        stream = stream.strip()
        subject = subject.strip()
        if not stream or not subject:
            raise ClientError("iomeshclient: stream and subject required")
        if isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = payload
        body: dict[str, Any] = {
            "subject": subject,
            "payload": base64.b64encode(data).decode("ascii"),
        }
        if partition_key:
            body["partition_key"] = partition_key
        if partition is not None:
            body["partition"] = partition
        if headers:
            body["headers"] = dict(headers)
        path = f"/v1/streams/{urllib.parse.quote(stream, safe='')}/publish"
        raw = self._do_json("POST", path, body) or {}
        ts = _parse_ts(raw.get("timestamp"))
        return PubAck(
            stream=str(raw.get("stream") or stream),
            seq=int(raw.get("seq") or 0),
            subject=str(raw.get("subject") or subject),
            partition=int(raw.get("partition") or 0),
            timestamp=ts,
        )

    # --- consumers ---

    def create_consumer(self, cfg: CreateConsumerConfig) -> ConsumerInfo:
        if not cfg.stream or not cfg.name:
            raise ClientError("iomeshclient: stream and name required")
        req: dict[str, Any] = {"name": cfg.name}
        if cfg.filter_subject:
            req["filter_subject"] = cfg.filter_subject
        if cfg.ack_wait_sec:
            req["ack_wait_sec"] = cfg.ack_wait_sec
        if cfg.max_deliver:
            req["max_deliver"] = cfg.max_deliver
        path = f"/v1/streams/{urllib.parse.quote(cfg.stream, safe='')}/consumers"
        try:
            raw = self._do_json("POST", path, req) or {}
            info = ConsumerInfo(
                stream=str(raw.get("stream") or cfg.stream),
                name=str(raw.get("name") or cfg.name),
            )
            return info
        except APIError as e:
            if e.status_code == 409:
                return ConsumerInfo(stream=cfg.stream, name=cfg.name)
            raise

    def ensure_consumer(self, cfg: CreateConsumerConfig) -> ConsumerInfo:
        return self.create_consumer(cfg)

    def pull_subscribe(self, cfg: PullSubscribeConfig) -> Subscription:
        if not cfg.stream or not cfg.consumer:
            raise ClientError("iomeshclient: stream and consumer required")
        info = self.create_consumer(
            CreateConsumerConfig(
                stream=cfg.stream,
                name=cfg.consumer,
                filter_subject=cfg.filter,
                ack_wait_sec=cfg.ack_wait_sec,
                max_deliver=cfg.max_deliver,
            )
        )
        return Subscription(client=self, stream=cfg.stream, consumer=cfg.consumer, info=info)

    def consumer_fetch(
        self,
        stream: str,
        consumer: str,
        batch: int,
        *,
        max_wait_ms: int = DEFAULT_FETCH_MAX_WAIT_MS,
    ) -> list[Msg]:
        if not stream or not consumer:
            raise ClientError("iomeshclient: stream and consumer required")
        if batch <= 0:
            raise ClientError("iomeshclient: batch must be > 0")
        path = (
            f"/v1/streams/{urllib.parse.quote(stream, safe='')}"
            f"/consumers/{urllib.parse.quote(consumer, safe='')}/fetch"
        )
        raw = self._do_json(
            "POST",
            path,
            {"batch": batch, "max_wait_ms": int(max_wait_ms)},
        ) or {}
        messages = raw.get("messages") if isinstance(raw, dict) else None
        if not messages:
            return []
        sub = Subscription(
            client=self,
            stream=stream,
            consumer=consumer,
            info=ConsumerInfo(stream=stream, name=consumer),
        )
        out: list[Msg] = []
        for m in messages:
            payload_b64 = m.get("payload") or ""
            try:
                data = base64.b64decode(payload_b64)
            except Exception as e:
                raise ClientError(f"iomeshclient: decode payload seq {m.get('seq')}: {e}") from e
            out.append(
                Msg(
                    stream=str(m.get("stream") or stream),
                    seq=int(m.get("seq") or 0),
                    subject=str(m.get("subject") or ""),
                    data=data,
                    partition=int(m.get("partition") or 0),
                    headers=dict(m.get("headers") or {}),
                    _sub=sub,
                )
            )
        return out

    def consumer_ack(self, stream: str, consumer: str, *seqs: int) -> None:
        if not stream or not consumer:
            raise ClientError("iomeshclient: stream and consumer required")
        if not seqs:
            raise ClientError("iomeshclient: seqs required")
        path = (
            f"/v1/streams/{urllib.parse.quote(stream, safe='')}"
            f"/consumers/{urllib.parse.quote(consumer, safe='')}/ack"
        )
        self._do_json("POST", path, {"seqs": list(seqs)})

    def consumer_nack(self, stream: str, consumer: str, *seqs: int) -> None:
        if not stream or not consumer:
            raise ClientError("iomeshclient: stream and consumer required")
        if not seqs:
            raise ClientError("iomeshclient: seqs required")
        path = (
            f"/v1/streams/{urllib.parse.quote(stream, safe='')}"
            f"/consumers/{urllib.parse.quote(consumer, safe='')}/nack"
        )
        self._do_json("POST", path, {"seqs": list(seqs)})

    # --- HTTP ---

    def _auth_headers(self) -> dict[str, str]:
        h = {"User-Agent": self.user_agent}
        if self.tenant:
            h[TENANT_HEADER] = self.tenant
        if self.org:
            h[ORG_HEADER] = self.org
        if self.workspace:
            h[WORKSPACE_HEADER] = self.workspace
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def _get_status(self, path: str) -> None:
        url = self.base_url + path
        req = urllib.request.Request(url, method="GET", headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if 200 <= resp.status < 300:
                    return
                body = resp.read().decode("utf-8", errors="replace")
                raise APIError(resp.status, body.strip())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise APIError(e.code, body.strip()) from e
        except urllib.error.URLError as e:
            raise ClientError(f"iomeshclient: request failed: {e}") from e

    def _do_json(self, method: str, path: str, req_body: Any) -> Any:
        url = self.base_url + path
        headers = self._auth_headers()
        data: Optional[bytes] = None
        if req_body is not None:
            data = json.dumps(req_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not (200 <= resp.status < 300):
                    raise APIError(resp.status, raw.decode("utf-8", errors="replace").strip())
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise APIError(e.code, body.strip()) from e
        except urllib.error.URLError as e:
            raise ClientError(f"iomeshclient: request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise ClientError(f"iomeshclient: invalid JSON response: {e}") from e


@dataclass
class Subscription:
    client: Client
    stream: str
    consumer: str
    info: ConsumerInfo = field(default_factory=ConsumerInfo)

    def fetch(self, batch: int, *, max_wait_ms: int = DEFAULT_FETCH_MAX_WAIT_MS) -> list[Msg]:
        return self.client.consumer_fetch(
            self.stream, self.consumer, batch, max_wait_ms=max_wait_ms
        )

    def ack(self, *seqs: int) -> None:
        self.client.consumer_ack(self.stream, self.consumer, *seqs)

    def nack(self, *seqs: int) -> None:
        self.client.consumer_nack(self.stream, self.consumer, *seqs)


def connect(options: ConnectOptions) -> Client:
    """Return a client for the broker. No network I/O is performed."""
    raw = (options.url or "").strip().rstrip("/")
    if not raw:
        raise ClientError("iomeshclient: URL required")
    _validate_broker_url(raw)
    return Client(
        base_url=raw,
        timeout=options.timeout,
        tenant=options.tenant,
        org=options.org,
        workspace=options.workspace,
        bearer_token=options.bearer_token,
        user_agent=options.user_agent,
    )


def _validate_broker_url(raw: str) -> None:
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ClientError(
            f'iomeshclient: unsupported URL scheme "{parsed.scheme}" (want http or https)'
        )
    if not parsed.netloc:
        raise ClientError("iomeshclient: URL host required")
    if parsed.username is not None or parsed.password is not None:
        raise ClientError("iomeshclient: URL must not contain userinfo; use bearer_token")


def _stream_info_from(raw: Any) -> StreamInfo:
    if not isinstance(raw, dict):
        return StreamInfo()
    subjects = raw.get("subjects") or []
    if not isinstance(subjects, list):
        subjects = []
    return StreamInfo(
        name=str(raw.get("name") or ""),
        subjects=[str(s) for s in subjects],
        retention=str(raw.get("retention") or ""),
        partitions=int(raw.get("partitions") or 0),
        messages=int(raw.get("messages") or 0),
        first_seq=int(raw.get("first_seq") or 0),
        last_seq=int(raw.get("last_seq") or 0),
        description=str(raw.get("description") or ""),
    )


def _parse_ts(val: Any) -> Optional[datetime]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)
    s = str(val).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
