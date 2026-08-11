"""Stream format helpers — pure views matching Go FormatStreams / FormatStreamDetail."""

from __future__ import annotations

from datetime import datetime, timezone

from iomeshclient import StreamInfo, format_stream_detail, format_streams


def test_format_streams_empty() -> None:
    out = format_streams([])
    assert "count=0" in out
    assert "(no streams)" in out


def test_format_streams_one() -> None:
    out = format_streams(
        [
            StreamInfo(
                name="EVENTS",
                subjects=["dept.ops.>", "dept.sre.>"],
                messages=42,
                first_seq=1,
                last_seq=42,
                partitions=3,
                retention="limits",
            )
        ]
    )
    assert "count=1" in out
    assert "EVENTS" in out
    assert "42" in out
    assert "limits" in out
    assert "dept.ops.>" in out


def test_format_streams_cap_50() -> None:
    streams = [StreamInfo(name=f"s{i}", messages=i) for i in range(55)]
    out = format_streams(streams)
    assert "… (5 more)" in out


def test_format_stream_detail_fields() -> None:
    detail = format_stream_detail(
        StreamInfo(
            name="EVENTS",
            description="org heartbeats",
            retention="limits",
            partitions=2,
            max_msgs=1000,
            max_age_sec=3600,
            messages=10,
            first_seq=1,
            last_seq=10,
            created_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
            subjects=["dept.ops.>", "dept.sre.>"],
        )
    )
    for needle in (
        "iomesh stream",
        "name:        EVENTS",
        "description: org heartbeats",
        "retention:   limits",
        "partitions:  2",
        "max_msgs:    1000",
        "max_age_sec: 3600",
        "messages:    10",
        "first_seq:   1",
        "last_seq:    10",
        "created_at:  2026-07-01T12:00:00Z",
        "  - dept.ops.>",
        "  - dept.sre.>",
    ):
        assert needle in detail, f"missing {needle!r} in:\n{detail}"


def test_format_stream_detail_empty_always_emit() -> None:
    detail = format_stream_detail(StreamInfo(name="EMPTY"))
    for needle in (
        "name:        EMPTY",
        "description: ",
        "retention:   ",
        "partitions:  0",
        "max_msgs:    \n",
        "max_age_sec: \n",
        "created_at:  \n",
        "  (none)",
    ):
        assert needle in detail, f"missing {needle!r} in:\n{detail}"
    assert "max_msgs:    0" not in detail


def test_format_stream_detail_subjects_cap() -> None:
    subjects = [f"subj.{i}" for i in range(30)]
    detail = format_stream_detail(StreamInfo(name="BIG", subjects=subjects))
    assert "… +6 more" in detail
