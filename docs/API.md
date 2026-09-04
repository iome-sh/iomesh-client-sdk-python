# API surface inventory (`iomeshclient` v0.10)

> **Status:** Beta / **pre-1.0** · MIT edge client only  
> **Not claimed:** freemium palace · control-plane GA · Memory GA · dual_write ON by default · Kafka full client · invent 1.0  
> **Parity target:** [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go) (`iomeshclient` + `kafka` + `connectorsdk`)

This page is an **inventory of public modules and methods**, not a full reference manual.
Wire details and honesty notes live in module docstrings and [README.md](../README.md).
For the future 1.0 checklist (not met yet), see [1.0-bar.md](1.0-bar.md).

**Package marker:** PEP 561 `py.typed` ships in the wheel (typed package; gradual typing).

---

## Connect / client core

| Symbol | Kind | Notes |
|--------|------|--------|
| `connect(options: ConnectOptions) -> Client` | factory | No network I/O |
| `connect_from_env(environ=None) -> Client` | factory | `IOMESH_URL` required; optional tenant/org/workspace/token/timeout; `IOMESH_REQUIRE_ORG` fail-closes catalog/consume when org is empty |
| `ConnectOptions` | dataclass | `url`, `timeout`, `tenant`, `org`, `workspace`, `bearer_token`, `user_agent`, `require_org` |
| `Client` | class | HTTP plane; mixins for KV, memory, metering, catalog, policy, context, liveview, status |
| `VERSION` / `__version__` | str | e.g. `0.10.1` |
| `ClientError` / `APIError` | exceptions | Transport / non-2xx |

**Headers:** `X-IOMesh-Tenant`, `X-IOMesh-Org`, `X-IOMesh-Workspace`; optional `Authorization: Bearer …`  
`ConnectOptions.org` / `IOMESH_ORG` is sent as `X-IOMesh-Org` on every request when set. Omitting org leaves isolation to the broker: local/dev may mix shared-stream reads; hosted brokers may reject catalog/consume. `require_org` / `IOMESH_REQUIRE_ORG=1` raises `ClientError` before the request. No library default org.  
**User-Agent:** `iomesh-client-sdk-python/<VERSION>`

---

## Health / ready

| Method | Path / behavior | Honesty |
|--------|-----------------|---------|
| `Client.health()` | `GET /health` | raises on failure |
| `Client.ready()` | `GET /ready` then `/readyz` | raises on failure |
| `Client.wait_ready(timeout_sec, interval_sec, require_health=False)` | poll | returns `WaitReadyResult` |
| `Client.connection_status()` | health + ready probes | operator diagnostics; always both run |
| `format_connection_status` / `aggregate_connection_result` | pure | not product GA |

---

## Streams

| Method | Path / behavior | Honesty |
|--------|-----------------|---------|
| `create_stream` / `ensure_stream` | `POST /v1/streams` (409 → GET) | explicit errors except 409 path |
| `get_stream` / `list_streams` / `delete_stream` | `/v1/streams…` | When `X-IOMesh-Org` is set, hosted brokers return that org's streams plus shared persist; without the header, hosted brokers may reject list/consume |
| `list_stream_messages(stream, opts?)` | `GET …/messages` | discovery; replay requires tenant header or operator replay flag; non-2xx → `APIError` |
| Types | `StreamConfig`, `StreamInfo` (`org_id`; empty = shared persist), `StreamMessage`, `ListStreamMessagesOptions` | |
| Formatters | `format_streams`, `format_stream_detail` | operator diagnostics |

---

## Publish

| Method | Path / behavior | Honesty |
|--------|-----------------|---------|
| `Client.publish(stream, subject, payload, *, partition_key, partition, headers)` | `POST /v1/streams/{stream}/publish` | base64 payload; returns `PubAck` |

Public lexicon for org-tool events: **heartbeat / pulse** (e.g. on `dept.*`).

---

## Consumers / durable pull

| Method | Path / behavior | Honesty |
|--------|-----------------|---------|
| `create_consumer` / `ensure_consumer` | `POST …/consumers` (409 → name-only) | durable consumer config |
| `pull_subscribe(PullSubscribeConfig)` | ensure consumer → `Subscription` | |
| `consumer_fetch` / `Subscription.fetch` | `POST …/fetch` | batch + `max_wait_ms`; base64 decode; sends `X-IOMesh-Org` when org is set; omit-org can mix shared streams unless `require_org` |
| `consumer_ack` / `consumer_nack` / `Msg.ack` / `Msg.nack` | `POST …/ack` / `…/nack` | Ack is served. **Nack** is a Go-parity helper; serving broker may 404 |
| Types | `CreateConsumerConfig`, `ConsumerInfo`, `PullSubscribeConfig`, `Subscription`, `Msg` | |
| Formatters | `format_msg`, `format_msgs`, `format_consumer_info` | operator diagnostics |

Example: [`examples/pull_loop.py`](../examples/pull_loop.py) (needs broker).

---

## KV

| Method | Path / behavior | Honesty |
|--------|-----------------|---------|
| `create_bucket` / `ensure_bucket` | `POST /v1/kv/{name}` | 409 → name-only `BucketInfo` |
| `put` / `get` / `delete` / `list_keys` | `/v1/kv/…` | value base64 on wire |
| Types | `CreateBucketConfig`, `BucketInfo`, `KVEntry`, `PutResult` | |
| Formatters | `format_put_result`, `format_bucket_info`, `format_kv_entry`, `format_kv_keys` | operator diagnostics |

---

## Memory helpers

| Method | Behavior | Honesty |
|--------|----------|---------|
| `publish_memory_ingest` | publish `MEMORY_INGEST` | edge only |
| `dual_write_memory_turn(..., sync=False)` | async primary; optional sync | **dual_write OFF by default** |
| `ingest_memory_turn` | sync ingest path | **sidecar-on-operator**; broker-only URL may return `status=accepted` + `note` (keep `note`; not a palace write) |
| `retrieve_memory` | retrieve HTTP/RPC | sidecar-on-operator · not Memory GA invent |
| `request_memory_recall` / `request_memory_recall_full` | publish `MEMORY_RPC` subject `{tenant}.memory.retrieve.request` | async fire-and-forget edge publish |
| `retrieve_memory_related` | multi-hop **lite** | sidecar-on-operator · not full graph RAG |
| `export_ops_digest` | ops digest export | ops horizon framing · knowledge Beta · not a Memory Ops Pack |
| Types | `MemoryEnvelope`, `MemoryRecallRequest`, `MemoryRetrieveRequest`, hits, ops-digest structs | |
| Constants | `STREAM_MEMORY_INGEST`, `STREAM_MEMORY_RPC` | |

**Not Memory GA.** Async recall ≠ product Memory GA. Local memory tools run on the operator machine. This client is not Memory GA.

---

## Metering (dept.* heartbeat / pulse)

| Method | Behavior | Honesty |
|--------|----------|---------|
| `emit_dept_event(DeptEvent)` | publish stream `dept`, subject = event type | org heartbeat / ops pulse |
| `emit_llm_call(LLMCallEvent)` | type `dept.agent.llm_call` + structured payload | multi-tenant enrich from client options |
| Constants | `STREAM_DEPT`, `TYPE_DEPT_AGENT_LLM_CALL` | public lexicon heartbeat/pulse only |

Example: [`examples/emit_llm_call.py`](../examples/emit_llm_call.py).

---

## Catalog (fail-open)

| Method | Behavior | Honesty |
|--------|----------|---------|
| `list_catalog(query="")` | path cascade (broker + portal) | empty / fail-open when no path works |
| `get_catalog_product(id)` | detail cascade + list filter | returns `(CatalogProduct, CatalogResult)` |
| Formatters | `format_catalog`, `format_product_detail` | operator views |

**Not** control-plane GA / freemium palace catalog invent. **Data-products only** (not the integrations catalog). Knowledge layer is **Beta**. Listing ≠ Connected. Does not wrap webhook install or OAuth. Mesh `/v1/catalog/*` probes 404 on current serving broker; live list is portal `/v17` (and `/v16` marketing).

---

## Policy evaluate (fail-open)

| Method | Behavior | Honesty |
|--------|----------|---------|
| `evaluate_policy(PolicyInput)` | `POST /v1/policy/evaluate` | modes `off` / `advisory` / `enforce`; serving broker may 404 → unavailable |
| `PolicyDecision.should_block_tool()` | enforce + mesh deny only | soft errors fail-open |
| `normalize_policy_mode` | helper | |
| Constants | `POLICY_OFF`, `POLICY_ADVISORY`, `POLICY_ENFORCE` | |

---

## Context (fail-open)

| Method | Behavior | Honesty |
|--------|----------|---------|
| `query_context(...)` | `POST /v1/context/query` | fail-open empty on soft failure; serving broker may not register the path |
| `context_snippet(...)` | always `include_lineage=true` | empty string on soft failure |
| `format_context_snippet` | pure text + lineage block | agent prompt helper, not product GA |
| Types | `ContextResult`, `LineageRef` | |

---

## Liveview / v3 registry

| Method | Behavior | Honesty |
|--------|----------|---------|
| `register_processor(ProcessorConfig)` | `POST /v3/registry/processors` | **409 = success** (idempotent) |
| `list_live_views(tenant_id)` | `GET /v3/registry/liveviews?tenant_id=` | explicit errors (not fail-open) |
| Types / constants | `ProcessorConfig`, `DataProduct`, `LiveView`, `PROCESSOR_TYPE_*` | edge HTTP only · not liveview product GA |

---

## Kafka Produce subset

| Symbol | Behavior | Honesty |
|--------|----------|---------|
| `KafkaClient(addr).produce(topic, partition, key, value) -> offset` | Produce protocol subset | **Produce only** — no consumer/admin |
| `KafkaClient.close` / context manager | | |

Import: `from iomeshclient import KafkaClient` or `from iomeshclient.kafka import KafkaClient`.

---

## connectorsdk

Local HMAC + subject/envelope helpers (stdlib). **Not** mesh connector HTTP, OAuth, or Connected. Import: `from iomeshclient.connectorsdk import …`.

| Area | Symbols |
|------|---------|
| HMAC | `compute_hmac_sha256`, `verify_hmac`, `ErrMissingSecret`, `ErrMissingSignature`, `ErrInvalidSignature`, header constants |
| Subjects | `subject_for_department`, `subject_for_document`, `subject_for_embedding`, `subject_for_warehouse`, `subject_for_metric` |
| Envelope | `normalize_envelope`, `publish_headers` |

---

## Known gaps

| Gap | Status |
|-----|--------|
| **PyPI live publish** | Version/package ready; upload needs `secrets.PYPI_TOKEN` (see [RELEASING.md](../RELEASING.md)) |
| **Kafka consumer / admin** | Not in scope — Produce subset only |
| **Full mypy / pyright CI** | `py.typed` present; strict type CI optional |
| **1.0 stability bar** | Explicit checklist in [1.0-bar.md](1.0-bar.md) — **not 1.0 yet** |
| **Go surface parity matrix** | Expanding; document remaining deltas before major |
| **Memory GA / dual_write product** | dual_write OFF by default · helpers are edge/async · sidecar-on-operator |
| **HTTP `/nack`** | Client helper exists; serving broker registers ack, not nack (404 is honest) |
| **Integrations / OAuth / portal session** | Not this SDK. Data-products catalog ≠ Connected. Knowledge Beta. |
| **Broker `/v1/catalog/*`** | Cascade (404 → portal `/v17` / `/v16`) |

---

## Versioning note

This inventory tracks **v0.10.x Beta**. Semver major `1.0.0` will only ship when the [1.0 bar](1.0-bar.md) is met — **v0.10 does not invent or declare 1.0**.
