# Releasing `iomeshclient` to PyPI

This document describes how to cut a versioned release of the official I/O Mesh
Python client (`iomeshclient`). Publishing requires a PyPI API token held as a
repository secret — **do not commit tokens**.

**Continuum tip:** **v0.10.0** closed the active 0.x feature wave; **v0.10.1** is an
optional docs wrap-up patch ([docs/WRAP_UP.md](docs/WRAP_UP.md)). Tag/publish either
when ready — do not invent live PyPI or declare 1.0.

## Preconditions

- [ ] Version bumped consistently in:
  - `pyproject.toml` → `project.version`
  - `src/iomeshclient/client.py` → `VERSION`
  - `CHANGELOG.md` → dated section (move `[Unreleased]` notes)
  - `README.md` → version badges / UA string if mentioned
- [ ] `python3 -m pytest -q` green locally
- [ ] CI green on the release PR / tag commit
- [ ] GitHub Actions secret `PYPI_TOKEN` configured (Trusted Publisher or API token)

## Tag a release

```bash
# from a clean main tip after the version PR is merged
git checkout main && git pull --ff-only
git tag -a v0.10.0 -m "v0.10.0: typing marker + API inventory + 1.0 bar docs (not invent 1.0)"
git push origin v0.10.0
# optional docs patch:
# git tag -a v0.10.1 -m "v0.10.1: docs wrap-up closeout (not invent 1.0)"
# git push origin v0.10.1
```

Then create a GitHub Release from the tag (UI or `gh release create v0.10.0`).

The optional workflow [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
runs on `release: published` (and `workflow_dispatch`) and uploads sdist + wheel
when `PYPI_TOKEN` is present.

## Manual build + upload

If you prefer a local publish (or the workflow secret is not set):

```bash
python3 -m pip install -U build twine
rm -rf dist/
python3 -m build
# inspect
ls -la dist/
twine check dist/*
# upload (use a token, not a password)
TWINE_USERNAME=__token__ TWINE_PASSWORD="$PYPI_TOKEN" twine upload dist/*
```

Test index first if desired:

```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD="$TESTPYPI_TOKEN" \
  twine upload --repository testpypi dist/*
```

## Verify

```bash
# when live PyPI exists (token residual — not claimed today):
# python3 -m pip install -U iomeshclient==0.10.1
python3 -c "from iomeshclient import VERSION, MemoryRecallRequest, connect_from_env; print(VERSION, MemoryRecallRequest, connect_from_env)"
```

Until PyPI is live, install from git or a GitHub Release wheel — see [docs/WRAP_UP.md](docs/WRAP_UP.md).

## Honesty

- MIT edge client only · Beta / pre-1.0
- Not freemium palace · not control-plane GA · not Memory GA invent
- Kafka is **Produce subset only** for mesh integrations / pilots
- dual_write remains **OFF** by default elsewhere
- 0.x feature continuum closed at v0.10.0; true 1.0 only when [docs/1.0-bar.md](docs/1.0-bar.md) gates are met
