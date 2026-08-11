# Releasing `iomeshclient` to PyPI

This document describes how to cut a versioned release of the official I/O Mesh
Python client (`iomeshclient`). Publishing requires a PyPI API token held as a
repository secret — **do not commit tokens**.

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
git tag -a v0.7.0 -m "v0.7.0: metering emit_dept_event / emit_llm_call"
git push origin v0.7.0
```

Then create a GitHub Release from the tag (UI or `gh release create v0.7.0`).

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
python3 -m pip install -U iomeshclient==0.7.0
python3 -c "from iomeshclient import VERSION, DeptEvent, LLMCallEvent; print(VERSION, DeptEvent, LLMCallEvent)"
```

## Honesty

- MIT edge client only · Beta / pre-1.0
- Not freemium palace · not control-plane GA · not Memory GA invent
- Kafka is **Produce subset only** for mesh integrations / pilots
- dual_write remains **OFF** by default elsewhere
