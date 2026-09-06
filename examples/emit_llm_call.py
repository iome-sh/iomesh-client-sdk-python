#!/usr/bin/env python3
"""Emit a dept.agent.llm_call organizational heartbeat (ops pulse) via metering helpers.

Requires a reachable local or stage I/O Mesh broker (default http://127.0.0.1:8422).
This example does not start a broker and does not claim dual_write / Memory GA /
hosted control-plane access. Surfaces are Beta / pre-1.0.
Public lexicon: heartbeat / pulse only. MIT edge client only.

Env:
  IOMESH_URL        mesh broker base (default http://127.0.0.1:8422)
  IOMESH_TENANT     tenant (default dept.engineering)
  IOMESH_ORG        X-IOMesh-Org (also enriched into payload when unset; set for hosted isolation)
  IOMESH_WORKSPACE  optional X-IOMesh-Workspace
  IOMESH_DEPARTMENT optional X-IOMesh-Department
  IOMESH_API_KEY    optional Bearer
  IOMESH_SESSION    optional session_id on the event (default sess-demo)
  IOMESH_MODEL      model name (default demo-model)

Usage:
  export IOMESH_URL=http://127.0.0.1:8422
  python examples/emit_llm_call.py

Needs a reachable broker. Running this example locally is not a production rollout.
dual_write is not claimed here.
"""

from __future__ import annotations

import os
import sys

from iomeshclient import VERSION, ConnectOptions, LLMCallEvent, connect


def env(key: str, default: str) -> str:
    v = os.environ.get(key, "").strip()
    return v if v else default


def main() -> int:
    base = env("IOMESH_URL", "http://127.0.0.1:8422")
    tenant = env("IOMESH_TENANT", "dept.engineering")
    session = env("IOMESH_SESSION", "sess-demo")
    model = env("IOMESH_MODEL", "demo-model")

    nc = connect(
        ConnectOptions(
            url=base,
            tenant=tenant,
            org=os.environ.get("IOMESH_ORG", "").strip(),
            workspace=os.environ.get("IOMESH_WORKSPACE", "").strip(),
            department=os.environ.get("IOMESH_DEPARTMENT", "").strip(),
            bearer_token=os.environ.get("IOMESH_API_KEY", "").strip(),
            require_org=os.environ.get("IOMESH_REQUIRE_ORG", "").strip().lower()
            in ("1", "true", "yes", "on"),
        )
    )

    print(f"sdk={VERSION} emit_llm_call framing (dept stream · ops pulse)")

    # Remote metering heartbeat — type dept.agent.llm_call → stream "dept".
    ack = nc.emit_llm_call(
        LLMCallEvent(
            tenant=tenant,
            session_id=session,
            model=model,
            model_id=model,
            duration_ms=12,
            attempts=1,
            est_usd=0.001,
            prompt_tokens=5,
            completion_tokens=5,
            total_tokens=10,
        )
    )
    print(
        f"PASS emit_llm_call seq={ack.seq} stream={ack.stream} "
        f"subject={ack.subject} partition={ack.partition}"
    )

    print("RESULT=done")
    print(
        "note: needs local/stage broker · example is not a production rollout · "
        "dual_write not claimed · Beta pre-1.0 · MIT edge client only · "
        "public lexicon heartbeat/pulse only"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise SystemExit(1)
