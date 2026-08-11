# Changelog

All notable changes to `iomesh-client-sdk-python` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
