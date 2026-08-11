"""SDK errors."""

from __future__ import annotations


class ClientError(Exception):
    """Client-side configuration or usage error (no HTTP response)."""


class APIError(Exception):
    """Broker responded with a non-2xx status."""

    def __init__(self, status_code: int, body: str = "") -> None:
        self.status_code = status_code
        self.body = body or ""
        super().__init__(f"iomeshclient: HTTP {status_code}: {self.body}")
