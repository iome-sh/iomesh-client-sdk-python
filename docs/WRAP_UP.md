# 0.x status

> **Beta / MIT edge client.** This page summarizes the public **0.1 → 0.10** surface.
> It does **not** declare **1.0**, invent product GA, or claim live PyPI.

| Framing that remains true | |
|---------------------------|---|
| License / scope | **MIT edge client** only |
| Maturity | **Beta** / pre-1.0 (`0.x` may still evolve under SemVer norms) |
| Memory | dual_write **OFF** by default · **not** Memory GA |
| Product | **not** freemium palace · **not** control-plane GA |
| Kafka | **Produce subset** only until a consumer is intentionally scoped |
| 1.0 | Only when [1.0-bar.md](1.0-bar.md) is met with evidence |

Current version: **v0.10.1** (docs). Feature surface: **v0.10.0**.

---

## What shipped (0.1 → 0.10)

Summary of the public `0.x` continuum. Details live in [CHANGELOG.md](../CHANGELOG.md) and [API.md](API.md).

| Version | Theme | Highlights |
|---------|--------|------------|
| **0.1.0** | Core HTTP plane | `connect` / publish / streams / consumers / health·ready; stdlib only; org heartbeat example |
| **0.2.0** | KV + memory + connectorsdk | KV CRUD; memory helpers with dual_write **OFF** default; HMAC / subjects / observation envelope |
| **0.3.0** | Kafka Produce + readiness + memory lite | `KafkaClient.produce`; `wait_ready`; `retrieve_memory_related`; `export_ops_digest`; PyPI workflow prep |
| **0.4.0** | Catalog + policy | Fail-open `list_catalog` / `get_catalog_product`; `evaluate_policy` (`off` / `advisory` / `enforce`) |
| **0.5.0** | Context + operator formatters | Fail-open `query_context` / `context_snippet`; stream formatters; `connection_status` |
| **0.6.0** | KV/msg formatters + replay | KV / msg / consumer format helpers; `list_stream_messages` |
| **0.7.0** | Metering (heartbeat / pulse) | `emit_dept_event` / `emit_llm_call` → stream `dept` |
| **0.8.0** | Liveview / registry | `register_processor` (409 = success); `list_live_views` |
| **0.9.0** | Async recall + env connect | `request_memory_recall` / `_full`; `connect_from_env` |
| **0.10.0** | Packaging + inventory | PEP 561 `py.typed`; [API.md](API.md); [1.0-bar.md](1.0-bar.md); `examples/pull_loop.py` |
| **0.10.1** | Docs | This page + README status; **no** new feature surface |

Parity target remains Go [`iomeshclient`](https://github.com/iome-sh/iomesh-client-sdk-go) + `kafka` + `connectorsdk`.

---

## Install paths today

**Live PyPI is not claimed.** Prefer GitHub source, editable install, or release/wheel assets when present.

### From Git (always available)

```bash
pip install -e "git+https://github.com/iome-sh/iomesh-client-sdk-python.git#egg=iomeshclient"
# pin a tag when tagged, e.g.:
# pip install "git+https://github.com/iome-sh/iomesh-client-sdk-python.git@v0.10.0#egg=iomeshclient"
```

### Clone + editable

```bash
git clone https://github.com/iome-sh/iomesh-client-sdk-python.git
cd iomesh-client-sdk-python
pip install -e .
# dev: pip install -e ".[dev]"
```

### GitHub Release assets / wheel URL

When a GitHub Release is cut for a tag, download the sdist or wheel from the release page and install locally:

```bash
# example shape (replace version / asset name from the actual Release):
pip install https://github.com/iome-sh/iomesh-client-sdk-python/releases/download/v0.10.0/iomeshclient-0.10.0-py3-none-any.whl
# or after download:
# pip install ./iomeshclient-0.10.0-py3-none-any.whl
```

Build locally without publishing:

```bash
python3 -m pip install -U build
python3 -m build
pip install dist/iomeshclient-*.whl
```

See [RELEASING.md](../RELEASING.md) for tag + optional PyPI upload when `PYPI_TOKEN` is available.

---

## Known limitations

| Item | Notes |
|------|--------|
| **Live PyPI** | Package/version ready; a live upload needs `secrets.PYPI_TOKEN` (or Trusted Publisher). Do not invent a published package. |
| **Kafka consumer** | Produce subset ships; full consumer/admin is not in scope yet. |
| **HTTP `/nack`** | Client helper / Go parity; serving broker registers ack, not nack. |
| **Memory sidecar vs broker** | Sync ingest/retrieve/related/ops_digest are operator-local sidecar routes. A broker `status=accepted` + `note` is not a palace write. Not Memory GA. |
| **Data-products vs integrations** | `list_catalog` is data-products. Knowledge Beta. Listing ≠ Connected. No OAuth/webhook wrap. |
| **1.0** | Only when [1.0-bar.md](1.0-bar.md) is met with evidence. **0.10 is not 1.0.** |
| Optional: strict typing CI | `py.typed` ships; full mypy/pyright remains optional. |

A GitHub Release for v0.10.x may trail this docs page if publish is deferred.

---

## Related docs

| Doc | Role |
|-----|------|
| [API.md](API.md) | Public surface inventory |
| [1.0-bar.md](1.0-bar.md) | Future 1.0 checklist (**not 1.0 yet**) |
| [CHANGELOG.md](../CHANGELOG.md) | Per-version detail |
| [RELEASING.md](../RELEASING.md) | Tag / wheel / optional PyPI |
| [README.md](../README.md) | Install, example, and non-claims |

---

*Remain on **0.x Beta** until a 1.0 ships under the checklist.*
