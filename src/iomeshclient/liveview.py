"""Liveview / v3 registry helpers — processor register + list live views.

Wire parity with Go ``iomeshclient`` liveview.go:

- ``register_processor`` → ``POST /v3/registry/processors`` (409 conflict = success)
- ``list_live_views`` → ``GET /v3/registry/liveviews?tenant_id=`` (explicit errors, not fail-open)

Honesty: MIT edge client · Beta · registry helpers not invent liveview GA ·
dual_write OFF elsewhere · not control-plane product GA.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .errors import APIError, ClientError

# Processor type constants for v3 registry processors (Go ProcessorType*).
PROCESSOR_TYPE_FILTER = "filter"
PROCESSOR_TYPE_MAP = "map"
PROCESSOR_TYPE_ENRICH = "enrich"

REGISTER_PROCESSOR_PATH = "/v3/registry/processors"
LIST_LIVE_VIEWS_PATH = "/v3/registry/liveviews"


@dataclass
class ProcessorConfig:
    """In-stream enrichment processor bound to a stream pair.

    Wire shape matches Go ``ProcessorConfig`` (JSON snake_case).
    """

    id: str = ""
    source_stream: str = ""
    target_stream: str = ""
    tenant: str = ""
    type: str = ""  # filter | map | enrich
    config_json: str = ""


@dataclass
class DataProduct:
    """Registry metadata for a governed stream or subject family (minimal).

    Named for /v3 registry rows — distinct from catalog ``CatalogProduct``.
    """

    id: str = ""
    tenant_id: str = ""
    name: str = ""
    domain: str = ""
    owner: str = ""
    schema_ref: str = ""
    upstream_product_ids: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    stream_name: str = ""
    created_at: Optional[datetime] = None


@dataclass
class LiveView(DataProduct):
    """DataProduct plus enrichment lineage and warm-tier metadata."""

    processor_ids: list[str] = field(default_factory=list)
    freshness_slo_sec: int = 0
    materialized_path: str = ""


class LiveViewClientMethods:
    """Mixin: Client liveview/registry methods (Go RegisterProcessor / ListLiveViews)."""

    def register_processor(self, cfg: ProcessorConfig) -> None:
        """Register a processor via ``POST /v3/registry/processors``.

        A 409 conflict is treated as success (idempotent re-register), matching Go.
        Other non-2xx raise ``APIError``. Missing required fields raise ``ClientError``.
        """
        pid = (cfg.id or "").strip()
        if not pid:
            raise ClientError("iomeshclient: processor id required")
        source = (cfg.source_stream or "").strip()
        if not source:
            raise ClientError("iomeshclient: source_stream required")
        tenant = (cfg.tenant or "").strip()
        if not tenant:
            raise ClientError("iomeshclient: tenant required")
        ptype = (cfg.type or "").strip()
        if not ptype:
            raise ClientError("iomeshclient: type required")

        body: dict[str, Any] = {
            "id": pid,
            "source_stream": source,
            "tenant": tenant,
            "type": ptype,
        }
        target = (cfg.target_stream or "").strip()
        if target:
            body["target_stream"] = target
        config_json = (cfg.config_json or "").strip()
        if config_json:
            body["config_json"] = config_json

        try:
            self._do_json("POST", REGISTER_PROCESSOR_PATH, body)  # type: ignore[attr-defined]
        except APIError as e:
            if e.status_code == 409:
                return
            raise

    def list_live_views(self, tenant_id: str) -> list[LiveView]:
        """List live views for ``tenant_id`` via ``GET /v3/registry/liveviews``.

        Empty response body → ``[]``. Non-2xx raises ``APIError`` (not fail-open).
        """
        tenant_id = (tenant_id or "").strip()
        if not tenant_id:
            raise ClientError("iomeshclient: tenant_id required")

        path = f"{LIST_LIVE_VIEWS_PATH}?tenant_id={urllib.parse.quote(tenant_id, safe='')}"
        raw = self._do_json("GET", path, None)  # type: ignore[attr-defined]
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ClientError("iomeshclient: unexpected list_live_views body")
        return [_live_view_from(item) for item in raw]


def _live_view_from(raw: Any) -> LiveView:
    if not isinstance(raw, dict):
        return LiveView()
    upstream = raw.get("upstream_product_ids") or []
    if not isinstance(upstream, list):
        upstream = []
    subjects = raw.get("subjects") or []
    if not isinstance(subjects, list):
        subjects = []
    processor_ids = raw.get("processor_ids") or []
    if not isinstance(processor_ids, list):
        processor_ids = []
    freshness = raw.get("freshness_slo_sec")
    try:
        freshness_slo = int(freshness) if freshness is not None else 0
    except (TypeError, ValueError):
        freshness_slo = 0
    return LiveView(
        id=str(raw.get("id") or ""),
        tenant_id=str(raw.get("tenant_id") or ""),
        name=str(raw.get("name") or ""),
        domain=str(raw.get("domain") or ""),
        owner=str(raw.get("owner") or ""),
        schema_ref=str(raw.get("schema_ref") or ""),
        upstream_product_ids=[str(x) for x in upstream],
        subjects=[str(x) for x in subjects],
        stream_name=str(raw.get("stream_name") or ""),
        created_at=_parse_ts(raw.get("created_at")),
        processor_ids=[str(x) for x in processor_ids],
        freshness_slo_sec=freshness_slo,
        materialized_path=str(raw.get("materialized_path") or ""),
    )


def _parse_ts(val: Any) -> Optional[datetime]:
    # Local re-export of client parse to avoid circular import at module load.
    from .client import _parse_ts as _client_parse_ts

    return _client_parse_ts(val)
