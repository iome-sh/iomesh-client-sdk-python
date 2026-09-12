# I/O Mesh Client SDK for Python

[![CI](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/iome-sh/iomesh-client-sdk-python)](https://github.com/iome-sh/iomesh-client-sdk-python/releases/latest)
[![Status](https://img.shields.io/badge/status-Beta%20pre--1.0-yellow.svg)](#status)

Official **Python client** for the [I/O Mesh](https://iome.sh) broker: HTTP publish/pull, streams, KV, and a Kafka Produce subset. **MIT**. **Beta / pre-1.0**. From [IOMesh](https://iome.sh) (**IOMesh Technology Ltd.**).

Connectors and services publish **organizational heartbeats** (ops **pulse**) on `dept.*` streams; agents and workers consume them with durable pull.

This repository is **edge client code** only — not hosted control-plane access. There is **no live PyPI package** yet; install from git or source.

## Contents

- [Status](#status)
- [Install](#install)
- [Quick start](#quick-start)
- [Environment](#environment)
- [Capabilities](#capabilities)
- [API](#api)
- [Examples](#examples)
- [License](#license)

## Status

Public OSS **[v0.11.1](https://github.com/iome-sh/iomesh-client-sdk-python/releases/tag/v0.11.1)** — **Beta / pre-1.0**. APIs may change before 1.0. See [CHANGELOG.md](CHANGELOG.md) and [docs/WRAP_UP.md](docs/WRAP_UP.md).

- **MIT edge client** — not free mesh control-plane access.
- **Catalog list ≠ Connected.** `list_catalog` is data-product discovery (Knowledge stays Beta), not a connector install or OAuth wrap.
- **Memory helpers** talk to a **local sidecar**. `dual_write_memory_turn` is async-only unless you pass `sync=True`. A mesh-broker URL may 404 retrieve.
- **Nack** is a client helper; the serving broker may 404 until the route exists (ack is served).
- **1.0** only when [docs/1.0-bar.md](docs/1.0-bar.md) is met.

Package `iomeshclient` · User-Agent `iomesh-client-sdk-python/0.11.1`. Parity target: the Go package [`iomeshclient`](https://github.com/iome-sh/iomesh-client-sdk-go).

## Requirements

- Python **3.10+**
- Network access to an I/O Mesh broker (or local foundation)
- **stdlib only** at runtime (`urllib`, `socket`); no third-party runtime deps

## Install

From git or a local clone (until a PyPI release is published — see [RELEASING.md](RELEASING.md)):

```bash
pip install "git+https://github.com/iome-sh/iomesh-client-sdk-python.git#egg=iomeshclient"
# or clone:
git clone https://github.com/iome-sh/iomesh-client-sdk-python.git
cd iomesh-client-sdk-python
pip install -e .
```

Dev extras (tests / ruff):

```bash
pip install -e ".[dev]"
```

## Quick start

Connect, ensure a `dept.*` stream, and publish one organizational heartbeat. Needs a reachable broker.

```python
from iomeshclient import ConnectOptions, StreamConfig, connect

nc = connect(
    ConnectOptions(
        url="http://127.0.0.1:8422",
        tenant="dept.engineering",
        org="org_<cuid2>",
        workspace="",
        department="engineering",
    )
)

info = nc.create_stream(
    StreamConfig(name="EVENTS", subjects=["dept.engineering.events.>"])
)
if info is not None:
    print(f"stream={info.name} subjects={info.subjects}")

ack = nc.publish(
    "EVENTS",
    "dept.engineering.events.demo",
    b'{"hello":"mesh","kind":"org_heartbeat"}',
)
print(f"published seq={ack.seq} subject={ack.subject} partition={ack.partition}")
```

Omit a blank workspace (`workspace=""` / unset `IOMESH_WORKSPACE`) so the broker binds the org **root-default**. This client never invents `workspaces[0]` (creation-order first row is not the root bind). Hosted public ids are `org_`+cuid2 and `ws_`+cuid2 (control-plane minted, opaque — not display-name slugs). Do not invent `acme-org` / `ws_default` as if minted.

Runnable framing (publish + optional pull): [`examples/org_heartbeat_publish.py`](examples/org_heartbeat_publish.py).

```bash
export IOMESH_URL=http://127.0.0.1:8422
export IOMESH_ORG=org_<cuid2>   # CP-minted X-IOMesh-Org
python examples/org_heartbeat_publish.py
IOMESH_PULL=1 python examples/org_heartbeat_publish.py
```

## Environment

`connect_from_env()` reads process env. `IOMESH_URL` is required; the rest are optional. No network I/O on connect.

| Variable | Header / effect |
|----------|-----------------|
| `IOMESH_URL` | Broker base (`http`/`https`) |
| `IOMESH_TENANT` | `X-IOMesh-Tenant` |
| `IOMESH_ORG` | `X-IOMesh-Org` — hosted: CP-minted `org_`+cuid2 |
| `IOMESH_WORKSPACE` | `X-IOMesh-Workspace` — omit blank = broker root-default |
| `IOMESH_DEPARTMENT` | `X-IOMesh-Department` (omit when empty) |
| `IOMESH_BEARER_TOKEN` or `IOMESH_TOKEN` | `Authorization: Bearer` (`BEARER_TOKEN` wins if both set) |
| `IOMESH_TIMEOUT` | Request timeout in seconds (float; default 30) |
| `IOMESH_REQUIRE_ORG` | `1`/`true`/`yes`/`on` — fail-closed catalog/consume when org is empty |

```python
from iomeshclient import connect_from_env

nc = connect_from_env()
```

Hosted brokers isolate catalog and durable pull by `X-IOMesh-Org`. Omitting it can mix shared-stream reads (or the broker may reject). Local/dev brokers still fail-open when org is empty. The library does **not** invent a default org and does **not** mint or validate the cuid2 shape.

## Capabilities

| Capability | Notes |
|------------|--------|
| `connect` / `connect_from_env` | No network I/O; env reads `IOMESH_*` |
| `publish` | `POST /v1/streams/{stream}/publish` → `PubAck` |
| Streams / consumers | Create, list, replay, durable pull; **ack is served**; nack may 404 |
| KV | Create / put / get / delete / list_keys; 409 create → name-only |
| Memory helpers | Edge publish + optional local sidecar HTTP |
| Metering | `emit_dept_event` / `emit_llm_call` → stream `dept` |
| Liveview / registry | `register_processor` (409 = success) · `list_live_views` |
| Catalog | Data-products cascade; fail-open |
| Policy / context | Fail-open evaluate + prompt snippet |
| Format + `connection_status` | Operator string views; dual health/ready snapshot |
| `connectorsdk` | Local HMAC + subjects + envelope; not OAuth |
| Kafka Produce subset | `KafkaClient(addr).produce(...)` |
| Health / `wait_ready` | `GET /health`, `/ready` then `/readyz` |
| Typing | PEP 561 `py.typed` (gradual) |

## API

Surface inventory: **[docs/API.md](docs/API.md)**. 0.x notes: [docs/WRAP_UP.md](docs/WRAP_UP.md). Future 1.0 checklist: [docs/1.0-bar.md](docs/1.0-bar.md).

### Metering

```python
from iomeshclient import ConnectOptions, LLMCallEvent, connect

nc = connect(
    ConnectOptions(
        url="http://127.0.0.1:8422",
        tenant="dept.engineering",
        org="org_<cuid2>",
        workspace="",
        department="engineering",
    )
)
ack = nc.emit_llm_call(
    LLMCallEvent(
        tenant="dept.engineering",
        session_id="sess-1",
        model="deepseek-v4-flash",
        model_id="deepseek-v4-flash",
        duration_ms=12,
        attempts=1,
        est_usd=0.001,
        prompt_tokens=5,
        total_tokens=10,
    )
)
print(ack.seq, ack.subject)
```

Runnable: [`examples/emit_llm_call.py`](examples/emit_llm_call.py).

### KV

```python
from iomeshclient import CreateBucketConfig

nc.create_bucket("agent-state", CreateBucketConfig(history=5))
nc.put("agent-state", "worker-1.checkpoint", b"seq=42")
entry = nc.get("agent-state", "worker-1.checkpoint")
print(entry.revision, entry.value)
```

### Memory

Async local-primary path publishes to `MEMORY_INGEST`. Pass `sync=True` for an optional sidecar write. Local memory HTTP runs on the operator machine.

```python
from iomeshclient import MemoryEnvelope, MemoryRecallRequest

env = MemoryEnvelope(role="user", content="lease rotation due Q3", session_id="sess-1")
res = nc.dual_write_memory_turn("dept.research", env)  # sync=False
print(res.async_ack.seq)

ack = nc.request_memory_recall("dept.research", "lease notes", limit=8)
print(ack.stream, ack.seq, ack.subject)
```

Related is multi-hop **lite** (`retrieve_memory_related`). `export_ops_digest` is an ops heartbeat digest.

### Catalog

Discover governed **data products**. Path cascade matches Go (`/v1/catalog/*` then `/v17`/`/v16` portal). Soft failures return empty `CatalogResult` with `source=fail-open`. This wrapper does not expose webhook URLs or OAuth install.

```python
from iomeshclient import format_catalog

res = nc.list_catalog("")
print(format_catalog(res))
```

### Policy and context

```python
from iomeshclient import POLICY_ENFORCE, PolicyInput, format_context_snippet

dec = nc.evaluate_policy(PolicyInput(tool="run_shell", mode=POLICY_ENFORCE))
if dec.should_block_tool():
    print("blocked:", dec.summary())

res = nc.query_context("incidents", workspace="ws1", include_lineage=True)
print(format_context_snippet(res))
```

Modes: `off` (default) · `advisory` · `enforce`. Missing broker path → fail-open (Allow true). Context soft-fails to empty text.

### Format helpers + connection status

```python
from iomeshclient import format_connection_status, format_streams

print(format_streams(nc.list_streams()))
print(format_connection_status(nc.connection_status()))
```

Stream replay (non-2xx raises):

```python
from iomeshclient import ListStreamMessagesOptions

msgs = nc.list_stream_messages("EVENTS", ListStreamMessagesOptions(from_seq=1, limit=50))
for m in msgs:
    print(m.seq, m.subject, m.payload)
```

### Kafka Produce subset

```python
from iomeshclient import KafkaClient

with KafkaClient("127.0.0.1:9423") as kc:
    offset = kc.produce("events", 0, None, b'{"hello":"mesh"}')
    print("offset", offset)
```

### connectorsdk

Local partner webhook helpers (GitHub-style HMAC + subjects + observation envelope). Not mesh connector HTTP, not OAuth:

```python
from iomeshclient.connectorsdk import (
    normalize_envelope,
    publish_headers,
    subject_for_department,
    verify_hmac,
)

verify_hmac(secret, body, signature)
subj = subject_for_department("engineering", "slack")
payload = normalize_envelope(
    "slack", "engineering", "slack",
    external_id="Ev001", event_type="message",
    event={"text": "hello"},
)
headers = publish_headers("slack", "engineering", "Ev001", "slack")
nc.publish("EVENTS", subj, payload, headers=headers)
```

### Pull consume

```python
from iomeshclient import CreateConsumerConfig, PullSubscribeConfig

nc.create_consumer(
    CreateConsumerConfig(
        stream="EVENTS",
        name="worker-1",
        filter_subject="dept.engineering.events.>",
    )
)
sub = nc.pull_subscribe(PullSubscribeConfig(stream="EVENTS", consumer="worker-1"))
for msg in sub.fetch(10, max_wait_ms=5000):
    print(msg.seq, msg.subject, msg.data)
    msg.ack()
```

Runnable: [`examples/pull_loop.py`](examples/pull_loop.py).

```bash
export IOMESH_URL=http://127.0.0.1:8422
export IOMESH_ORG=org_<cuid2>
IOMESH_PUBLISH=1 python examples/pull_loop.py
```

### Health / wait_ready

```python
nc.health()
nc.ready()
result = nc.wait_ready(timeout_sec=30.0, interval_sec=0.5, require_health=False)
print(result.elapsed_sec, result.attempts)
```

## Examples

| Example | What it shows |
|---------|----------------|
| [`examples/org_heartbeat_publish.py`](examples/org_heartbeat_publish.py) | Publish + optional pull of an org heartbeat |
| [`examples/pull_loop.py`](examples/pull_loop.py) | Durable fetch + ack (optional publish seed) |
| [`examples/emit_llm_call.py`](examples/emit_llm_call.py) | Metering pulse on stream `dept` |

Needs a local or stage broker. Running an example locally is not a production rollout.

## Known limitations

- **PyPI** — package is ready; a live upload needs `secrets.PYPI_TOKEN` (see [RELEASING.md](RELEASING.md)).
- **Kafka consumer** — Produce subset only; full consumer/admin is not in scope yet.
- **HTTP `/nack`** — helper kept for Go parity; serving broker does not register the route.
- **1.0** — only when [docs/1.0-bar.md](docs/1.0-bar.md) is met.

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
ruff check src tests examples
```

Release process: [RELEASING.md](RELEASING.md). See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Related

| Project | Role |
|---------|------|
| [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go) | Official Go client (broader surface) |
| [docs/API.md](docs/API.md) | Python surface inventory |
| [iomesh-tui](https://github.com/iome-sh/iomesh-tui) | Agent TUI |
| [iome.sh](https://iome.sh) | Product home |

## Contact

- Product / questions: [hello@iome.sh](mailto:hello@iome.sh)
- Security: [security@iome.sh](mailto:security@iome.sh) — see [SECURITY.md](SECURITY.md)

## License

[MIT](LICENSE) © IOMesh Technology Ltd.
