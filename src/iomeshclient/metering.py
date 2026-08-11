"""Metering helpers — dept.* organizational heartbeats / ops pulse (remote metering).

Wire parity with Go ``iomeshclient`` metering.go:

- ``emit_dept_event`` → ``POST /v1/streams/dept/publish`` (subject = event type)
- ``emit_llm_call`` → wraps with type ``dept.agent.llm_call`` + structured payload
- Multi-tenant org/workspace/tenant enriched into payload when unset on the body

Public lexicon: **heartbeat / pulse** only (org-tool events agents consume).
Honesty: MIT edge · Beta · dual_write OFF elsewhere · not invent GA · not freemium palace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from .errors import ClientError

if TYPE_CHECKING:
    from .client import PubAck

# Stream name for operational dept.* organizational heartbeats.
STREAM_DEPT = "dept"

# Event type for platform remote LLM call metering dashboards.
TYPE_DEPT_AGENT_LLM_CALL = "dept.agent.llm_call"


@dataclass
class DeptEvent:
    """Lightweight organizational heartbeat / ops pulse on the dept.* family.

    Wire shape matches Go ``DeptEvent`` / iomesh-tui internal metering for
    platform remote dashboards. Public lexicon: heartbeat / pulse only.
    """

    type: str = ""  # e.g. dept.agent.llm_call
    ts: Optional[datetime] = None
    tenant: str = ""
    session_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMCallEvent:
    """Structured payload for ``dept.agent.llm_call`` (remote metering dashboards).

    Org / workspace are also sent as Connect headers; fields here mirror
    iomesh-tui RecordLLMCall payload for consumers that only read the body.
    """

    tenant: str = ""
    session_id: str = ""
    model: str = ""
    model_id: str = ""
    org: str = ""
    workspace: str = ""
    duration_ms: int = 0
    attempts: int = 0
    fallback: bool = False
    est_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str = ""  # optional redacted error string
    extra: dict[str, Any] = field(default_factory=dict)


class MeteringClientMethods:
    """Mixin: Client metering methods (Go EmitDeptEvent / EmitLLMCall)."""

    def emit_dept_event(self, ev: DeptEvent) -> PubAck:
        """Publish a structured dept.* organizational heartbeat (ops pulse).

        ``POST /v1/streams/dept/publish``. Subject defaults to ``ev.type``
        (e.g. ``dept.agent.llm_call``). Tenant defaults to client tenant.
        Agents and dashboards pull these org-tool events.
        """
        type_ = (ev.type or "").strip()
        if not type_:
            raise ClientError("iomeshclient: type required")

        ts = ev.ts
        if ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        tenant = (ev.tenant or "").strip()
        if not tenant:
            tenant = (getattr(self, "tenant", "") or "").strip()

        payload: dict[str, Any] = dict(ev.payload) if ev.payload else {}

        # Enrich multi-tenant fields when configured on the client (parity with Go).
        org = (getattr(self, "org", "") or "").strip()
        if org and "org" not in payload:
            payload["org"] = org
        ws = (getattr(self, "workspace", "") or "").strip()
        if ws and "workspace" not in payload:
            payload["workspace"] = ws
        if tenant and "tenant" not in payload:
            payload["tenant"] = tenant

        body: dict[str, Any] = {
            "type": type_,
            "ts": _format_ts(ts),
        }
        if tenant:
            body["tenant"] = tenant
        session_id = (ev.session_id or "").strip()
        if session_id:
            body["session_id"] = session_id
        if payload:
            body["payload"] = payload

        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self.publish(STREAM_DEPT, type_, raw)  # type: ignore[attr-defined]

    def emit_llm_call(self, call: LLMCallEvent) -> PubAck:
        """Publish ``dept.agent.llm_call`` for platform remote metering dashboards.

        Uses the same multi-tenant headers as other client methods
        (``ConnectOptions.org`` / ``workspace``).
        """
        payload: dict[str, Any] = {
            "model": call.model,
            "model_id": call.model_id,
            "duration_ms": int(call.duration_ms),
            "attempts": int(call.attempts),
            "fallback": bool(call.fallback),
            "est_usd": float(call.est_usd),
            "tokens": {
                "prompt": int(call.prompt_tokens),
                "completion": int(call.completion_tokens),
                "total": int(call.total_tokens),
            },
        }
        tenant = (call.tenant or "").strip()
        if tenant:
            payload["tenant"] = tenant
        org = (call.org or "").strip()
        if org:
            payload["org"] = org
        ws = (call.workspace or "").strip()
        if ws:
            payload["workspace"] = ws
        err_msg = (call.error or "").strip()
        if err_msg:
            payload["error"] = err_msg
        for k, v in (call.extra or {}).items():
            if not k:
                continue
            payload[k] = v

        return self.emit_dept_event(
            DeptEvent(
                type=TYPE_DEPT_AGENT_LLM_CALL,
                tenant=call.tenant,
                session_id=call.session_id,
                payload=payload,
            )
        )


def _format_ts(ts: datetime) -> str:
    """RFC3339 UTC with Z suffix (Go time.Time JSON shape)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    # Match common Go encoding: 2006-01-02T15:04:05.999999999Z (trim trailing zeros lightly)
    s = ts.isoformat(timespec="microseconds")
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s
