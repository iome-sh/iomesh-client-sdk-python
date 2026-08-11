"""KV format helpers — pure operator/CLI views (no network I/O).

Wire parity with Go ``iomeshclient`` kv_format.go:

- ``format_put_result`` multi-line put outcome
- ``format_bucket_info`` multi-line bucket detail (always-emit knobs)
- ``format_kv_entry`` multi-line entry detail (always-emit created_at)
- ``format_kv_keys`` compact key listing

Honesty: MIT edge · Beta · operator diagnostics formatters · not product GA.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from unicodedata import category

if TYPE_CHECKING:
    from .kv import BucketInfo, KVEntry, PutResult


def format_put_result(r: PutResult) -> str:
    """Multi-line view for one Put outcome (Go FormatPutResult).

    Pure helper with no network I/O.
    """
    lines = [
        "iomesh kv put",
        f"bucket:     {r.bucket}",
        f"key:        {r.key}",
        f"revision:   {r.revision}",
    ]
    return "\n".join(lines) + "\n"


def format_bucket_info(info: BucketInfo) -> str:
    """Multi-line view for one KV bucket (Go FormatBucketInfo).

    Always emits optional knobs for scrapers: history, max_bytes, ttl_seconds
    (0 / blank when unset; None max_bytes/ttl → blank value, not omitted).
    """
    lines = [
        "iomesh kv bucket",
        f"name:         {info.name}",
        f"history:      {info.history}",
    ]
    max_bytes: Optional[int] = getattr(info, "max_bytes", None)
    if max_bytes is not None:
        lines.append(f"max_bytes:    {max_bytes}")
    else:
        lines.append("max_bytes:    ")
    ttl: Optional[int] = getattr(info, "ttl_seconds", None)
    if ttl is not None:
        lines.append(f"ttl_seconds:  {ttl}")
    else:
        lines.append("ttl_seconds:  ")
    return "\n".join(lines) + "\n"


def format_kv_entry(e: KVEntry) -> str:
    """Multi-line view for one KV entry (Go FormatKVEntry).

    Value is shown as UTF-8 text when printable; otherwise as a byte-length
    note with a short hex preview. Always emits created_at for scrapers
    (RFC3339 UTC when set; blank value when unset).
    """
    created = ""
    created_at = getattr(e, "created_at", None)
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created = created_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            created = created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    value = e.value if isinstance(getattr(e, "value", None), (bytes, bytearray)) else b""
    lines = [
        "iomesh kv entry",
        f"bucket:     {e.bucket}",
        f"key:        {e.key}",
        f"revision:   {e.revision}",
        f"created_at: {created}",
        f"value:      {_format_kv_value(bytes(value), 256)}",
    ]
    return "\n".join(lines) + "\n"


def format_kv_keys(bucket: str, keys: Optional[list[str]]) -> str:
    """Compact key listing for operator discovery (Go FormatKVKeys).

    Pure helper with no network I/O. Caps at 50 keys then ellipsis.
    """
    if keys is None:
        keys = []
    lines = [f"iomesh kv keys bucket={bucket} count={len(keys)}"]
    if not keys:
        lines.append("(no keys)")
        return "\n".join(lines) + "\n"
    for i, k in enumerate(keys):
        if i >= 50:
            lines.append(f"… ({len(keys) - 50} more)")
            break
        lines.append(_truncate(k, 96))
    return "\n".join(lines) + "\n"


def _format_kv_value(v: bytes, max_runes: int) -> str:
    if len(v) == 0:
        return '""'
    if _is_mostly_printable_utf8(v):
        s = v.decode("utf-8")
        if len(s) > max_runes:
            return _truncate(s, max_runes)
        return s
    preview = v[:16]
    return f"<{len(v)} bytes hex={preview.hex()}…>"


def _is_mostly_printable_utf8(v: bytes) -> bool:
    try:
        s = v.decode("utf-8")
    except UnicodeDecodeError:
        return False
    for ch in s:
        if ch in "\n\r\t":
            continue
        # unicode.IsPrint equivalent: letters, numbers, punctuation, symbols, spaces
        cat = category(ch)
        if cat.startswith("C"):  # control / other
            return False
    return True


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    if n <= 1:
        return s[:n]
    return s[: n - 1] + "…"
