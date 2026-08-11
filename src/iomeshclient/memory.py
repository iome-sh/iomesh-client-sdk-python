"""Memory helpers — edge async ingest + optional sync dual_write.

Honesty:
- dual_write **OFF** by default (sync=False): local-primary MEMORY_INGEST publish only
- Not freemium palace · not product Memory GA · not control-plane GA
- Sync ingest is fail-open audit path when sync=True
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .errors import APIError, ClientError

if TYPE_CHECKING:
    from .client import PubAck

MEMORY_ENVELOPE_INGEST = "memory_ingest"
MEMORY_ENVELOPE_RECALL = "memory_recall"
STREAM_MEMORY_INGEST = "MEMORY_INGEST"

PATH_MEMORY_INGEST_V1 = "/v1/memory/ingest"
PATH_MEMORY_INGEST_V5 = "/v5/memory/ingest"
PATH_MEMORY_RETRIEVE_V1 = "/v1/memory/retrieve"
PATH_MEMORY_RETRIEVE_V5 = "/v5/memory/retrieve"


@dataclass
class MemoryEntityRef:
    """Anchor a memory turn to an external entity (ticket, PR, account)."""

    type: str = ""
    id: str = ""


@dataclass
class MemoryEnvelope:
    """v5 memory stream / ingest payload shape (optional temporal fields)."""

    type: str = ""
    session_id: str = ""
    turn_id: str = ""
    memory_id: str = ""
    tier: int = 0
    role: str = ""
    content: str = ""
    embedding_ref: str = ""
    surprise_score: float = 0.0
    # Temporal (optional)
    event_time: str = ""
    ingested_at: str = ""
    source_stream: str = ""
    source_seq: int = 0
    session_seq: int = 0
    causal_parent_id: str = ""
    entity_refs: list[MemoryEntityRef] = field(default_factory=list)
    valid_from: str = ""
    valid_until: str = ""


@dataclass
class MemoryIngestResponse:
    """Sync ingest JSON body from POST /v1|/v5/memory/ingest."""

    status: str = ""
    memory_id: str = ""
    tier: int = 0
    ingested: int = 0


@dataclass
class DualWriteMemoryResult:
    """Outcome of dual_write_memory_turn.

    Async failure raises; sync failures are fail-open in sync_err.
    """

    async_ack: Optional[PubAck] = None
    sync: Optional[MemoryIngestResponse] = None
    sync_err: Optional[BaseException] = None


@dataclass
class MemoryHit:
    """One recall result from the memory sidecar."""

    id: str = ""
    memory_id: str = ""
    summary: str = ""
    full: str = ""
    content: str = ""
    score: float = 0.0
    confidence: float = 0.0
    timestamp: str = ""
    turn_id: str = ""
    event_time: str = ""
    session_seq: int = 0


@dataclass
class MemoryRetrieveRequest:
    """Sync HTTP body for POST /v1|/v5/memory/retrieve."""

    tenant_id: str = ""
    query: str = ""
    limit: int = 0
    session_id: str = ""
    session_seq: int = 0
    since: str = ""
    until: str = ""


@dataclass
class MemoryRetrieveResponse:
    """Sync retrieve JSON body."""

    memories: list[MemoryHit] = field(default_factory=list)
    path: str = ""  # successful API path; not on wire


class MemoryClientMethods:
    """Mixin: Client memory helpers (Go PublishMemoryIngest / DualWrite / Ingest / Retrieve)."""

    def publish_memory_ingest(self, tenant_id: str, env: MemoryEnvelope) -> PubAck:
        """Publish memory_ingest envelope to MEMORY_INGEST subject {tenant}.memory.ingest.turn."""
        tenant_id = (tenant_id or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")
        if not (env.content or "").strip():
            raise ClientError("iomeshclient: content required for memory ingest")
        type_ = (env.type or "").strip() or MEMORY_ENVELOPE_INGEST
        payload = _envelope_to_dict(env, type_default=type_)
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        subject = f"{tenant_id}.memory.ingest.turn"
        return self.publish(STREAM_MEMORY_INGEST, subject, raw)  # type: ignore[attr-defined]

    def dual_write_memory_turn(
        self,
        tenant_id: str,
        env: MemoryEnvelope,
        *,
        sync: bool = False,
        sync_client: Any = None,
    ) -> DualWriteMemoryResult:
        """Async MEMORY_INGEST first; optional sync ingest when sync=True (fail-open).

        Default sync=False keeps dual_write **OFF** (local-primary stream only).
        """
        ack = self.publish_memory_ingest(tenant_id, env)
        out = DualWriteMemoryResult(async_ack=ack)
        if not sync:
            return out
        sc = sync_client if sync_client is not None else self
        try:
            resp = sc.ingest_memory_turn(tenant_id, env)
            out.sync = resp
            out.sync_err = None
        except BaseException as e:  # fail-open: surface in result, do not raise
            out.sync = None
            out.sync_err = e
        return out

    def ingest_memory_turn(
        self, tenant_id: str, env: MemoryEnvelope
    ) -> MemoryIngestResponse:
        """POST try /v1/memory/ingest then /v5/memory/ingest (tenant_id + envelope fields)."""
        tenant_id = (tenant_id or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")
        if not (env.content or "").strip():
            raise ClientError("iomeshclient: content required for memory ingest")
        type_ = (env.type or "").strip() or MEMORY_ENVELOPE_INGEST
        body = _ingest_body(tenant_id, env, type_)
        last_err: Optional[BaseException] = None
        for path in (PATH_MEMORY_INGEST_V1, PATH_MEMORY_INGEST_V5):
            try:
                raw = self._do_json("POST", path, body) or {}  # type: ignore[attr-defined]
                return MemoryIngestResponse(
                    status=str(raw.get("status") or ""),
                    memory_id=str(raw.get("memory_id") or ""),
                    tier=int(raw.get("tier") or 0),
                    ingested=int(raw.get("ingested") or 0),
                )
            except APIError as e:
                last_err = e
                if e.status_code == 404:
                    continue
                if 400 <= e.status_code < 500:
                    raise
                continue
            except ClientError as e:
                last_err = e
                continue
        if last_err is not None:
            raise last_err
        raise ClientError("iomeshclient: memory ingest: no path succeeded")

    def retrieve_memory(self, req: MemoryRetrieveRequest) -> MemoryRetrieveResponse:
        """Thin sync hybrid recall: POST /v1 then /v5 /memory/retrieve.

        Query may be empty when session_id is set. Not Memory GA.
        """
        tenant_id = (req.tenant_id or "").strip()
        query = (req.query or "").strip()
        session_id = (req.session_id or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")
        if not query and not session_id:
            raise ClientError("iomeshclient: query or session_id required")
        body: dict[str, Any] = {
            "tenant_id": tenant_id,
            "type": MEMORY_ENVELOPE_RECALL,
            "query": query,
        }
        if req.limit > 0:
            body["limit"] = req.limit
        if session_id:
            body["session_id"] = session_id
        if req.session_seq:
            body["session_seq"] = req.session_seq
        since = (req.since or "").strip()
        until = (req.until or "").strip()
        if since:
            body["since"] = since
        if until:
            body["until"] = until

        last_err: Optional[BaseException] = None
        for path in (PATH_MEMORY_RETRIEVE_V1, PATH_MEMORY_RETRIEVE_V5):
            try:
                raw = self._do_json("POST", path, body) or {}  # type: ignore[attr-defined]
                memories_raw = raw.get("memories") if isinstance(raw, dict) else None
                memories: list[MemoryHit] = []
                if isinstance(memories_raw, list):
                    for m in memories_raw:
                        if not isinstance(m, dict):
                            continue
                        memories.append(
                            MemoryHit(
                                id=str(m.get("id") or ""),
                                memory_id=str(m.get("memory_id") or ""),
                                summary=str(m.get("summary") or ""),
                                full=str(m.get("full") or ""),
                                content=str(m.get("content") or ""),
                                score=float(m.get("score") or 0),
                                confidence=float(m.get("confidence") or 0),
                                timestamp=str(m.get("timestamp") or ""),
                                turn_id=str(m.get("turn_id") or ""),
                                event_time=str(m.get("event_time") or ""),
                                session_seq=int(m.get("session_seq") or 0),
                            )
                        )
                return MemoryRetrieveResponse(memories=memories, path=path)
            except APIError as e:
                last_err = e
                if e.status_code == 404:
                    continue
                if 400 <= e.status_code < 500:
                    raise
                continue
            except ClientError as e:
                last_err = e
                continue
        if last_err is not None:
            raise last_err
        raise ClientError("iomeshclient: memory retrieve: no path succeeded")


def _envelope_to_dict(env: MemoryEnvelope, *, type_default: str) -> dict[str, Any]:
    """JSON-serialize envelope with omitempty-style omission of empty optional fields."""
    out: dict[str, Any] = {"type": type_default}
    if env.session_id:
        out["session_id"] = env.session_id
    if env.turn_id:
        out["turn_id"] = env.turn_id
    if env.memory_id:
        out["memory_id"] = env.memory_id
    if env.tier:
        out["tier"] = env.tier
    if env.role:
        out["role"] = env.role
    if env.content:
        out["content"] = env.content
    if env.embedding_ref:
        out["embedding_ref"] = env.embedding_ref
    if env.surprise_score:
        out["surprise_score"] = env.surprise_score
    if env.event_time:
        out["event_time"] = env.event_time
    if env.ingested_at:
        out["ingested_at"] = env.ingested_at
    if env.source_stream:
        out["source_stream"] = env.source_stream
    if env.source_seq:
        out["source_seq"] = env.source_seq
    if env.session_seq:
        out["session_seq"] = env.session_seq
    if env.causal_parent_id:
        out["causal_parent_id"] = env.causal_parent_id
    if env.entity_refs:
        out["entity_refs"] = [
            {"type": r.type, "id": r.id} for r in env.entity_refs if r.type or r.id
        ]
    if env.valid_from:
        out["valid_from"] = env.valid_from
    if env.valid_until:
        out["valid_until"] = env.valid_until
    return out


def _ingest_body(tenant_id: str, env: MemoryEnvelope, type_: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "tenant_id": tenant_id,
        "type": type_,
    }
    if env.session_id:
        body["session_id"] = env.session_id
    if env.turn_id:
        body["turn_id"] = env.turn_id
    if env.memory_id:
        body["memory_id"] = env.memory_id
    if env.role:
        body["role"] = env.role
    if env.content:
        body["content"] = env.content
    if env.tier:
        body["tier"] = env.tier
    if env.event_time:
        body["event_time"] = env.event_time
    if env.ingested_at:
        body["ingested_at"] = env.ingested_at
    if env.source_stream:
        body["source_stream"] = env.source_stream
    if env.source_seq:
        body["source_seq"] = env.source_seq
    if env.session_seq:
        body["session_seq"] = env.session_seq
    if env.causal_parent_id:
        body["causal_parent_id"] = env.causal_parent_id
    if env.entity_refs:
        body["entity_refs"] = [{"type": r.type, "id": r.id} for r in env.entity_refs]
    if env.valid_from:
        body["valid_from"] = env.valid_from
    if env.valid_until:
        body["valid_until"] = env.valid_until
    return body
