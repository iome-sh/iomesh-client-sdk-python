"""Catalog helpers — governed data-product discovery (broker + portal federation).

Wire parity with Go ``iomeshclient`` catalog.go:

- ``list_catalog`` tries broker ``/v1/catalog/*`` then portal ``/v17``/``/v16`` paths
- ``get_catalog_product`` prefers portal detail, then mesh detail, then list filter
- Fail-open empty result when no path succeeds (not control-plane GA)

Honesty: MIT edge client · Beta · not freemium palace · not invent GA.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from .errors import APIError, ClientError

# Path cascade matching Go defaultCatalogPaths (broker first, then portal).
DEFAULT_CATALOG_PATHS: list[tuple[str, str]] = [
    ("/v1/catalog/data-products", "mesh"),
    ("/v1/catalog/products", "mesh"),
    ("/v17/portal/catalog/data-products", "portal"),
    ("/v16/portal/catalog/marketing/data-products", "portal"),
]


@dataclass
class CatalogProduct:
    """Governed catalog entry (data product / stream surface).

    Accepts both broker (``/v1/catalog``) and portal (``/v17/portal/catalog``)
    JSON field names; call :meth:`normalize` to fold portal aliases.
    """

    id: str = ""
    name: str = ""
    title: str = ""
    description: str = ""
    summary: str = ""  # portal
    subject: str = ""
    subject_pattern: str = ""  # portal
    subjects: list[str] = field(default_factory=list)
    sample_subjects: list[str] = field(default_factory=list)  # portal
    layer: str = ""  # operational | knowledge | analytical
    mesh_layer: str = ""  # portal alias
    freshness: str = ""
    owner: str = ""
    department: str = ""
    status: str = ""
    lineage: list[str] = field(default_factory=list)

    def normalize(self) -> CatalogProduct:
        """Copy portal aliases into the common fields used by format helpers."""
        if not self.layer:
            self.layer = self.mesh_layer
        if not self.subject:
            self.subject = self.subject_pattern
        if not self.description:
            self.description = self.summary
        if not self.subjects and self.sample_subjects:
            self.subjects = list(self.sample_subjects)
        if not self.title:
            self.title = _first_non_empty(self.name, self.id)
        return self


@dataclass
class CatalogResult:
    """Fail-open catalog list result."""

    products: list[CatalogProduct] = field(default_factory=list)
    # mesh | portal | fail-open | off
    source: str = ""
    # Short operator note (error or path used).
    detail: str = ""


class CatalogClientMethods:
    """Mixin: Client catalog methods (Go ListCatalog / GetCatalogProduct)."""

    def list_catalog(self, query: str = "") -> CatalogResult:
        """Fetch data products from mesh catalog and/or portal federation.

        Tries broker ``/v1/catalog/*`` then portal paths (404 → next; all fail →
        fail-open empty). Public SDK always discovers (no CatalogPlane flag).
        """
        return self._list_catalog_paths((query or "").strip())

    def get_catalog_product(self, product_id: str) -> tuple[CatalogProduct, CatalogResult]:
        """Fetch one product by id (portal detail, mesh detail, or list filter)."""
        product_id = (product_id or "").strip()
        if not product_id:
            return CatalogProduct(), CatalogResult(
                source="fail-open", detail="empty product id"
            )
        # Prefer portal detail routes, then mesh (Go GetCatalogProduct order).
        detail_paths: list[tuple[str, str]] = [
            (
                f"/v17/portal/catalog/data-products/{urllib.parse.quote(product_id, safe='')}",
                "portal",
            ),
            (
                f"/v1/catalog/data-products/{urllib.parse.quote(product_id, safe='')}",
                "mesh",
            ),
        ]
        for path, source in detail_paths:
            products, _detail, ok = self._catalog_get(path, None)
            if not ok or not products:
                continue
            p = products[0]
            p.normalize()
            return p, CatalogResult(products=products, source=source, detail=path)

        # Fallback: list + filter by id/name.
        listed = self.list_catalog(product_id)
        for p in listed.products:
            p.normalize()
            if p.id == product_id or p.name == product_id:
                return p, CatalogResult(
                    products=[p],
                    source=listed.source,
                    detail=f"{listed.detail} (list filter)",
                )
        return CatalogProduct(), CatalogResult(
            source="fail-open", detail=f"product not found: {product_id}"
        )

    def _list_catalog_paths(self, query: str) -> CatalogResult:
        last_detail = ""
        tenant = getattr(self, "tenant", "") or ""
        for path, source in DEFAULT_CATALOG_PATHS:
            vals: dict[str, str] = {}
            if query:
                # Broker q= ; portal often uses free-text or mesh_layer=
                vals["q"] = query
                if query in ("operational", "knowledge", "analytical"):
                    vals["mesh_layer"] = query
            if tenant:
                vals["tenant"] = tenant
            products, detail, ok = self._catalog_get(path, vals)
            if not ok:
                last_detail = detail
                continue
            for p in products:
                p.normalize()
            return CatalogResult(products=products, source=source, detail=path)
        if not last_detail:
            last_detail = "no catalog path succeeded"
        return CatalogResult(source="fail-open", detail=last_detail)

    def _catalog_get(
        self, path: str, vals: Optional[dict[str, str]]
    ) -> tuple[list[CatalogProduct], str, bool]:
        """One catalog GET with auth headers. ok=False on 404/non-OK/transport/decode."""
        base_url = getattr(self, "base_url", "")
        timeout = getattr(self, "timeout", 30.0)
        url = base_url + path
        if vals:
            enc = urllib.parse.urlencode(vals)
            if enc:
                url += "?" + enc
        headers = self._auth_headers()  # type: ignore[attr-defined]
        req = urllib.request.Request(url, method="GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not (200 <= resp.status < 300):
                    return [], f"{path} http {resp.status}", False
                products, err = _decode_catalog_body(raw)
                if err is not None:
                    return [], f"decode: {err}", False
                return products, path, True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return [], f"{path} 404", False
            return [], f"{path} http {e.code}", False
        except urllib.error.URLError as e:
            return [], str(e), False
        except (ClientError, APIError, OSError, ValueError, json.JSONDecodeError) as e:
            return [], str(e), False


def format_catalog(res: CatalogResult) -> str:
    """Compact table for CLI / operators (Go FormatCatalog)."""
    lines: list[str] = [f"iomesh catalog source={res.source}"]
    if res.detail:
        lines[0] += f" detail={res.detail}"
    if not res.products:
        lines.append("(no data products)")
        return "\n".join(lines) + "\n"
    lines.append(f"{'ID':<24} {'LAYER':<12} {'SUBJECT':<28} TITLE/NAME")
    for i, p in enumerate(res.products):
        p.normalize()
        if i >= 50:
            lines.append(f"… ({len(res.products) - 50} more)")
            break
        pid = _first_non_empty(p.id, p.name)
        title = _first_non_empty(p.title, p.name, p.description, p.summary)
        subj = p.subject
        if not subj and p.subjects:
            subj = p.subjects[0]
        lines.append(
            f"{_truncate(pid, 24):<24} {_truncate(p.layer, 12):<12} "
            f"{_truncate(subj, 28):<28} {_truncate(title, 48)}"
        )
    return "\n".join(lines) + "\n"


def format_product_detail(p: CatalogProduct, meta: CatalogResult) -> str:
    """Multi-line view for one product (Go FormatProductDetail)."""
    p.normalize()
    lines = [
        f"iomesh catalog product source={meta.source} detail={meta.detail}",
        f"id:          {_first_non_empty(p.id, p.name)}",
        f"name:        {_first_non_empty(p.title, p.name)}",
        f"layer:       {p.layer}",
        f"subject:     {p.subject}",
    ]
    if p.status:
        lines.append(f"status:      {p.status}")
    if p.department:
        lines.append(f"department:  {p.department}")
    desc = _first_non_empty(p.description, p.summary)
    if desc:
        lines.append(f"description: {desc}")
    if p.lineage:
        lines.append("lineage:")
        for step in p.lineage:
            lines.append(f"  - {step}")
    if p.subjects:
        lines.append("subjects:")
        for i, s in enumerate(p.subjects):
            if i >= 12:
                lines.append(f"  … +{len(p.subjects) - 12} more")
                break
            lines.append(f"  - {s}")
    return "\n".join(lines) + "\n"


def _product_from(raw: Any) -> CatalogProduct:
    if not isinstance(raw, dict):
        return CatalogProduct()
    subjects = raw.get("subjects") or []
    if not isinstance(subjects, list):
        subjects = []
    sample = raw.get("sample_subjects") or []
    if not isinstance(sample, list):
        sample = []
    lineage = raw.get("lineage") or []
    if not isinstance(lineage, list):
        lineage = []
    return CatalogProduct(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        title=str(raw.get("title") or ""),
        description=str(raw.get("description") or ""),
        summary=str(raw.get("summary") or ""),
        subject=str(raw.get("subject") or ""),
        subject_pattern=str(raw.get("subject_pattern") or ""),
        subjects=[str(s) for s in subjects],
        sample_subjects=[str(s) for s in sample],
        layer=str(raw.get("layer") or ""),
        mesh_layer=str(raw.get("mesh_layer") or ""),
        freshness=str(raw.get("freshness") or ""),
        owner=str(raw.get("owner") or ""),
        department=str(raw.get("department") or ""),
        status=str(raw.get("status") or ""),
        lineage=[str(s) for s in lineage],
    )


def _decode_catalog_body(raw: bytes) -> tuple[list[CatalogProduct], Optional[str]]:
    """Decode list/detail envelopes. Returns (products, error_message)."""
    if not raw:
        return [], None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return [], str(e)

    # Single product object (detail endpoint) — avoid list envelopes.
    if isinstance(data, dict):
        one = _product_from(data)
        if (one.id or one.name) and not any(
            k in data for k in ("products", "items", "data_products")
        ):
            one.normalize()
            return [one], None

    if isinstance(data, list):
        return [_product_from(x) for x in data], None

    if isinstance(data, dict):
        for key in ("products", "items", "data_products"):
            arr = data.get(key)
            if isinstance(arr, list) and arr:
                return [_product_from(x) for x in arr], None
        # Empty products array with version envelope is still success.
        if data.get("version") or data == {}:
            for key in ("products", "items", "data_products"):
                arr = data.get(key)
                if isinstance(arr, list):
                    return [], None
            return [], None
        # Empty list keys present
        for key in ("products", "items", "data_products"):
            if key in data and isinstance(data[key], list):
                return [], None
        return [], None

    return [], "unexpected catalog body"


def _first_non_empty(*vals: str) -> str:
    for v in vals:
        if (v or "").strip():
            return v.strip()
    return ""


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    if n <= 1:
        return s[:n]
    return s[: n - 1] + "…"
