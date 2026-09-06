"""Observation envelope normalize + publish headers for connector ingress."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .subject import subject_for_department

RawEvent = bytes | str | dict[str, Any] | list[Any] | None

ENVELOPE_VERSION = 1
DEFAULT_SCHEMA_VERSION = "1.0.0"


def normalize_envelope(
    connector_id: str,
    department: str,
    source: str,
    external_id: str = "",
    event_type: str = "",
    event: RawEvent = None,
) -> bytes:
    """Build an internal observation envelope JSON from verified inbound partner fields.

    When external_id is empty, generates a correlation id via uuid4.
    """
    connector_id = (connector_id or "").strip()
    if not connector_id:
        raise ValueError("connectorsdk: connector id required")
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")

    external_id = (external_id or "").strip()
    if not external_id:
        external_id = str(uuid.uuid4())

    subject = subject_for_department(dept, src)
    raw_payload = _coerce_raw(event)
    inner = {
        "connector_id": connector_id,
        "source": src,
        "department": dept,
        "external_id": external_id,
    }
    et = (event_type or "").strip()
    if et:
        inner["event_type"] = et
    if raw_payload is not None:
        inner["raw"] = raw_payload

    envelope = {
        "v": ENVELOPE_VERSION,
        "type": "observation",
        "agent_id": f"connector:{connector_id}",
        "correlation_id": external_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": inner,
        "metadata": {
            "data_product_id": subject,
            "schema_version": DEFAULT_SCHEMA_VERSION,
            "embedding_ref": None,
            "surprise_score": None,
        },
    }
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# Identity wire name for connector ingress (not the bare "department" key).
DEPARTMENT_HEADER = "X-IOMesh-Department"


def publish_headers(
    connector_id: str,
    department: str,
    external_id: str,
    source: str,
) -> dict[str, str]:
    """Broker metadata headers for connector ingress.

    Department maps to ``X-IOMesh-Department``. Other keys stay envelope
    metadata names (connector_id / external_id / source).
    """
    headers = {
        "connector_id": (connector_id or "").strip(),
        "external_id": (external_id or "").strip(),
        "source": (source or "").strip(),
    }
    dept = (department or "").strip()
    if dept:
        headers[DEPARTMENT_HEADER] = dept
    return headers


def _coerce_raw(event: RawEvent) -> Optional[Any]:
    if event is None:
        return None
    if isinstance(event, (dict, list)):
        return event
    if isinstance(event, bytes):
        if not event:
            return None
        try:
            return json.loads(event.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return event.decode("utf-8", errors="replace")
    if isinstance(event, str):
        if not event:
            return None
        try:
            return json.loads(event)
        except json.JSONDecodeError:
            return event
    return event
