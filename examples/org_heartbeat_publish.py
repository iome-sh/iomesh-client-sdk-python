#!/usr/bin/env python3
"""Publish (+ optional pull) organizational heartbeats (ops pulse) on dept.* streams.

Requires a reachable local or stage I/O Mesh broker (default http://127.0.0.1:8422).
This example does not start a broker and does not claim dual_write / Memory GA /
hosted control-plane access. Surfaces are Beta / pre-1.0. MIT edge client only.

Env:
  IOMESH_URL        mesh broker base (default http://127.0.0.1:8422)
  IOMESH_TENANT     tenant (default dept.engineering)
  IOMESH_ORG        optional X-IOMesh-Org
  IOMESH_WORKSPACE  optional X-IOMesh-Workspace
  IOMESH_API_KEY    optional Bearer
  IOMESH_STREAM     stream name (default EVENTS)
  IOMESH_SUBJECT    publish subject (default <tenant>.events.org-heartbeat)
  IOMESH_PULL=1     also pull_subscribe + one fetch (durable consumer demo)
  IOMESH_CONSUMER   consumer name when IOMESH_PULL=1 (default sdk-org-heartbeat)

Usage:
  export IOMESH_URL=http://127.0.0.1:8422
  python examples/org_heartbeat_publish.py
  IOMESH_PULL=1 python examples/org_heartbeat_publish.py

Offline stage smoke ≠ live APPLY. dual_write is not claimed here.
"""

from __future__ import annotations

import os
import sys

from iomeshclient import (
    VERSION,
    ConnectOptions,
    PullSubscribeConfig,
    StreamConfig,
    connect,
)


def env(key: str, default: str) -> str:
    v = os.environ.get(key, "").strip()
    return v if v else default


def main() -> int:
    base = env("IOMESH_URL", "http://127.0.0.1:8422")
    tenant = env("IOMESH_TENANT", "dept.engineering")
    stream = env("IOMESH_STREAM", "EVENTS")
    subject = env("IOMESH_SUBJECT", f"{tenant}.events.org-heartbeat")
    filt = f"{tenant}.events.>"

    nc = connect(
        ConnectOptions(
            url=base,
            tenant=tenant,
            org=os.environ.get("IOMESH_ORG", "").strip(),
            workspace=os.environ.get("IOMESH_WORKSPACE", "").strip(),
            bearer_token=os.environ.get("IOMESH_API_KEY", "").strip(),
        )
    )

    print(f"sdk={VERSION} org-heartbeat framing (publish/pull dept.* pulse)")

    # Ensure a stream that accepts dept.* organizational heartbeats.
    info = nc.ensure_stream(StreamConfig(name=stream, subjects=[filt]))
    if info is not None:
        print(f"PASS EnsureStream name={info.name} subjects={info.subjects}")
    else:
        print(f"PASS EnsureStream name={stream} (info nil after conflict is OK)")

    # Organizational heartbeat (ops pulse) — public lexicon: heartbeat / pulse only.
    payload = (
        b'{"kind":"org_heartbeat","source":"iomesh-client-sdk-python",'
        b'"note":"examples/org_heartbeat_publish"}'
    )
    ack = nc.publish(stream, subject, payload)
    print(
        f"PASS Publish org_heartbeat seq={ack.seq} subject={ack.subject} "
        f"partition={ack.partition}"
    )

    if os.environ.get("IOMESH_PULL") == "1":
        consumer = env("IOMESH_CONSUMER", "sdk-org-heartbeat")
        sub = nc.pull_subscribe(
            PullSubscribeConfig(stream=stream, consumer=consumer, filter=filt)
        )
        print(f"PASS PullSubscribe stream={stream} consumer={consumer} filter={filt}")
        batch = sub.fetch(5, max_wait_ms=2000)
        print(f"PASS Fetch count={len(batch)}")
        for m in batch:
            print(f"  seq={m.seq} subject={m.subject} bytes={len(m.data)}")

    print("RESULT=done")
    print(
        "note: needs local/stage broker · offline stage smoke ≠ live APPLY · "
        "dual_write not claimed · Beta pre-1.0 · MIT edge client only"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise SystemExit(1)
