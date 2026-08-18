"""Memory helpers — edge async ingest/recall + optional sync dual_write + related/ops_digest.

Honesty:
- dual_write **OFF** by default (sync=False): local-primary MEMORY_INGEST publish only
- async MEMORY_RPC recall is **edge publish only** · not invent Memory GA / freemium palace
- multi-hop related is **lite** (EntityGraph BFS) · not full graph RAG / KG · not Memory GA
- ops_digest: ops horizon framing · knowledge/analytical Beta · never invent GA
  or a Memory Ops Pack
- Sync HTTP ingest/retrieve/related/ops_digest live on the **operator-local memory
  sidecar**, not as Memory GA on the mesh broker. A broker-only URL may 404 those
  paths, or return a plan-gate stub (``status=accepted`` + ``note``) that is **not**
  a palace write.
- This SDK is a mesh/control-plane HTTP client, not Memory GA.
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
STREAM_MEMORY_RPC = "MEMORY_RPC"

PATH_MEMORY_INGEST_V1 = "/v1/memory/ingest"
PATH_MEMORY_INGEST_V5 = "/v5/memory/ingest"
PATH_MEMORY_RETRIEVE_V1 = "/v1/memory/retrieve"
PATH_MEMORY_RETRIEVE_V5 = "/v5/memory/retrieve"
PATH_MEMORY_RELATED_V1 = "/v1/memory/related"
PATH_MEMORY_RELATED_V5 = "/v5/memory/related"
PATH_MEMORY_OPS_DIGEST_V1 = "/v1/memory/ops_digest"
PATH_MEMORY_OPS_DIGEST_V5 = "/v5/memory/ops_digest"


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
    """Sync ingest JSON body from POST /v1|/v5/memory/ingest.

    Sidecar success is typically ``status=ok`` plus ``memory_id``. A mesh-broker
    plan-gate stub may return ``status=accepted`` with a ``note`` and **no**
    ``memory_id`` — that is not a palace write and not Memory GA.
    """

    status: str = ""
    memory_id: str = ""
    tier: int = 0
    ingested: int = 0
    note: str = ""


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
    """One recall result from the memory sidecar (retrieve or related)."""

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
    # hop_distance set on multi-hop related when sidecar annotates min hop from seed
    # (0 = seed entity). Omitted on plain retrieve. Multi-hop lite · not full graph RAG.
    hop_distance: int = 0


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
class MemoryRecallRequest:
    """Async MEMORY_RPC publish body (request_memory_recall / request_memory_recall_full).

    Edge publish only — not invent Memory GA · dual_write OFF elsewhere · not freemium palace.
    """

    tenant_id: str = ""
    query: str = ""
    limit: int = 0
    session_id: str = ""  # optional temporal correlation (parity with Go / iomesh-tui dogfood)


@dataclass
class MemoryRetrieveResponse:
    """Sync retrieve / related JSON body."""

    memories: list[MemoryHit] = field(default_factory=list)
    path: str = ""  # successful API path; not on wire


@dataclass
class MemoryOpsDigestHonesty:
    """Residual-honest framing on the ops digest export."""

    ops_pulse: str = ""
    knowledge: str = ""
    analytical: str = ""
    never_invent_ga: bool = False
    dual_write_default: str = ""
    book_demo: str = ""
    note: str = ""


@dataclass
class MemoryOpsDigestPattern:
    """One pattern signal in an ops digest."""

    id: str = ""
    kind: str = ""
    subject: str = ""
    count: int = 0
    window: str = ""
    score: float = 0.0
    summary: str = ""
    first_seen: str = ""
    last_seen: str = ""


@dataclass
class MemoryOpsDigestReceipt:
    """One timeline receipt in an ops digest pack."""

    id: str = ""
    event_time: str = ""
    summary: str = ""
    source_hint: str = ""


@dataclass
class MemoryOpsDigestDecisionStub:
    """Human-owned decision scaffold (not auto-apply)."""

    pattern: str = ""
    receipts_ref: list[str] = field(default_factory=list)
    product_or_gtm_hypothesis: str = ""


@dataclass
class MemoryOpsDigestResponse:
    """Ops digest export JSON body from POST /v1|/v5/memory/ops_digest."""

    window: str = ""
    horizon: str = ""
    as_of: str = ""
    since: str = ""
    honesty: Optional[MemoryOpsDigestHonesty] = None
    patterns: list[MemoryOpsDigestPattern] = field(default_factory=list)
    receipts: list[MemoryOpsDigestReceipt] = field(default_factory=list)
    decision_stub: Optional[MemoryOpsDigestDecisionStub] = None
    path: str = ""  # successful API path; not on wire


class MemoryClientMethods:
    """Mixin: Client memory helpers (Go PublishMemoryIngest / DualWrite / Recall / Retrieve)."""

    def request_memory_recall(
        self, tenant_id: str, query: str, limit: int = 0
    ) -> PubAck:
        """Publish async memory_recall to MEMORY_RPC.

        For session correlation use :meth:`request_memory_recall_full`. For sync hits
        use :meth:`retrieve_memory`. Edge publish only — not invent Memory GA.
        """
        return self.request_memory_recall_full(
            MemoryRecallRequest(tenant_id=tenant_id, query=query, limit=limit)
        )

    def request_memory_recall_full(self, req: MemoryRecallRequest) -> PubAck:
        """Publish async MEMORY_RPC with optional session_id (TUI dogfood parity).

        Stream ``MEMORY_RPC``, subject ``{tenant}.memory.retrieve.request``, JSON body
        type ``memory_recall``. Not product Memory GA · dual_write OFF elsewhere.
        """
        tenant_id = (req.tenant_id or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")
        query = (req.query or "").strip()
        if not query:
            raise ClientError("iomeshclient: query required")

        body: dict[str, Any] = {
            "type": MEMORY_ENVELOPE_RECALL,
            "tenant_id": tenant_id,
            "query": query,
        }
        if req.limit > 0:
            body["limit"] = req.limit
        session_id = (req.session_id or "").strip()
        if session_id:
            body["session_id"] = session_id
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        subject = f"{tenant_id}.memory.retrieve.request"
        return self.publish(STREAM_MEMORY_RPC, subject, raw)  # type: ignore[attr-defined]

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
        """POST try /v1/memory/ingest then /v5/memory/ingest (tenant_id + envelope fields).

        These paths are served by the operator-local memory sidecar. Pointing the
        client at a mesh broker URL is not Memory GA: the broker may 404 ``/v1``
        and return a plan-gate stub on ``/v5`` (keep ``note``; do not invent a write).
        """
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
                    note=str(raw.get("note") or ""),
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

        Query may be empty when session_id is set. Sidecar-on-operator.
        Not Memory GA. A mesh-broker URL typically 404s these paths.
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
                        memories.append(_memory_hit_from(m))
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

    def retrieve_memory_related(
        self,
        tenant_id: str,
        *,
        seed_entity: str = "",
        query: str = "",
        max_hops: int = 0,
        limit: int = 0,
        session_id: str = "",
        as_of: str = "",
        prefer_shorter_hops: Optional[bool] = None,
    ) -> MemoryRetrieveResponse:
        """Multi-hop associative recall: POST /v1 then /v5 /memory/related.

        Honesty: multi-hop lite (EntityGraph BFS + entry entity tags) · not full
        graph RAG / KG · not product Memory GA · dual_write remains OFF by default
        elsewhere. At least one of *seed_entity* or *query* is required.
        *prefer_shorter_hops* omit/None = kernel default true; False = legacy seed-first.
        """
        tenant_id = (tenant_id or "").strip()
        seed_entity = (seed_entity or "").strip()
        query = (query or "").strip()
        session_id = (session_id or "").strip()
        as_of = (as_of or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")
        if not seed_entity and not query:
            raise ClientError("iomeshclient: seed_entity or query required")

        body: dict[str, Any] = {"tenant_id": tenant_id}
        if seed_entity:
            body["seed_entity"] = seed_entity
        if query:
            body["query"] = query
        if max_hops > 0:
            body["max_hops"] = max_hops
        if limit > 0:
            body["limit"] = limit
        if session_id:
            body["session_id"] = session_id
        if as_of:
            body["as_of"] = as_of
        if prefer_shorter_hops is not None:
            body["prefer_shorter_hops"] = prefer_shorter_hops

        last_err: Optional[BaseException] = None
        for path in (PATH_MEMORY_RELATED_V1, PATH_MEMORY_RELATED_V5):
            try:
                raw = self._do_json("POST", path, body) or {}  # type: ignore[attr-defined]
                memories_raw = raw.get("memories") if isinstance(raw, dict) else None
                memories: list[MemoryHit] = []
                if isinstance(memories_raw, list):
                    for m in memories_raw:
                        if isinstance(m, dict):
                            memories.append(_memory_hit_from(m))
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
        raise ClientError("iomeshclient: memory related: no path succeeded")

    def export_ops_digest(
        self,
        tenant_id: str,
        *,
        window: str = "day",
        horizon: str = "ops",
        as_of: str = "",
        limit: int = 0,
    ) -> MemoryOpsDigestResponse:
        """Ops heartbeat digest export: POST /v1 then /v5 /memory/ops_digest.

        Honesty: ops horizon framing · knowledge/analytical Beta · never invent GA
        or a Memory Ops Pack · dual_write OFF · book-demo OFF · not product Memory
        GA. Human owns irreversible decisions. *window* defaults to ``day``;
        *horizon* defaults to ``ops``. Sidecar HTTP, not a mesh-broker Memory GA
        surface.
        """
        tenant_id = (tenant_id or "").strip()
        window = (window or "").strip().lower() or "day"
        horizon = (horizon or "").strip().lower() or "ops"
        as_of = (as_of or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")

        body: dict[str, Any] = {
            "tenant_id": tenant_id,
            "window": window,
            "horizon": horizon,
        }
        if limit > 0:
            body["limit"] = limit
        if as_of:
            body["as_of"] = as_of

        last_err: Optional[BaseException] = None
        for path in (PATH_MEMORY_OPS_DIGEST_V1, PATH_MEMORY_OPS_DIGEST_V5):
            try:
                raw = self._do_json("POST", path, body) or {}  # type: ignore[attr-defined]
                if not isinstance(raw, dict):
                    raw = {}
                return MemoryOpsDigestResponse(
                    window=str(raw.get("window") or window),
                    horizon=str(raw.get("horizon") or horizon),
                    as_of=str(raw.get("as_of") or ""),
                    since=str(raw.get("since") or ""),
                    honesty=_ops_honesty_from(raw.get("honesty")),
                    patterns=_ops_patterns_from(raw.get("patterns")),
                    receipts=_ops_receipts_from(raw.get("receipts")),
                    decision_stub=_ops_decision_from(raw.get("decision_stub")),
                    path=path,
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
        raise ClientError("iomeshclient: memory ops_digest: no path succeeded")


def _memory_hit_from(m: dict[str, Any]) -> MemoryHit:
    return MemoryHit(
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
        hop_distance=int(m.get("hop_distance") or 0),
    )


def _ops_honesty_from(raw: Any) -> Optional[MemoryOpsDigestHonesty]:
    if not isinstance(raw, dict):
        return None
    return MemoryOpsDigestHonesty(
        ops_pulse=str(raw.get("ops_pulse") or ""),
        knowledge=str(raw.get("knowledge") or ""),
        analytical=str(raw.get("analytical") or ""),
        never_invent_ga=bool(raw.get("never_invent_ga")),
        dual_write_default=str(raw.get("dual_write_default") or ""),
        book_demo=str(raw.get("book_demo") or ""),
        note=str(raw.get("note") or ""),
    )


def _ops_patterns_from(raw: Any) -> list[MemoryOpsDigestPattern]:
    if not isinstance(raw, list):
        return []
    out: list[MemoryOpsDigestPattern] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        out.append(
            MemoryOpsDigestPattern(
                id=str(p.get("id") or ""),
                kind=str(p.get("kind") or ""),
                subject=str(p.get("subject") or ""),
                count=int(p.get("count") or 0),
                window=str(p.get("window") or ""),
                score=float(p.get("score") or 0),
                summary=str(p.get("summary") or ""),
                first_seen=str(p.get("first_seen") or ""),
                last_seen=str(p.get("last_seen") or ""),
            )
        )
    return out


def _ops_receipts_from(raw: Any) -> list[MemoryOpsDigestReceipt]:
    if not isinstance(raw, list):
        return []
    out: list[MemoryOpsDigestReceipt] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        out.append(
            MemoryOpsDigestReceipt(
                id=str(r.get("id") or ""),
                event_time=str(r.get("event_time") or ""),
                summary=str(r.get("summary") or ""),
                source_hint=str(r.get("source_hint") or ""),
            )
        )
    return out


def _ops_decision_from(raw: Any) -> Optional[MemoryOpsDigestDecisionStub]:
    if not isinstance(raw, dict):
        return None
    refs = raw.get("receipts_ref") or []
    if not isinstance(refs, list):
        refs = []
    return MemoryOpsDigestDecisionStub(
        pattern=str(raw.get("pattern") or ""),
        receipts_ref=[str(x) for x in refs],
        product_or_gtm_hypothesis=str(raw.get("product_or_gtm_hypothesis") or ""),
    )


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
