# Changelog

All notable changes to `iomesh-client-sdk-python` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.3] — 2026-09-04

Patch: optional fail-closed `X-IOMesh-Org` on catalog/consume, plus pull-example isolation docs. **Does not declare 1.0 / GA / live PyPI / Memory GA / Connected.**

### Added

- **`ConnectOptions.require_org` / `IOMESH_REQUIRE_ORG`** — optional fail-closed catalog/consume/publish when org is empty (`ClientError` instead of omitting `X-IOMesh-Org`). Default off for local/dev. Closes [#19](https://github.com/iome-sh/iomesh-client-sdk-python/issues/19).

### Changed

- **Docs** — README, `docs/API.md`, and pull/publish examples document `IOMESH_ORG` → `X-IOMesh-Org` on fetch/ack/create_consumer/publish. Omitting org can mix shared-stream reads (or hosted brokers may reject). No library default org. Closes [#20](https://github.com/iome-sh/iomesh-client-sdk-python/issues/20).
- Version bump **0.10.2 → 0.10.3**

### Honesty

- MIT edge client · Beta · dual_write **OFF** · not Memory GA · catalog ≠ Connected

## [0.10.2] — 2026-09-04

Patch: additive `StreamInfo.org_id`, public copy hygiene, and serving-plane honesty. **Does not declare 1.0 / GA / live PyPI / Memory GA / Connected.**

### Added

- **`StreamInfo.org_id`** — decode JSON `org_id` from `GET /v1/streams` and `GET /v1/streams/{name}` (unknown keys ignored; empty string is shared persist)
- **`MemoryIngestResponse.note`** — keep the serving-broker stub `note` (do not drop it so `status=accepted` looks like a palace write)
- **User-Agent** — `iomesh-client-sdk-python/0.10.2`

### Changed

- **Docs** — public README, examples, API inventory, 0.x status, and changelog copy hygiene: strip internal serials, private repository names, and internal workflow phrasing from user-facing docs (#18)
- Docs / docstrings: nack is a client helper (broker may 404); catalog is **data-products** (Knowledge Beta; listing ≠ Connected; mesh `/v1/catalog/*` cascade); memory HTTP is sidecar-on-operator; replay requires tenant header or operator replay flag; connectorsdk is local HMAC only
- `examples/pull_loop.py` — `IOMESH_NACK=1` is a client helper demo (broker may 404)
- Version bump **0.10.1 → 0.10.2** (additive org_id + copy hygiene; no intentional breaking API changes)

### Honesty

- MIT edge client · Beta · dual_write **OFF** · not Memory GA · not Knowledge GA · not Connected · not a Memory Ops Pack

## [0.10.1] — 2026-08-11

Docs-only wrap-up closeout for the active **0.x feature continuum**. **Does not declare or invent 1.0 / GA / live PyPI.**

### Added

- **Wrap-up status** — [`docs/WRAP_UP.md`](docs/WRAP_UP.md): 0.1–0.10 summary table, honest install paths (git / GitHub Release assets / local wheel), residual park list only
- **User-Agent** — `iomesh-client-sdk-python/0.10.1`

### Changed

- Version bump **0.10.0 → 0.10.1** (docs closeout; no intentional API changes)
- README **Status (wrap-up)** section + Residual Next reduced to parked items only
- RELEASING note: v0.10.0 is the feature continuum tip; 0.10.1 is an optional docs patch

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- dual_write **OFF** by default elsewhere · Kafka Produce subset only
- **0.x continuum closed** at feature tip v0.10.0; true **1.0 only when [1.0-bar.md](docs/1.0-bar.md) gates are met**

## [0.10.0] — 2026-08-11

1.0-readiness residual polish — typing marker, public API inventory, future 1.0 bar checklist, durable pull example. **Does not declare or invent 1.0 / GA.**

### Added

- **PEP 561** — `src/iomeshclient/py.typed` marker; hatch wheel `force-include` so the marker ships in the built wheel
- **API inventory** — [`docs/API.md`](docs/API.md) table of public modules/methods by area (connect, streams, publish, consumers, KV, memory, metering, catalog, policy, context, kafka produce, liveview, formatters) with Beta honesty + residual gaps
- **1.0 bar checklist** — [`docs/1.0-bar.md`](docs/1.0-bar.md) future gates (tests, docs, semver, PyPI, Go parity) with explicit **not 1.0 yet** banner
- **Example** — `examples/pull_loop.py` residual-honest durable pull fetch/ack demo (needs broker; dual_write not claimed)
- **User-Agent** — `iomesh-client-sdk-python/0.10.0`

### Changed

- Version bump **0.9.0 → 0.10.0** (no intentional breaking API changes)
- README Residual Next / capability table → v0.10 framing; docs index pointers

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- **v0.10 ≠ 1.0** — residual polish toward a future bar only; dual_write **OFF** by default elsewhere · Kafka Produce subset only
- Typing marker enables gradual typing consumers; full mypy/pyright CI remains optional residual

## [0.9.0] — 2026-08-11

Async memory recall + `connect_from_env` residual polish — wire parity with Go `RequestMemoryRecall` / `RequestMemoryRecallFull`; env-based connect helper (stdlib only).

### Added

- **Async memory recall** — `MemoryRecallRequest`; `Client.request_memory_recall(tenant_id, query, limit=0)` and `request_memory_recall_full(req)` → publish stream `MEMORY_RPC`, subject `{tenant}.memory.retrieve.request`, JSON body type `memory_recall` (optional `session_id` / `limit`)
- **`connect_from_env()`** — reads `IOMESH_URL` (required), optional `IOMESH_TENANT` / `IOMESH_ORG` / `IOMESH_WORKSPACE` / `IOMESH_BEARER_TOKEN` or `IOMESH_TOKEN` / `IOMESH_TIMEOUT`; clear `ClientError` when URL missing
- **Exports** — `MemoryRecallRequest`, `STREAM_MEMORY_RPC`, `STREAM_MEMORY_INGEST`, `connect_from_env`
- **Tests** — mock HTTP publish path for recall; monkeypatch env for `connect_from_env`
- **User-Agent** — `iomesh-client-sdk-python/0.9.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Async recall is **edge MEMORY_RPC publish** only — not invent product Memory GA · dual_write **OFF** by default elsewhere · Kafka Produce subset only
- `connect_from_env` is convenience wiring for local/stage scripts; no network I/O on connect

## [0.8.0] — 2026-08-11

Liveview / v3 registry residual polish — processor register + list live views; wire parity with Go `RegisterProcessor` / `ListLiveViews` (stdlib only).

### Added

- **Liveview / registry** — `ProcessorConfig`, `DataProduct` (minimal), `LiveView`; constants `PROCESSOR_TYPE_FILTER` / `MAP` / `ENRICH`
- **`Client.register_processor(cfg)`** — `POST /v3/registry/processors`; **409 conflict = success** (idempotent re-register)
- **`Client.list_live_views(tenant_id)`** — `GET /v3/registry/liveviews?tenant_id=`; empty body → `[]`; non-2xx → `APIError` (not fail-open)
- **Exports** — `ProcessorConfig`, `DataProduct`, `LiveView`, processor type constants
- **Tests** — `test_liveview.py` mock HTTP register + list path
- **User-Agent** — `iomesh-client-sdk-python/0.8.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Registry helpers are **edge HTTP** only — **not** invent liveview product GA · dual_write **OFF** by default elsewhere · Kafka Produce subset only
- List is explicit (raises on non-2xx); not fail-open catalog/policy/context semantics

## [0.7.0] — 2026-08-11

Metering residual polish — dept.* organizational heartbeat / ops pulse emit helpers; wire parity with Go `EmitDeptEvent` / `EmitLLMCall` (stdlib only, publish path).

### Added

- **Metering** — `DeptEvent`, `LLMCallEvent`; `Client.emit_dept_event(ev)` → publish stream `dept` subject = event type → `PubAck`; `Client.emit_llm_call(call)` → type `dept.agent.llm_call` + structured payload (model, tokens, duration_ms, est_usd, …)
- **Multi-tenant enrich** — when unset on the body, payload gains `tenant` / `org` / `workspace` from client Connect options (parity with Go / iomesh-tui)
- **Exports** — `STREAM_DEPT`, `TYPE_DEPT_AGENT_LLM_CALL`, `DeptEvent`, `LLMCallEvent`
- **Example** — `examples/emit_llm_call.py` (needs local/stage broker; residual-honest comments)
- **Tests** — `test_metering.py` mock HTTP publish path
- **User-Agent** — `iomesh-client-sdk-python/0.7.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Public lexicon **heartbeat / pulse** only · dual_write **OFF** by default elsewhere · Kafka Produce subset only
- Metering is edge publish of org-tool events — not product metering GA or hosted billing invent

## [0.6.0] — 2026-08-11

Operator diagnostics residual polish — KV + message/consumer format helpers, thin stream replay (`list_stream_messages`); wire parity with Go `FormatPutResult` / `FormatBucketInfo` / `FormatKVEntry` / `FormatKVKeys` / `FormatMsg` / `FormatMsgs` / `FormatConsumerInfo` / `ListStreamMessages` (stdlib only, pure formatters).

### Added

- **KV formatters** — `format_put_result`, `format_bucket_info` (always-emit history/max_bytes/ttl_seconds blanks), `format_kv_entry` (always-emit created_at; printable UTF-8 vs binary hex preview), `format_kv_keys` (cap 50)
- **Message / consumer formatters** — `format_msg` / `format_msgs` (nil → `(nil)`; empty batch `count=0` header OK), `format_consumer_info` (always-emit filter_subject)
- **`list_stream_messages(stream, opts?)`** — `GET /v1/streams/{name}/messages`; `ListStreamMessagesOptions` (from_seq/to_seq/limit defaults 1/0/100, limit cap 1000); `StreamMessage` with base64 payload soft-fallback
- **ConsumerInfo knobs** — `ack_floor`, `pending_count`, `filter_subject` decoded from create/ensure wire for formatters
- **Tests** — `test_kv_format.py`, `test_msg_format.py`, list_stream_messages mock HTTP
- **User-Agent** — `iomesh-client-sdk-python/0.6.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Format helpers are **operator diagnostics** only · dual_write **OFF** by default elsewhere · Kafka Produce subset only
- `list_stream_messages` is explicit discovery (non-2xx → `APIError`), not fail-open

## [0.5.0] — 2026-08-10

Context plane + operator diagnostics formatters (residual polish) — wire parity with Go `QueryContext` / `ContextSnippet` / `FormatStreams` / `FormatStreamDetail` / `ConnectionStatus` (stdlib only, fail-open).

### Added

- **Context** — `query_context(query, workspace="", limit=0, *, include_lineage=False)` → `ContextResult` (text, lineage/items, path, ok/fail-open); `POST /v1/context/query`; limit default 20; fail-open on transport / non-OK / decode
- **`context_snippet(query, workspace="")`** — always sets `include_lineage=true`; returns prompt-injection text or empty string on soft failure
- **`format_context_snippet(result)`** — text + compact `<iomesh-lineage>` block (max 12 refs; product fallback when id empty)
- **Types** — `LineageRef`, `ContextResult`
- **Stream formatters** — `format_streams(list[StreamInfo])` compact table; `format_stream_detail(StreamInfo)` multi-line (always emits max_msgs / max_age_sec / created_at blanks when unset)
- **Connection status** — `connection_status()` probes health then ready (both always run) → `ConnectionStatus` (ok flags, errs, ms latencies, result ok|err); `format_connection_status`; `aggregate_connection_result`
- **StreamInfo knobs** — optional `max_msgs`, `max_age_sec`, `created_at` decoded from wire for formatters
- **Tests** — `test_context.py`, `test_status.py`, `test_streams_format.py` (mock HTTP / pure helpers)
- **User-Agent** — `iomesh-client-sdk-python/0.5.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Context is **fail-open** Beta agent helper; formatters / connection status are **operator diagnostics**, not product GA
- dual_write **OFF** by default elsewhere · Kafka Produce subset only

## [0.4.0] — 2026-08-10

Catalog + policy evaluate helpers (residual polish) — wire parity with Go `ListCatalog` / `GetCatalogProduct` / `EvaluatePolicy` (stdlib only, fail-open).

### Added

- **Catalog** — `list_catalog(query="")` → `CatalogResult` (products + source/detail); path cascade matching Go `defaultCatalogPaths` (`/v1/catalog/data-products`, `/v1/catalog/products`, `/v17/portal/catalog/data-products`, `/v16/portal/catalog/marketing/data-products`); fail-open empty when no path succeeds
- **`get_catalog_product(id)`** — portal detail → mesh detail → list filter fallback; returns `(CatalogProduct, CatalogResult)`
- **Types** — `CatalogProduct` (portal alias normalize: mesh_layer / subject_pattern / summary / sample_subjects), `CatalogResult`
- **Format helpers** — `format_catalog`, `format_product_detail` (operator/CLI thin views)
- **Policy evaluate** — `evaluate_policy(PolicyInput)` → `PolicyDecision`; `POST /v1/policy/evaluate`; modes `off` | `advisory` | `enforce`; auto `action=tool.{tool}` when action empty; 404 → Source `unavailable`; transport/non-OK → fail-open; `should_block_tool()` only enforce + mesh deny; `summary()` operator string
- **Constants** — `POLICY_OFF`, `POLICY_ADVISORY`, `POLICY_ENFORCE`, `normalize_policy_mode`
- **Tests** — `test_catalog.py`, `test_policy.py` (mock HTTP broker)
- **User-Agent** — `iomesh-client-sdk-python/0.4.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- Catalog / policy are **Beta** discovery + tool-gate helpers; fail-open when broker missing paths
- dual_write **OFF** by default elsewhere · Kafka Produce subset only

## [0.3.0] — 2026-08-10

Kafka Produce subset, `wait_ready`, memory related + ops_digest, PyPI publish prep — wire parity with Go `kafka` / `WaitReady*` / memory related & ops_digest (stdlib only).

### Added

- **Kafka Produce subset** (`iomeshclient.kafka` / `KafkaClient`) — TCP Produce API v1, message set magic-1 encode (CRC-32C), response offset parse; `produce(topic, partition, key, value) -> offset` + `close()`; mock TCP tests
- **`wait_ready`** — poll `ready()` (+ optional `health()`) until success or timeout; returns `WaitReadyResult(elapsed_sec, attempts)`; default interval 0.5s
- **Memory related** — `retrieve_memory_related` POST `/v1` then `/v5/memory/related` cascade; `hop_distance` on `MemoryHit`; multi-hop **lite** honesty
- **Ops digest** — `export_ops_digest` POST `/v1` then `/v5/memory/ops_digest`; dataclasses for honesty / patterns / receipts / decision_stub
- **PyPI prep** — `RELEASING.md`, optional `.github/workflows/publish.yml` (release / workflow_dispatch + `secrets.PYPI_TOKEN`; no live publish without token)
- **User-Agent** — `iomesh-client-sdk-python/0.3.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- dual_write **OFF** by default elsewhere
- Kafka is **Produce subset only** for mesh integrations / pilots (not full consumer/admin client)
- multi-hop related is lite · ops GA-path framing · knowledge/analytical Beta · never invent GA

## [0.2.0] — 2026-08-10

KV helpers, memory helpers (dual_write **OFF** by default), and connectorsdk — wire parity with Go `iomeshclient` / `connectorsdk` (stdlib only).

### Added

- **KV** — `create_bucket` / `ensure_bucket` (`POST /v1/kv/{name}`; 409 → name-only `BucketInfo`), `put` (`PUT` base64 value → `PutResult`), `get` (base64 decode with graceful fallback), `delete`, `list_keys` (`?prefix=`)
- **Memory helpers** — `MemoryEnvelope`, `publish_memory_ingest` → stream `MEMORY_INGEST` subject `{tenant}.memory.ingest.turn`, `ingest_memory_turn` (`POST /v1` then `/v5/memory/ingest`), `dual_write_memory_turn(*, sync=False)` dual_write **OFF** by default (async-only); sync path fail-open (`sync_err`, no raise on sync fail), thin `retrieve_memory` (`/v1` then `/v5/memory/retrieve`)
- **connectorsdk** — `compute_hmac_sha256` / `verify_hmac` (`sha256=` default prefix), subject builders (`subject_for_department|document|embedding|warehouse|metric`), `normalize_envelope` + `publish_headers` (uuid4 correlation when `external_id` empty)
- **Types** — `BucketInfo`, `KVEntry`, `PutResult`, `CreateBucketConfig`, `MemoryEnvelope`, `DualWriteMemoryResult`, `MemoryIngestResponse`, `MemoryRetrieveRequest` / `MemoryRetrieveResponse`, …
- **Tests** — `test_kv.py`, `test_memory.py`, `test_connectorsdk.py` (mock HTTP broker)
- **User-Agent** — `iomesh-client-sdk-python/0.2.0`

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent
- dual_write **OFF** by default on `dual_write_memory_turn` (`sync=False`) — optional audit when `sync=True`


## [0.1.0] — 2026-08-10

Initial public release: official MIT Python edge client for the I/O Mesh broker HTTP plane (**Beta** / pre-1.0).

### Added

- **`connect` / `ConnectOptions`** — validate absolute `http`/`https` broker URL (reject empty, `file://`, non-http schemes, userinfo); no network I/O on connect
- **Wire headers** — `X-IOMesh-Tenant`, `X-IOMesh-Org`, `X-IOMesh-Workspace`, optional `Authorization: Bearer …`, default `User-Agent: iomesh-client-sdk-python/0.1.0`
- **`publish`** — `POST /v1/streams/{stream}/publish` with base64 payload → `PubAck` (seq / subject / partition / timestamp)
- **Streams** — `create_stream` / `ensure_stream` / `get_stream` / `list_streams` / `delete_stream`; 409 conflict → best-effort GET (nil info OK)
- **Consumers** — `create_consumer` / `ensure_consumer` / `pull_subscribe` / `consumer_fetch` / `consumer_ack` / `consumer_nack`; fetch decodes base64; `Msg.ack` / `Msg.nack`
- **Health** — `health()` (`GET /health`), `ready()` (`GET /ready` then `/readyz`)
- **stdlib HTTP** — `urllib` only; zero runtime third-party dependencies
- **Example** `examples/org_heartbeat_publish.py` — residual-honest org heartbeat publish (+ optional pull); needs local/stage broker; dual_write not claimed; Beta
- **Tests** — mocked HTTP broker via `http.server` (connect validation, headers, publish, streams 201/409, consumers fetch/ack, health/ready)
- **CI** — GitHub Actions pytest matrix on Python 3.10–3.13

### Honesty

- MIT edge client only · **not** freemium palace · **not** control-plane GA · **not** Memory GA invent · dual_write **not** claimed · KV / memory helpers / connectorsdk / Kafka Produce **not** in v0.1 · parity target is Go `iomeshclient` core HTTP plane
