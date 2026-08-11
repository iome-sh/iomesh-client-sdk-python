"""Stream format helpers — pure operator/CLI views (no network I/O).

Wire parity with Go ``iomeshclient`` streams_format.go:

- ``format_streams`` compact table (name, msgs, subjects)
- ``format_stream_detail`` multi-line single-stream view

Honesty: MIT edge · Beta · operator diagnostics formatters · not product GA.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .client import StreamInfo


def format_streams(streams: list[StreamInfo]) -> str:
    """Render a compact table for operator discovery (Go FormatStreams).

    Pure helper with no network I/O. Caps at 50 rows then ellipsis.
    """
    lines = [f"iomesh streams count={len(streams)}"]
    if not streams:
        lines.append("(no streams)")
        return "\n".join(lines) + "\n"
    lines.append(
        f"{'NAME':<24} {'MSGS':>8} {'FIRST':>8} {'LAST':>8} {'PART':>5} "
        f"{'RETENTION':<10} SUBJECTS"
    )
    for i, s in enumerate(streams):
        if i >= 50:
            lines.append(f"… ({len(streams) - 50} more)")
            break
        subj = ",".join(s.subjects or [])
        lines.append(
            f"{_truncate(s.name, 24):<24} {s.messages:8d} {s.first_seq:8d} "
            f"{s.last_seq:8d} {s.partitions:5d} {_truncate(s.retention, 10):<10} "
            f"{_truncate(subj, 48)}"
        )
    return "\n".join(lines) + "\n"


def format_stream_detail(s: StreamInfo) -> str:
    """Multi-line view for one stream (Go FormatStreamDetail).

    Always emits optional knobs for scrapers: description, retention,
    partitions, max_msgs, max_age_sec, created_at, subjects (empty / zero /
    blank when unset; None max_* → blank value, not omitted).
    """
    lines = [
        "iomesh stream",
        f"name:        {s.name}",
        f"description: {s.description}",
        f"retention:   {s.retention}",
        f"partitions:  {s.partitions}",
    ]
    max_msgs: Optional[int] = getattr(s, "max_msgs", None)
    if max_msgs is not None:
        lines.append(f"max_msgs:    {max_msgs}")
    else:
        lines.append("max_msgs:    ")
    max_age_sec: Optional[int] = getattr(s, "max_age_sec", None)
    if max_age_sec is not None:
        lines.append(f"max_age_sec: {max_age_sec}")
    else:
        lines.append("max_age_sec: ")
    lines.append(f"messages:    {s.messages}")
    lines.append(f"first_seq:   {s.first_seq}")
    lines.append(f"last_seq:    {s.last_seq}")
    created = ""
    created_at = getattr(s, "created_at", None)
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created = created_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            created = created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"created_at:  {created}")
    lines.append("subjects:")
    subjects = s.subjects or []
    if not subjects:
        lines.append("  (none)")
    else:
        for i, sub in enumerate(subjects):
            if i >= 24:
                lines.append(f"  … +{len(subjects) - 24} more")
                break
            lines.append(f"  - {sub}")
    return "\n".join(lines) + "\n"


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    if n <= 1:
        return s[:n]
    return s[: n - 1] + "…"
