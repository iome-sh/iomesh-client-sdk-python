"""KV bucket helpers — wire parity with Go iomeshclient KV plane.

POST /v1/kv/{name} · PUT/GET/DELETE /v1/kv/{bucket}/{key} · GET list with prefix.
409 create/ensure is success (name-only BucketInfo). Not control-plane GA.
"""

from __future__ import annotations

import base64
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .errors import APIError, ClientError


@dataclass
class KVEntry:
    """Versioned key-value record from the broker."""

    bucket: str = ""
    key: str = ""
    value: bytes = b""
    revision: int = 0
    created_at: Optional[datetime] = None


@dataclass
class BucketInfo:
    """Broker KV bucket metadata from create responses."""

    name: str = ""
    max_bytes: Optional[int] = None
    history: int = 0
    ttl_seconds: Optional[int] = None


@dataclass
class PutResult:
    """Outcome of put."""

    bucket: str = ""
    key: str = ""
    revision: int = 0


@dataclass
class CreateBucketConfig:
    """Optional knobs for a new KV bucket."""

    max_bytes: Optional[int] = None
    history: int = 0
    ttl_seconds: Optional[int] = None


class KVClientMethods:
    """Mixin: Client KV methods (Go CreateBucket / Put / Get / Delete / ListKeys)."""

    def create_bucket(
        self,
        name: str,
        cfg: Optional[CreateBucketConfig] = None,
    ) -> BucketInfo:
        """POST /v1/kv/{name}. 409 conflict → success with name-only BucketInfo."""
        name = (name or "").strip()
        if not name:
            raise ClientError("iomeshclient: bucket name required")
        body: Optional[dict[str, Any]] = None
        if cfg is not None:
            body = {}
            if cfg.max_bytes is not None:
                body["max_bytes"] = cfg.max_bytes
            if cfg.history:
                body["history"] = cfg.history
            if cfg.ttl_seconds is not None:
                body["ttl_seconds"] = cfg.ttl_seconds
            if not body:
                body = None
        path = f"/v1/kv/{urllib.parse.quote(name, safe='')}"
        try:
            raw = self._do_json("POST", path, body)  # type: ignore[attr-defined]
            info = _bucket_info_from(raw)
            if not info.name:
                info.name = name
            return info
        except APIError as e:
            if e.status_code == 409:
                return BucketInfo(name=name)
            raise

    def ensure_bucket(
        self,
        name: str,
        cfg: Optional[CreateBucketConfig] = None,
    ) -> BucketInfo:
        """Create bucket if missing (CreateBucket semantics; 409 is success)."""
        return self.create_bucket(name, cfg)

    def put(self, bucket: str, key: str, value: bytes | str) -> PutResult:
        """PUT /v1/kv/{bucket}/{key} body {"value": base64} → PutResult."""
        bucket = (bucket or "").strip()
        key = (key or "").strip()
        if not bucket:
            raise ClientError("iomeshclient: bucket required")
        if not key:
            raise ClientError("iomeshclient: key required")
        if isinstance(value, str):
            data = value.encode("utf-8")
        else:
            data = value if value is not None else b""
        body = {"value": base64.b64encode(data).decode("ascii")}
        path = _kv_key_path(bucket, key)
        raw = self._do_json("PUT", path, body) or {}  # type: ignore[attr-defined]
        result = PutResult(
            bucket=str(raw.get("bucket") or ""),
            key=str(raw.get("key") or ""),
            revision=int(raw.get("revision") or 0),
        )
        if not result.bucket:
            result.bucket = bucket
        if not result.key:
            result.key = key
        return result

    def get(self, bucket: str, key: str) -> KVEntry:
        """GET /v1/kv/{bucket}/{key}. Value: JSON string → base64 decode; graceful fallback."""
        bucket = (bucket or "").strip()
        key = (key or "").strip()
        if not bucket:
            raise ClientError("iomeshclient: bucket required")
        if not key:
            raise ClientError("iomeshclient: key required")
        path = _kv_key_path(bucket, key)
        raw = self._do_json("GET", path, None)  # type: ignore[attr-defined]
        if not isinstance(raw, dict):
            raise ClientError("iomeshclient: unexpected kv get body")
        entry = KVEntry(
            bucket=str(raw.get("bucket") or bucket),
            key=str(raw.get("key") or key),
            value=_decode_kv_value(raw.get("value")),
            revision=int(raw.get("revision") or 0),
            created_at=_parse_ts(raw.get("created_at")),
        )
        return entry

    def delete(self, bucket: str, key: str) -> None:
        """DELETE /v1/kv/{bucket}/{key}."""
        bucket = (bucket or "").strip()
        key = (key or "").strip()
        if not bucket:
            raise ClientError("iomeshclient: bucket required")
        if not key:
            raise ClientError("iomeshclient: key required")
        path = _kv_key_path(bucket, key)
        self._do_json("DELETE", path, None)  # type: ignore[attr-defined]

    def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        """GET /v1/kv/{bucket}?prefix=… → list of keys."""
        bucket = (bucket or "").strip()
        if not bucket:
            raise ClientError("iomeshclient: bucket required")
        path = f"/v1/kv/{urllib.parse.quote(bucket, safe='')}"
        if prefix:
            path += f"?prefix={urllib.parse.quote(prefix, safe='')}"
        raw = self._do_json("GET", path, None)  # type: ignore[attr-defined]
        if raw is None:
            return []
        if isinstance(raw, dict):
            keys = raw.get("keys")
            if keys is None:
                return []
            if isinstance(keys, list):
                return [str(k) for k in keys]
        raise ClientError("iomeshclient: unexpected list_keys body")


def _kv_key_path(bucket: str, key: str) -> str:
    return (
        f"/v1/kv/{urllib.parse.quote(bucket, safe='')}"
        f"/{urllib.parse.quote(key, safe='')}"
    )


def _bucket_info_from(raw: Any) -> BucketInfo:
    if not isinstance(raw, dict):
        return BucketInfo()
    max_bytes = raw.get("max_bytes")
    ttl = raw.get("ttl_seconds")
    return BucketInfo(
        name=str(raw.get("name") or ""),
        max_bytes=int(max_bytes) if max_bytes is not None else None,
        history=int(raw.get("history") or 0),
        ttl_seconds=int(ttl) if ttl is not None else None,
    )


def _decode_kv_value(val: Any) -> bytes:
    """Decode broker value field.

    Wire: JSON string is typically standard base64 (Go []byte encoding).
    If already bytes, return as-is. If base64 decode fails, treat string as UTF-8.
    """
    if val is None:
        return b""
    if isinstance(val, (bytes, bytearray)):
        return bytes(val)
    if isinstance(val, list):
        # unusual: JSON array of ints
        try:
            return bytes(int(x) & 0xFF for x in val)
        except (TypeError, ValueError):
            return b""
    if isinstance(val, str):
        if val == "":
            return b""
        try:
            return base64.b64decode(val, validate=False)
        except Exception:
            return val.encode("utf-8")
    # numbers / other — best-effort string
    return str(val).encode("utf-8")


def _parse_ts(val: Any) -> Optional[datetime]:
    from .client import _parse_ts as _client_parse_ts

    return _client_parse_ts(val)
