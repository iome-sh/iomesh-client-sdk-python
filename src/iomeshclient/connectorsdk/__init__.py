"""Connector helpers for partner webhook ingress (HMAC, subjects, observation envelopes).

stdlib only. Parity target: Go package github.com/iome-sh/iomesh-client-sdk-go/connectorsdk.

This package is **local** HMAC + subject/envelope helpers (GitHub-style
``sha256=`` / ``X-Hub-Signature-256``). It does **not** call mesh connector
HTTP, OAuth install, or portal session routes. Verify ≠ Connected. Knowledge
connectors stay Beta. Not OAuth-as-webhook.
"""

from .envelope import DEPARTMENT_HEADER, normalize_envelope, publish_headers
from .hmac import (
    DEFAULT_HMAC_PREFIX,
    HEADER_DELIVERY,
    HEADER_EVENT,
    HEADER_SIGNATURE_256,
    ErrInvalidSignature,
    ErrMissingSecret,
    ErrMissingSignature,
    compute_hmac_sha256,
    verify_hmac,
)
from .subject import (
    subject_for_department,
    subject_for_document,
    subject_for_embedding,
    subject_for_metric,
    subject_for_warehouse,
)

__all__ = [
    "DEFAULT_HMAC_PREFIX",
    "DEPARTMENT_HEADER",
    "HEADER_DELIVERY",
    "HEADER_EVENT",
    "HEADER_SIGNATURE_256",
    "ErrInvalidSignature",
    "ErrMissingSecret",
    "ErrMissingSignature",
    "compute_hmac_sha256",
    "normalize_envelope",
    "publish_headers",
    "subject_for_department",
    "subject_for_document",
    "subject_for_embedding",
    "subject_for_metric",
    "subject_for_warehouse",
    "verify_hmac",
]
