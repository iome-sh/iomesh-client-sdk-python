"""Policy evaluate helpers — remote tool policy (Rego / OPA path).

Wire parity with Go ``iomeshclient`` policy.go:

- ``POST /v1/policy/evaluate``
- Mode ``off`` / empty → Allow true, Source off (no network)
- 404 → Allow true, Source unavailable
- transport / non-OK / decode → fail-open (Allow true, Source fail-open)
- ``should_block_tool`` only when mode is enforce and mesh explicitly denies

Honesty: MIT edge client · Beta · fail-open when broker missing paths · not invent GA.
Serving HTTP may not register ``/v1/policy/evaluate``; 404 → unavailable (allow).
This helper never auto-emits dept audit events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .errors import APIError, ClientError

POLICY_EVALUATE_PATH = "/v1/policy/evaluate"

# Policy modes (Go PolicyMode)
POLICY_OFF = "off"
POLICY_ADVISORY = "advisory"
POLICY_ENFORCE = "enforce"


@dataclass
class PolicyInput:
    """Sent to POST /v1/policy/evaluate.

    Mode is per-call (this SDK has no offline policy config);
    empty/off → Source=off, Allow=true.
    """

    action: str = ""
    resource: str = ""
    tool: str = ""
    attributes: Optional[dict[str, Any]] = None
    mode: str = ""  # off | advisory | enforce


@dataclass
class PolicyDecision:
    """Evaluate response (broker Rego / OPA path)."""

    allow: bool = True
    reasons: list[str] = field(default_factory=list)
    # mesh | fail-open | off | unavailable
    source: str = ""
    # Echoes the normalized mode used for this check.
    mode: str = ""

    def should_block_tool(self) -> bool:
        """True only when mode is enforce and mesh explicitly denies."""
        return self.mode == POLICY_ENFORCE and (not self.allow) and self.source == "mesh"

    def summary(self) -> str:
        """Short operator-facing string."""
        if self.allow:
            return f"allow source={self.source} mode={self.mode}"
        r = "; ".join(self.reasons) if self.reasons else "denied"
        return f"deny source={self.source} mode={self.mode} reasons={r}"


def normalize_policy_mode(mode: str) -> str:
    """Lowercase/trim; only advisory/enforce stick, else off."""
    m = (mode or "").strip().lower()
    if m == POLICY_ADVISORY:
        return POLICY_ADVISORY
    if m == POLICY_ENFORCE:
        return POLICY_ENFORCE
    return POLICY_OFF


class PolicyClientMethods:
    """Mixin: Client.evaluate_policy (Go EvaluatePolicy)."""

    def evaluate_policy(self, inp: PolicyInput) -> PolicyDecision:
        """POST ``{base}/v1/policy/evaluate`` with fail-open semantics.

        - Mode off or empty → Allow true, Source off (no network)
        - Empty Action with Tool set → Action = ``tool.`` + Tool
        - 404 → Allow true, Source unavailable
        - transport / non-OK / decode → fail-open
        - mesh success → Source mesh; decode allow/allowed/deny/reason/reasons

        Enforce mode only blocks via :meth:`PolicyDecision.should_block_tool`
        when mesh explicitly denies. Never auto-emits dept audit events.
        """
        mode = normalize_policy_mode(inp.mode)
        if mode == POLICY_OFF:
            return PolicyDecision(allow=True, source="off", mode=mode)

        action = (inp.action or "").strip()
        tool = (inp.tool or "").strip()
        if not action and tool:
            action = f"tool.{tool}"

        tenant = getattr(self, "tenant", "") or ""
        payload: dict[str, Any] = {
            "tenant": tenant,
            "action": action,
            "resource": inp.resource or "",
            "tool": tool,
            "attributes": inp.attributes if inp.attributes is not None else None,
            "mode": mode,
        }

        try:
            raw = self._do_json("POST", POLICY_EVALUATE_PATH, payload)  # type: ignore[attr-defined]
        except APIError as e:
            if e.status_code == 404:
                return PolicyDecision(
                    allow=True,
                    source="unavailable",
                    mode=mode,
                    reasons=["policy endpoint 404"],
                )
            return PolicyDecision(
                allow=True,
                source="fail-open",
                mode=mode,
                reasons=[f"http {e.status_code}"],
            )
        except ClientError as e:
            return PolicyDecision(
                allow=True,
                source="fail-open",
                mode=mode,
                reasons=[str(e)],
            )
        except Exception as e:  # pragma: no cover — defensive
            return PolicyDecision(
                allow=True,
                source="fail-open",
                mode=mode,
                reasons=[str(e)],
            )

        return _decision_from_body(raw if isinstance(raw, dict) else {}, mode)


def _decision_from_body(out: dict[str, Any], mode: str) -> PolicyDecision:
    allow = True
    if "allow" in out and out["allow"] is not None:
        allow = bool(out["allow"])
    elif "allowed" in out and out["allowed"] is not None:
        allow = bool(out["allowed"])
    elif out.get("deny"):
        allow = False

    reasons: list[str] = []
    raw_reasons = out.get("reasons")
    if isinstance(raw_reasons, list):
        reasons.extend(str(r) for r in raw_reasons)
    reason = out.get("reason")
    if reason:
        reasons.append(str(reason))

    return PolicyDecision(allow=allow, reasons=reasons, source="mesh", mode=mode)
