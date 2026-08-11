# I/O Mesh Client SDK for Python

[![CI](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/iome-sh/iomesh-client-sdk-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI status](https://img.shields.io/badge/status-Beta%20pre--1.0-yellow.svg)](#status)

Official **Python client SDK** for the [I/O Mesh](https://iome.sh) broker (HTTP plane).

Publish and pull **organizational heartbeats** (ops **pulse**) on `dept.*` streams: connectors and services emit org-tool events; agents and workers consume them via durable pull. Public lexicon is **heartbeat / pulse** only.

This repository is **MIT edge client code** only — not free mesh control-plane access, not a freemium hosted palace, and not product Memory GA. Surfaces are **Beta** / pre-1.0. Official open-source tooling from [IOMesh](https://iome.sh) (**IOMesh Technology Ltd.**).

| Capability (v0.1) | Notes |
|-------------------|--------|
| `connect` + tenant / org / workspace / bearer headers | No network I/O on connect |
| `publish` (base64 payload) | `POST /v1/streams/{stream}/publish` → `PubAck` |
| Streams: create / ensure / get / list / delete | 409 conflict → best-effort GET |
| Consumers: create / ensure / fetch / ack / nack / pull_subscribe | Fetch decodes base64 payloads |
| Health / ready | `GET /health`, `GET /ready` then `/readyz` |

Parity target: the Go package [`iomeshclient`](https://github.com/iome-sh/iomesh-client-sdk-go) core HTTP plane. Python v0.1 does **not** yet ship KV helpers, memory helpers, connectorsdk, or Kafka Produce.

> **Package:** `iomeshclient`  
> **Wire headers:** `X-IOMesh-Tenant`, `X-IOMesh-Org`, `X-IOMesh-Workspace`  
> **User-Agent:** `iomesh-client-sdk-python/0.1.0`  
> **Status:** public OSS **v0.1.0** (pre-1.0, **Beta**)  
> **Go SDK:** [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go)

## Requirements

- Python **3.10+**
- Network access to an I/O Mesh broker (or local foundation)
- **stdlib only** for the client (`urllib`); no third-party runtime deps

## Install

From source (until a PyPI release is published):

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

Needs a local/stage broker. Offline stage smoke ≠ live APPLY. `dual_write` is not claimed.

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

## Health

```python
nc.health()  # GET /health
nc.ready()   # GET /ready, then /readyz if 404
```

## Honesty / non-claims

- **MIT edge client only** — not freemium palace access, not control-plane GA.
- **Beta / pre-1.0** — APIs may change before 1.0.
- **No Memory GA invent** — this release is core HTTP (streams / publish / pull / health).
- **dual_write not claimed** — examples do not assert dual-write or hosted memory.
- **Requires a broker** — unit tests mock HTTP; live examples need local/stage mesh.

## Related

| Project | Role |
|---------|------|
| [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go) | Official Go client (broader surface: KV, memory helpers, connectorsdk, Kafka Produce) |
| [iomesh-tui](https://github.com/iome-sh/iomesh-tui) | Agent TUI |
| [iome.sh](https://iome.sh) | Product home |

## Development

```bash
pip install -e ".[dev]"
python -m pytest -q
# optional
ruff check src tests examples
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © IOMesh Technology Ltd.
