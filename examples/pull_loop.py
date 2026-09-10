#!/usr/bin/env python3
"""Durable pull consumer demo: ensure stream/consumer, fetch batches, ack (or nack).

Requires a reachable local or stage I/O Mesh broker (default http://127.0.0.1:8422).
This example does not start a broker and does not claim dual_write / Memory GA /
hosted control-plane access. Surfaces are Beta / pre-1.0.
Public lexicon: heartbeat / pulse only. MIT edge client only.

Env:
  IOMESH_URL         mesh broker base (default http://127.0.0.1:8422)
  IOMESH_TENANT      tenant (default dept.engineering)
  IOMESH_ORG         X-IOMesh-Org — hosted public id is org_+cuid2 (CP-minted, not a
                     display-name slug). Set for hosted isolation; omit only on local
                     fail-open brokers. This example does not mint ids.
  IOMESH_REQUIRE_ORG 1/true/yes/on — client fail-closes catalog/consume when IOMESH_ORG is empty
  IOMESH_WORKSPACE   optional X-IOMesh-Workspace — hosted public id is ws_+cuid2.
                     Omit blank = broker root-default; never invent workspaces[0].
  IOMESH_DEPARTMENT  optional X-IOMesh-Department
  IOMESH_API_KEY     optional Bearer
  IOMESH_STREAM      stream name (default EVENTS)
  IOMESH_SUBJECT     optional one-shot publish subject before pull
  IOMESH_FILTER      consumer filter (default <tenant>.events.>)
  IOMESH_CONSUMER    durable consumer name (default sdk-pull-loop)
  IOMESH_BATCH       fetch batch size (default 5)
  IOMESH_MAX_WAIT_MS fetch max wait ms (default 2000)
  IOMESH_LOOPS       number of fetch iterations (default 3)
  IOMESH_PUBLISH=1   publish one org_heartbeat before the pull loop
  IOMESH_NACK=1      nack instead of ack (client helper demo only — serving
                     broker may 404 this path)

Usage:
  export IOMESH_URL=http://127.0.0.1:8422
  export IOMESH_ORG=org_<cuid2>   # CP-minted; not a slug / not org_example
  # omit IOMESH_WORKSPACE → broker binds org root-default (never workspaces[0])
  IOMESH_PUBLISH=1 python examples/pull_loop.py

Needs a reachable broker. Running this example locally is not a production rollout.
dual_write is not claimed here.
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
    filt = env("IOMESH_FILTER", f"{tenant}.events.>")
    consumer = env("IOMESH_CONSUMER", "sdk-pull-loop")
    subject = env("IOMESH_SUBJECT", f"{tenant}.events.org-heartbeat")
    batch = int(env("IOMESH_BATCH", "5"))
    max_wait_ms = int(env("IOMESH_MAX_WAIT_MS", "2000"))
    loops = int(env("IOMESH_LOOPS", "3"))
    do_publish = os.environ.get("IOMESH_PUBLISH") == "1"
    do_nack = os.environ.get("IOMESH_NACK") == "1"

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

    print(f"sdk={VERSION} pull_loop framing (durable fetch/ack · dept.* pulse)")

    info = nc.ensure_stream(StreamConfig(name=stream, subjects=[filt]))
    if info is not None:
        print(f"PASS EnsureStream name={info.name} subjects={info.subjects}")
    else:
        print(f"PASS EnsureStream name={stream} (info nil after conflict is OK)")

    if do_publish:
        payload = (
            b'{"kind":"org_heartbeat","source":"iomesh-client-sdk-python",'
            b'"note":"examples/pull_loop"}'
        )
        ack = nc.publish(stream, subject, payload)
        print(
            f"PASS Publish org_heartbeat seq={ack.seq} subject={ack.subject} "
            f"partition={ack.partition}"
        )

    sub = nc.pull_subscribe(
        PullSubscribeConfig(stream=stream, consumer=consumer, filter=filt)
    )
    print(f"PASS PullSubscribe stream={stream} consumer={consumer} filter={filt}")

    total = 0
    for i in range(loops):
        msgs = sub.fetch(batch, max_wait_ms=max_wait_ms)
        print(f"PASS Fetch loop={i + 1}/{loops} count={len(msgs)}")
        for m in msgs:
            total += 1
            print(f"  seq={m.seq} subject={m.subject} bytes={len(m.data)}")
            if do_nack:
                m.nack()
                print(f"  NACK seq={m.seq}")
            else:
                m.ack()
                print(f"  ACK seq={m.seq}")

    print(f"PASS pull_loop acked_or_nacked={total} mode={'nack' if do_nack else 'ack'}")
    print("RESULT=done")
    print(
        "note: needs local/stage broker · example is not a production rollout · "
        "dual_write not claimed · Beta pre-1.0 · MIT edge client only · "
        "public lexicon heartbeat/pulse only · durable pull demo · "
        "nack helper may 404 on serving broker"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise SystemExit(1)
