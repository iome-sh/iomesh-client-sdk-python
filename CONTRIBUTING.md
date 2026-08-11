# Contributing

Thanks for improving the I/O Mesh Python client SDK.

**Copyright:** © 2026 IOMesh Technology Ltd.

## Ground rules

1. **Public API stability** — prefer additive changes; breaking changes require a major version and CHANGELOG entry.  
2. **Pure client only** — stdlib HTTP preferred for the core client; keep runtime dependencies empty unless there is a strong reason.  
3. **Tests required** — unit tests with mocked HTTP (`http.server` or equivalent). No live broker credentials in CI.  
4. **Security** — follow [SECURITY.md](SECURITY.md); no credentials in fixtures.  

## Public repository policy

This is a **public** OSS repository. Keep the surface free of private-process leakage:

1. **No private ledger / internal serials** in PR titles, commit messages, or CHANGELOG bullets.  
2. **No private monorepo paths** — do not reference unpublished internal trees or non-public endpoints outside the documented I/O Mesh broker surface.  
3. **Prefer public product language** — I/O Mesh broker/platform and public peers such as [iomesh-client-sdk-go](https://github.com/iome-sh/iomesh-client-sdk-go).  

## Workflow

```bash
git clone https://github.com/iome-sh/iomesh-client-sdk-python.git
cd iomesh-client-sdk-python
python -m pip install -e ".[dev]"
python -m pytest -q
```

Optional (if installed):

```bash
ruff check src tests examples
```

### Typing

The package ships a PEP 561 marker (`src/iomeshclient/py.typed`) and the wheel
includes it. Gradual typing is welcome; a full mypy/pyright CI gate is **optional**
residual toward the [1.0 bar](docs/1.0-bar.md) and is not required for ordinary PRs.

1. Open a PR against `main` from a feature branch.  
2. Ensure CI is green (pytest matrix).  
3. Keep commits focused; squash merge is preferred.  
4. Update [CHANGELOG.md](CHANGELOG.md) for user-visible changes.  

## License

By contributing, you agree that your contributions are licensed under the MIT License (see [LICENSE](LICENSE)).
