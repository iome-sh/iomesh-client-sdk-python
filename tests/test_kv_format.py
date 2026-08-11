"""KV format helpers — pure views matching Go FormatPutResult / FormatBucketInfo / etc."""

from __future__ import annotations

from datetime import datetime, timezone

from iomeshclient import (
    BucketInfo,
    KVEntry,
    PutResult,
    format_bucket_info,
    format_kv_entry,
    format_kv_keys,
    format_put_result,
)


def test_format_put_result_fields() -> None:
    out = format_put_result(
        PutResult(bucket="agent-state", key="worker-1.checkpoint", revision=7)
    )
    for needle in (
        "iomesh kv put",
        "bucket:     agent-state",
        "key:        worker-1.checkpoint",
        "revision:   7",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"


def test_format_bucket_info_fields() -> None:
    out = format_bucket_info(
        BucketInfo(name="agent-state", history=5, max_bytes=1024, ttl_seconds=3600)
    )
    for needle in (
        "iomesh kv bucket",
        "name:         agent-state",
        "history:      5",
        "max_bytes:    1024",
        "ttl_seconds:  3600",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"


def test_format_bucket_info_empty_always_emit() -> None:
    out = format_bucket_info(BucketInfo(name="agent-state"))
    for needle in (
        "iomesh kv bucket",
        "name:         agent-state",
        "history:      0\n",
        "max_bytes:    \n",
        "ttl_seconds:  \n",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"
    assert "max_bytes:    0" not in out
    assert "ttl_seconds:  0" not in out


def test_format_kv_entry_fields() -> None:
    out = format_kv_entry(
        KVEntry(
            bucket="agent-state",
            key="worker-1.checkpoint",
            value=b"seq=42",
            revision=3,
            created_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
    )
    for needle in (
        "iomesh kv entry",
        "bucket:     agent-state",
        "key:        worker-1.checkpoint",
        "revision:   3",
        "created_at: 2026-07-01T12:00:00Z",
        "seq=42",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"


def test_format_kv_entry_empty_created_at_always_emit() -> None:
    out = format_kv_entry(
        KVEntry(bucket="b", key="k", value=b"v", revision=1)
    )
    assert "created_at: \n" in out
    for line in out.splitlines():
        if line.startswith("created_at:"):
            val = line[len("created_at:") :].strip()
            assert val == "", f"created_at should be blank when unset, got {val!r}"


def test_format_kv_entry_binary_value() -> None:
    out = format_kv_entry(KVEntry(bucket="b", key="k", value=bytes([0x00, 0x01, 0xFF])))
    assert "3 bytes" in out
    assert "hex=" in out


def test_format_kv_entry_empty_value() -> None:
    out = format_kv_entry(KVEntry(bucket="b", key="k", value=b""))
    assert 'value:      ""' in out


def test_format_kv_keys_empty() -> None:
    out = format_kv_keys("agent-state", None)
    assert "bucket=agent-state" in out
    assert "count=0" in out
    assert "(no keys)" in out
    out = format_kv_keys("agent-state", [])
    assert "count=0" in out
    assert "(no keys)" in out


def test_format_kv_keys_list() -> None:
    out = format_kv_keys(
        "agent-state",
        ["worker-1.checkpoint", "worker-2.checkpoint"],
    )
    assert out.startswith("iomesh kv keys bucket=agent-state")
    assert "count=2" in out
    assert "worker-1.checkpoint" in out
    assert "worker-2.checkpoint" in out


def test_format_kv_keys_cap_50() -> None:
    keys = [f"k{i}" for i in range(55)]
    out = format_kv_keys("b", keys)
    assert "… (5 more)" in out
