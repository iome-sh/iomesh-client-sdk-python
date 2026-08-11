# Changelog

All notable changes to `iomesh-client-sdk-python` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Kafka Produce, full multi-hop related / ops_digest, wait-ready, PyPI publish: residual **Next**

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
