"""HMAC-SHA256 helpers for partner webhook verification (GitHub-style prefix)."""

from __future__ import annotations

import hashlib
import hmac

DEFAULT_HMAC_PREFIX = "sha256="

HEADER_SIGNATURE_256 = "X-Hub-Signature-256"
HEADER_EVENT = "X-GitHub-Event"
HEADER_DELIVERY = "X-GitHub-Delivery"


class ErrMissingSecret(ValueError):
    """Webhook secret required."""

    def __init__(self) -> None:
        super().__init__("connectorsdk: webhook secret required")


class ErrMissingSignature(ValueError):
    """Missing signature header."""

    def __init__(self) -> None:
        super().__init__("connectorsdk: missing signature header")


class ErrInvalidSignature(ValueError):
    """HMAC signature does not match body."""

    def __init__(self) -> None:
        super().__init__("connectorsdk: invalid signature")


def compute_hmac_sha256(secret: str, body: bytes | str, prefix: str = "") -> str:
    """Return HMAC-SHA256 digest for body.

    When prefix is non-empty the result is prefix+<hex> (GitHub style with
    DEFAULT_HMAC_PREFIX); otherwise raw hex.
    """
    if isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        raw = body
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not prefix:
        return digest
    return prefix + digest


def verify_hmac(
    secret: str,
    body: str | bytes,
    signature: str,
    *,
    prefix: str = "",
) -> None:
    """Check signature against body using configured prefix (sha256= by default).

    Raises ErrMissingSecret / ErrMissingSignature / ErrInvalidSignature.
    """
    if not (secret or "").strip():
        raise ErrMissingSecret()
    sig = (signature or "").strip()
    if not sig:
        raise ErrMissingSignature()
    pfx = (prefix or "").strip() or DEFAULT_HMAC_PREFIX
    if isinstance(body, bytes):
        body_s = body.decode("utf-8", errors="surrogateescape")
        expected = compute_hmac_sha256(secret, body, pfx)
    else:
        body_s = body
        expected = compute_hmac_sha256(secret, body_s, pfx)
    # constant-time compare
    if not hmac.compare_digest(expected, sig):
        raise ErrInvalidSignature()
