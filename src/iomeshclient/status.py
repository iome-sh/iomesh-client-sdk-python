"""Connection status helpers — fail-open health+ready probe snapshot.

Wire parity with Go ``iomeshclient`` status.go:

- ``connection_status()`` probes Health then Ready (both always run)
- ``format_connection_status`` multi-line operator summary
- Aggregate result ``ok`` | ``err``; latencies in ms

Honesty: MIT edge · Beta · operator diagnostics · not product GA.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .errors import APIError, ClientError


@dataclass
class ConnectionStatus:
    """Fail-open snapshot of client identity + health/ready probes.

    Identity strings and probe error strings are always populated for
    operators/CI (empty string when unset / OK). Result is always
    ``ok`` or ``err``.
    """

    base_url: str = ""
    tenant: str = ""
    org: str = ""
    workspace: str = ""
    user_agent: str = ""
    version: str = ""
    health_ok: bool = False
    health_err: str = ""
    health_ms: int = 0
    ready_ok: bool = False
    ready_err: str = ""
    ready_ms: int = 0
    duration_ms: int = 0
    # Aggregate: "ok" when both probes succeeded, else "err"
    result: str = "err"


def aggregate_connection_result(health_ok: bool, ready_ok: bool) -> str:
    """Return ``ok`` when both probes succeeded, otherwise ``err``."""
    if health_ok and ready_ok:
        return "ok"
    return "err"


def _elapsed_ms(start: float) -> int:
    ms = int((time.monotonic() - start) * 1000)
    return ms if ms >= 0 else 0


def _package_version() -> str:
    # Local import avoids circular dependency (client imports this mixin).
    from .client import VERSION

    return VERSION


class StatusClientMethods:
    """Mixin: Client.connection_status (Go ConnectionStatus)."""

    def connection_status(self) -> ConnectionStatus:
        """Probe health then ready (fail-open fields; never panics).

        Both probes always run — does not short-circuit Ready when Health fails.
        Probe wall times are always set as health_ms / ready_ms / duration_ms (>= 0).
        Result is always ``ok`` | ``err``.
        """
        base_url = getattr(self, "base_url", "") or ""
        tenant = getattr(self, "tenant", "") or ""
        org = getattr(self, "org", "") or ""
        workspace = getattr(self, "workspace", "") or ""
        user_agent = getattr(self, "user_agent", "") or ""
        if not user_agent:
            from .client import DEFAULT_USER_AGENT

            user_agent = DEFAULT_USER_AGENT

        s = ConnectionStatus(
            base_url=base_url,
            tenant=tenant,
            org=org,
            workspace=workspace,
            user_agent=user_agent,
            version=_package_version(),
        )

        start = time.monotonic()

        t0 = time.monotonic()
        try:
            self.health()  # type: ignore[attr-defined]
            s.health_ok = True
            s.health_err = ""
        except (APIError, ClientError) as e:
            s.health_ok = False
            s.health_err = str(e)
        except Exception as e:  # pragma: no cover — defensive
            s.health_ok = False
            s.health_err = str(e)
        s.health_ms = _elapsed_ms(t0)

        t1 = time.monotonic()
        try:
            self.ready()  # type: ignore[attr-defined]
            s.ready_ok = True
            s.ready_err = ""
        except (APIError, ClientError) as e:
            s.ready_ok = False
            s.ready_err = str(e)
        except Exception as e:  # pragma: no cover — defensive
            s.ready_ok = False
            s.ready_err = str(e)
        s.ready_ms = _elapsed_ms(t1)

        s.duration_ms = _elapsed_ms(start)
        s.result = aggregate_connection_result(s.health_ok, s.ready_ok)
        return s


def format_connection_status(s: ConnectionStatus) -> str:
    """Human multi-line summary of ConnectionStatus (Go FormatConnectionStatus).

    Always emits tenant=, org=, workspace= (including empty), version,
    health_err=/ready_err= (including empty when OK), latencies, and result=.
    """
    ver = s.version or _package_version()
    lines = [
        f"base_url={s.base_url}",
        f"tenant={s.tenant}",
        f"org={s.org}",
        f"workspace={s.workspace}",
        f"user_agent={s.user_agent}",
        f"version={ver}",
        "health=ok" if s.health_ok else "health=FAIL",
        f"health_err={s.health_err}",
        f"health_ms={s.health_ms}",
        "ready=ok" if s.ready_ok else "ready=FAIL",
        f"ready_err={s.ready_err}",
        f"ready_ms={s.ready_ms}",
        f"duration_ms={s.duration_ms}",
    ]
    result = s.result
    if result not in ("ok", "err"):
        result = aggregate_connection_result(s.health_ok, s.ready_ok)
    lines.append(f"result={result}")
    return "\n".join(lines) + "\n"
