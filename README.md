# I/O Mesh Client SDK for Python

[![CI](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI status](https://img.shields.io/badge/status-Beta%20pre--1.0-yellow.svg)](#status)

Official **Python client SDK** for the [I/O Mesh](https://iome.sh) broker (HTTP plane + Kafka Produce subset).

Publish and pull **organizational heartbeats** (ops **pulse**) on `dept.*` streams: connectors and services emit org-tool events; agents and workers consume them via durable pull. Public lexicon is **heartbeat / pulse** only.

This repository is **MIT edge client code** only — not free mesh control-plane access, not a freemium hosted palace, and not product Memory GA. Surfaces are **Beta** / pre-1.0. Official open-source tooling from [IOMesh](https://iome.sh) (**IOMesh Technology Ltd.**).

| Capability (v0.5) | Notes |
|-------------------|--------|
| `connect` + tenant / org / workspace / bearer headers | No network I/O on connect |
| `publish` (base64 payload) | `POST /v1/streams/{stream}/publish` → `PubAck` |
| Streams: create / ensure / get / list / delete | 409 conflict → best-effort GET |
| Consumers: create / ensure / fetch / ack / nack / pull_subscribe | Fetch decodes base64 payloads |
| **KV** create / put / get / delete / list_keys | 409 create → name-only `BucketInfo` |
| **Memory helpers** | `publish_memory_ingest`, `dual_write_memory_turn` (**OFF** default), `ingest_memory_turn`, `retrieve_memory`, **`retrieve_memory_related`**, **`export_ops_digest`** |
| **Catalog** | `list_catalog` / `get_catalog_product` — broker + portal path cascade; fail-open |
| **Policy evaluate** | `evaluate_policy` → `PolicyDecision` (`should_block_tool` / `summary`); fail-open |
| **Context** | `query_context` / `context_snippet` / `format_context_snippet` — fail-open prompt injection |
| **Format + connection status** | `format_streams` / `format_stream_detail`; `connection_status` / `format_connection_status` |
| **connectorsdk** | HMAC verify, subject builders, observation envelope normalize |
| **Kafka Produce subset** | `KafkaClient(addr).produce(topic, partition, key, value) → offset` |
| Health / ready / **wait_ready** | `GET /health`, `GET /ready` then `/readyz`; poll until ready |

Parity target: the Go package [`iomeshclient`](https://github.com/iome-sh/iomesh-client-sdk-go) + [`kafka`](https://github.com/iome-sh/iomesh-client-sdk-go/tree/main/kafka) + [`connectorsdk`](https://github.com/iome-sh/iomesh-client-sdk-go/tree/main/connectorsdk).

**Residual Next:** live PyPI publish (token residual) · Kafka consumer residual · tool-marketing adopt optional · richer memory when product-ready.

> **Package:** `iomeshclient`  
> **Wire headers:** `X-IOMesh-Tenant`, `X-IOMesh-Org`, `X-IOMesh-Workspace`  
> **User-Agent:** `iomesh-client-sdk-python/0.5.0`  
> **Status:** public OSS **v0.5.0** (pre-1.0, **Beta**)  
> **Go SDK:** [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go)

## Requirements

- Python **3.10+**
- Network access to an I/O Mesh broker (or local foundation)
- **stdlib only** for the client (`urllib`, `socket`); no third-party runtime deps

## Install

From source (until a PyPI release is published — see [RELEASING.md](RELEASING.md)):

```bash
pip install -e "git+https://github.com/iome-sh/iomesh-client-sdk-python.git#egg=iomeshclient"
# or clone:
git clone https://github.com/iome-sh/iomesh-client-sdk-python.git
cd iomesh-client-sdk-python
pip install -e .
```

Dev extras (tests / ruff):

```bash
pip install -e ".[dev]"
```

## Quick start — publish an org heartbeat

Connect, ensure a stream under `dept.*`, and publish a single organizational heartbeat (ops pulse). Agents and workers pull the same subjects as durable consumers.

```python
from iomeshclient import ConnectOptions, StreamConfig, connect

nc = connect(
    ConnectOptions(
        url="http://127.0.0.1:8422",
        tenant="dept.engineering",
        org="acme-org",
        workspace="ws_default",
    )
)

info = nc.create_stream(
    StreamConfig(
        name="EVENTS",
        subjects=["dept.engineering.events.>"],
    )
)
if info is not None:
    print(f"stream={info.name} subjects={info.subjects}")

# Organizational heartbeat (ops pulse) — public lexicon: heartbeat / pulse only.
ack = nc.publish(
    "EVENTS",
    "dept.engineering.events.demo",
    b'{"hello":"mesh","kind":"org_heartbeat"}',
)
print(f"published seq={ack.seq} subject={ack.subject} partition={ack.partition}")
```

Runnable framing (publish + optional pull): [`examples/org_heartbeat_publish.py`](examples/org_heartbeat_publish.py).

```bash
export IOMESH_URL=http://127.0.0.1:8422
python examples/org_heartbeat_publish.py
IOMESH_PULL=1 python examples/org_heartbeat_publish.py
```

Needs a local/stage broker. Offline stage smoke ≠ live APPLY.

## KV

```python
from iomeshclient import CreateBucketConfig

nc.create_bucket("agent-state", CreateBucketConfig(history=5))  # 409 → name-only OK
nc.put("agent-state", "worker-1.checkpoint", b"seq=42")
entry = nc.get("agent-state", "worker-1.checkpoint")
print(entry.revision, entry.value)
keys = nc.list_keys("agent-state", prefix="worker")
nc.delete("agent-state", "worker-1.checkpoint")
```

## Memory helpers (dual_write OFF by default)

Async local-primary path publishes to `MEMORY_INGEST`. **dual_write is OFF by default** — `sync=False` means no sync sidecar call.

```python
from iomeshclient import MemoryEnvelope

env = MemoryEnvelope(role="user", content="lease rotation due Q3", session_id="sess-1")

# Async only (default dual_write OFF)
res = nc.dual_write_memory_turn("dept.research", env)
print(res.async_ack.seq)

# Optional audit dual-write (fail-open on sync errors)
res = nc.dual_write_memory_turn("dept.research", env, sync=True)
if res.sync_err:
    print("sync failed open:", res.sync_err)
elif res.sync:
    print("sync memory_id", res.sync.memory_id)
```

### Related (multi-hop lite) + ops digest

```python
# Multi-hop lite · not full graph RAG · not Memory GA
related = nc.retrieve_memory_related(
    "dept.research",
    seed_entity="person:alice",
    max_hops=2,
    limit=10,
)
for hit in related.memories:
    print(hit.id, hit.hop_distance, hit.summary)

# Ops heartbeat digest (ops GA-path framing; knowledge/analytical Beta)
digest = nc.export_ops_digest("dept.ops", window="day", horizon="ops")
print(digest.window, len(digest.patterns), digest.honesty)
```

Honesty: not freemium palace · not product Memory GA · not control-plane GA · dual_write OFF elsewhere.

## Catalog (fail-open)

Discover governed data products via broker catalog and/or portal federation. Path cascade matches Go (`/v1/catalog/*` then `/v17`/`/v16` portal). Soft failures return empty `CatalogResult` with `source=fail-open` — not control-plane GA.

```python
from iomeshclient import format_catalog, format_product_detail

res = nc.list_catalog("")  # optional query / mesh_layer filter
print(format_catalog(res))
for p in res.products:
    print(p.id, p.layer, p.subject)

product, meta = nc.get_catalog_product("ops-incidents")
print(format_product_detail(product, meta))
```

## Policy evaluate (fail-open)

Remote tool policy (`POST /v1/policy/evaluate`). Mode `off` skips the network. Enforce only blocks when mesh explicitly denies (`should_block_tool`).

```python
from iomeshclient import POLICY_ENFORCE, POLICY_ADVISORY, PolicyInput

dec = nc.evaluate_policy(
    PolicyInput(tool="run_shell", mode=POLICY_ENFORCE)
)
if dec.should_block_tool():
    print("blocked:", dec.summary())
else:
    print(dec.summary())  # allow / advisory deny still fail-open for tools
```

Modes: `off` (default) · `advisory` · `enforce`. Missing broker path → `source=unavailable` or `fail-open` (Allow true).

## Context (fail-open)

Agent prompt-injection helper (`POST /v1/context/query`). Soft failures return empty text — never raise for missing context plane.

```python
from iomeshclient import format_context_snippet

res = nc.query_context("incidents", workspace="ws1", include_lineage=True)
print(res.text, res.ok, res.source)
print(format_context_snippet(res))

# Always include_lineage=true; empty string on fail-open
snip = nc.context_snippet("sdk dogfood", workspace=".")
```

## Format helpers + connection status

Operator diagnostics (not product GA) — pure stream tables plus a dual health/ready probe snapshot:

```python
from iomeshclient import format_streams, format_stream_detail, format_connection_status

print(format_streams(nc.list_streams()))
print(format_stream_detail(nc.get_stream("EVENTS")))

status = nc.connection_status()  # health then ready; both always run
print(format_connection_status(status))
print(status.result, status.health_ok, status.ready_ok)
```

## Kafka Produce subset

Produce-only mesh Kafka protocol client for integrations / pilots (not a full Kafka consumer):

```python
from iomeshclient import KafkaClient
# or: from iomeshclient.kafka import KafkaClient

with KafkaClient("127.0.0.1:9423") as kc:
    offset = kc.produce("events", 0, None, b'{"hello":"mesh"}')
    print("offset", offset)
```

## connectorsdk

Partner webhook helpers (HMAC + subjects + observation envelope):

```python
from iomeshclient.connectorsdk import (
    DEFAULT_HMAC_PREFIX,
    compute_hmac_sha256,
    normalize_envelope,
    publish_headers,
    subject_for_department,
    verify_hmac,
)

verify_hmac(secret, body, signature)  # raises on mismatch
subj = subject_for_department("engineering", "slack")  # dept.engineering.events.slack
payload = normalize_envelope(
    "slack", "engineering", "slack",
    external_id="Ev001", event_type="message",
    event={"text": "hello"},
)
headers = publish_headers("slack", "engineering", "Ev001", "slack")
nc.publish("EVENTS", subj, payload, headers=headers)
```

## Pull consume

```python
from iomeshclient import CreateConsumerConfig, PullSubscribeConfig

nc.create_consumer(
    CreateConsumerConfig(
        stream="EVENTS",
        name="worker-1",
        filter_subject="dept.engineering.events.>",
    )
)

sub = nc.pull_subscribe(
    PullSubscribeConfig(stream="EVENTS", consumer="worker-1")
)
for msg in sub.fetch(10, max_wait_ms=5000):
    print(msg.seq, msg.subject, msg.data)
    msg.ack()
```

## Health / wait_ready / connection_status

```python
nc.health()  # GET /health
nc.ready()   # GET /ready, then /readyz if 404

# Poll until ready (optional health gate)
result = nc.wait_ready(timeout_sec=30.0, interval_sec=0.5, require_health=False)
print(result.elapsed_sec, result.attempts)

# One-shot dual probe snapshot (operator diagnostics)
status = nc.connection_status()
print(status.result, status.health_ms, status.ready_ms)
```

## Honesty / non-claims

- **MIT edge client only** — not freemium palace access, not control-plane GA.
- **Beta / pre-1.0** — APIs may change before 1.0.
- **No Memory GA invent** — memory helpers are edge/async + optional fail-open sync; related is multi-hop **lite**.
- **dual_write OFF by default** — `dual_write_memory_turn(..., sync=False)`; enable explicitly for audit path only.
- **Catalog / policy / context fail-open** — missing paths and soft errors do not raise; enforce blocks only on explicit mesh deny.
- **Formatters / connection status** — operator diagnostics only, not product GA surfaces.
- **Kafka Produce subset only** — not a full consumer/admin client; for mesh integrations / pilots.
- **Requires a broker** — unit tests mock HTTP/TCP; live examples need local/stage mesh.

## Residual Next

- **Live PyPI** — package/version ready; publish gated on `secrets.PYPI_TOKEN` residual (see [RELEASING.md](RELEASING.md)).
- **Kafka consumer residual** — Produce subset ships; full consumer/admin not in scope yet.
- **tool-marketing adopt optional** — thin adapter only when real mesh I/O (e.g. outbox → aion ingest) is wired; not a GTM rewrite vehicle.

## Related

| Project | Role |
|---------|------|
| [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go) | Official Go client (broader surface) |
| [iomesh-tui](https://github.com/iome-sh/iomesh-tui) | Agent TUI |
| [iome.sh](https://iome.sh) | Product home |

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
# optional
ruff check src tests examples
```

Release process: [RELEASING.md](RELEASING.md). See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © IOMesh Technology Ltd.
