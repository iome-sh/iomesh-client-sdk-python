"""Message / consumer format helpers — pure views matching Go FormatMsg family."""

from __future__ import annotations

from iomeshclient import ConsumerInfo, Msg, format_consumer_info, format_msg, format_msgs


def test_format_msg_nil() -> None:
    assert format_msg(None) == "iomesh msg (nil)\n"


def test_format_msg_fields() -> None:
    m = Msg(stream="S", seq=42, subject="dept.events.x", data=b"hello")
    out = format_msg(m)
    assert out == "iomesh msg seq=42 subject=dept.events.x bytes=5\n"
    for needle in ("seq=42", "subject=dept.events.x", "bytes=5"):
        assert needle in out


def test_format_msgs_empty() -> None:
    assert format_msgs(None) == "iomesh msgs count=0\n"
    assert format_msgs([]) == "iomesh msgs count=0\n"


def test_format_msgs_multi() -> None:
    msgs = [
        Msg(stream="S", seq=1, subject="dept.events.a", data=b"hi"),
        Msg(stream="S", seq=2, subject="dept.events.b", data=b"xyz"),
    ]
    out = format_msgs(msgs)
    assert out.startswith("iomesh msgs count=2\n")
    for needle in (
        "seq=1",
        "subject=dept.events.a",
        "bytes=2",
        "seq=2",
        "subject=dept.events.b",
        "bytes=3",
    ):
        assert needle in out, f"missing {needle!r} in {out!r}"
    assert format_msg(msgs[0]).rstrip("\n") in out
    assert format_msg(msgs[1]).rstrip("\n") in out


def test_format_consumer_info_fields() -> None:
    out = format_consumer_info(
        ConsumerInfo(
            stream="EVENTS",
            name="worker-1",
            ack_floor=42,
            pending_count=3,
            filter_subject="dept.events.>",
        )
    )
    for needle in (
        "iomesh consumer",
        "stream:          EVENTS",
        "name:            worker-1",
        "ack_floor:       42",
        "pending_count:   3",
        "filter_subject:  dept.events.>",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"


def test_format_consumer_info_empty_filter_always_emit() -> None:
    out = format_consumer_info(ConsumerInfo(stream="S", name="c"))
    for needle in (
        "stream:          S",
        "name:            c",
        "ack_floor:       0",
        "pending_count:   0",
        "filter_subject:  \n",
    ):
        assert needle in out, f"missing {needle!r} in:\n{out}"
