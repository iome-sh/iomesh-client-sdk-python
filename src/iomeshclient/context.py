"""Context plane helpers — fail-open agent prompt injection (text + lineage).

Wire parity with Go ``iomeshclient`` context.go:

- ``POST /v1/context/query``
- Fail-open empty result on transport / non-OK / decode
- ``context_snippet`` always sets ``include_lineage=true``
- ``format_context_snippet`` renders text + compact ``<iomesh-lineage>`` block

Honesty: MIT edge client · Beta · fail-open context · not invent GA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import APIError, ClientError

CONTEXT_QUERY_PATH = "/v1/context/query"


@dataclass
class LineageRef:
    """Governed data-product / stream lineage pointer from the context plane."""

    id: str = ""
    product: str = ""
    subject: str = ""
    source: str = ""
    freshness: str = ""


@dataclass
class ContextResult:
    """Fail-open context plane response (text + optional lineage).

    On success ``ok`` is True and ``path`` is the query path used.
    On soft failure ``ok`` is False, ``source`` is ``fail-open``, and
    text/lineage are empty (never raises for network/HTTP errors).
    """

    text: str = ""
    lineage: list[LineageRef] = field(default_factory=list)
    # items is an alternate wire shape folded into text/lineage on decode.
    items: list[dict[str, Any]] = field(default_factory=list)
    path: str = ""
    ok: bool = False
    # mesh | fail-open
    source: str = ""
    # Short operator note (error detail when fail-open).
    detail: str = ""


class ContextClientMethods:
    """Mixin: Client context methods (Go QueryContext / ContextSnippet)."""

    def query_context(
        self,
        query: str,
        workspace: str = "",
        limit: int = 0,
        *,
        include_lineage: bool = False,
    ) -> ContextResult:
        """POST ``{base}/v1/context/query`` with fail-open semantics.

        Limit defaults to 20 when <= 0. Empty query still POSTs (broker may
        return empty text). Soft failures → empty ContextResult with
        ``ok=False``, ``source=fail-open`` (never raises).
        """
        empty = ContextResult(source="fail-open", path=CONTEXT_QUERY_PATH)
        lim = limit if limit > 0 else 20
        tenant = getattr(self, "tenant", "") or ""
        payload: dict[str, Any] = {
            "tenant": tenant,
            "workspace": workspace or "",
            "query": query or "",
            "limit": lim,
        }
        if include_lineage:
            payload["include_lineage"] = True

        try:
            raw = self._do_json("POST", CONTEXT_QUERY_PATH, payload)  # type: ignore[attr-defined]
        except APIError as e:
            empty.detail = f"http {e.status_code}"
            return empty
        except ClientError as e:
            empty.detail = str(e)
            return empty
        except Exception as e:  # pragma: no cover — defensive
            empty.detail = str(e)
            return empty

        res = _result_from_body(raw if isinstance(raw, dict) else {})
        res.path = CONTEXT_QUERY_PATH
        res.ok = True
        res.source = "mesh"
        return res

    def context_snippet(
        self,
        query: str,
        workspace: str = "",
        *,
        limit: int = 0,
    ) -> str:
        """Fail-open prompt injection text for agent system prompts.

        Always requests ``include_lineage=true`` (agent default). Errors → "".
        """
        return format_context_snippet(
            self.query_context(
                query,
                workspace=workspace,
                limit=limit,
                include_lineage=True,
            )
        )


def format_context_snippet(res: ContextResult) -> str:
    """Merge text + lineage for prompt injection (Go FormatContextSnippet).

    Lineage is rendered as a compact ``<iomesh-lineage>`` block (max 12 refs).
    """
    parts: list[str] = []
    text = (res.text or "").strip()
    if text:
        parts.append(text)
    if res.lineage:
        lines = ["<iomesh-lineage>"]
        for i, ref in enumerate(res.lineage):
            if i >= 12:
                lines.append("…")
                break
            rid = _first_non_empty(ref.id, ref.product)
            fields: list[str] = []
            if rid:
                fields.append(rid)
            if ref.subject:
                fields.append(f"subject={ref.subject}")
            if ref.source:
                fields.append(f"source={ref.source}")
            if ref.freshness:
                fields.append(f"freshness={ref.freshness}")
            if not fields:
                continue
            lines.append("- " + " · ".join(fields))
        lines.append("</iomesh-lineage>")
        parts.append("\n".join(lines))
    return "\n\n".join(parts).strip()


def _lineage_from(raw: Any) -> LineageRef:
    if not isinstance(raw, dict):
        return LineageRef()
    return LineageRef(
        id=str(raw.get("id") or ""),
        product=str(raw.get("product") or ""),
        subject=str(raw.get("subject") or ""),
        source=str(raw.get("source") or ""),
        freshness=str(raw.get("freshness") or ""),
    )


def _result_from_body(out: dict[str, Any]) -> ContextResult:
    text = str(out.get("text") or "").strip()
    lineage_raw = out.get("lineage") or []
    lineage: list[LineageRef] = []
    if isinstance(lineage_raw, list):
        lineage = [_lineage_from(x) for x in lineage_raw]

    items_raw = out.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(items_raw, list):
        items = [x for x in items_raw if isinstance(x, dict)]

    # Alternate shape: fold items into text + lineage when top-level text empty.
    if not text and items:
        chunk_parts: list[str] = []
        for it in items:
            t = str(it.get("text") or "").strip()
            if t:
                chunk_parts.append(t)
            it_lineage = it.get("lineage") or []
            if isinstance(it_lineage, list):
                lineage.extend(_lineage_from(x) for x in it_lineage)
        text = "\n".join(chunk_parts)

    return ContextResult(text=text, lineage=lineage, items=items)


def _first_non_empty(*vals: str) -> str:
    for v in vals:
        if (v or "").strip():
            return v.strip()
    return ""
