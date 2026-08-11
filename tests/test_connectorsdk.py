"""connectorsdk — HMAC, subjects, observation envelope normalize."""

from __future__ import annotations

import json

import pytest

from iomeshclient.connectorsdk import (
    DEFAULT_HMAC_PREFIX,
    ErrInvalidSignature,
    ErrMissingSecret,
    ErrMissingSignature,
    compute_hmac_sha256,
    normalize_envelope,
    publish_headers,
    subject_for_department,
    subject_for_document,
    subject_for_embedding,
    subject_for_metric,
    subject_for_warehouse,
    verify_hmac,
)


def test_compute_hmac_sha256_github_prefix() -> None:
    secret = "test-webhook-secret"
    body = b'{"zen":"test"}'
    got = compute_hmac_sha256(secret, body, DEFAULT_HMAC_PREFIX)
    assert got.startswith(DEFAULT_HMAC_PREFIX)
    assert len(got) == len(DEFAULT_HMAC_PREFIX) + 64
    assert compute_hmac_sha256(secret, body, DEFAULT_HMAC_PREFIX) == got


def test_compute_hmac_sha256_no_prefix() -> None:
    got = compute_hmac_sha256("s", b"body", "")
    assert len(got) == 64
    assert not got.startswith("sha256=")


def test_verify_hmac_valid() -> None:
    secret = "test-webhook-secret"
    body = '{"action":"opened","number":42}'
    sig = compute_hmac_sha256(secret, body, DEFAULT_HMAC_PREFIX)
    verify_hmac(secret, body, sig)  # no raise


def test_verify_hmac_custom_prefix() -> None:
    secret = "test-webhook-secret"
    body = '{"action":"opened","number":42}'
    sig = compute_hmac_sha256(secret, body, "v1=")
    verify_hmac(secret, body, sig, prefix="v1=")


def test_verify_hmac_errors() -> None:
    secret = "test-webhook-secret"
    body = '{"action":"opened"}'
    sig = compute_hmac_sha256(secret, body, DEFAULT_HMAC_PREFIX)
    with pytest.raises(ErrMissingSecret):
        verify_hmac("", body, sig)
    with pytest.raises(ErrMissingSignature):
        verify_hmac(secret, body, "")
    with pytest.raises(ErrInvalidSignature):
        verify_hmac(secret, body, DEFAULT_HMAC_PREFIX + "deadbeef")
    with pytest.raises(ErrInvalidSignature):
        verify_hmac(secret, '{"action":"closed"}', sig)


def test_subject_for_department() -> None:
    assert subject_for_department("engineering", "slack") == "dept.engineering.events.slack"
    assert subject_for_department("  support ", " zendesk ") == "dept.support.events.zendesk"
    with pytest.raises(ValueError, match="department required"):
        subject_for_department("", "slack")
    with pytest.raises(ValueError, match="source required"):
        subject_for_department("engineering", "")


def test_subject_for_document() -> None:
    assert (
        subject_for_document("product", "notion") == "dept.product.events.docs.notion"
    )
    assert (
        subject_for_document("engineering", "confluence")
        == "dept.engineering.events.docs.confluence"
    )


def test_subject_for_embedding() -> None:
    assert (
        subject_for_embedding("engineering", "memory")
        == "dept.engineering.events.embeddings.memory"
    )


def test_subject_for_warehouse() -> None:
    assert (
        subject_for_warehouse("finance", "snowflake")
        == "dept.finance.views.warehouse.snowflake"
    )


def test_subject_for_metric() -> None:
    assert subject_for_metric("finance", "dbt") == "dept.finance.views.metrics.dbt"


def test_normalize_envelope_with_external_id() -> None:
    raw = normalize_envelope(
        "slack",
        "engineering",
        "slack",
        external_id="Ev001",
        event_type="message",
        event={"type": "message", "text": "hello"},
    )
    env = json.loads(raw.decode("utf-8"))
    assert env["type"] == "observation"
    assert env["agent_id"] == "connector:slack"
    assert env["correlation_id"] == "Ev001"
    assert env["v"] == 1
    assert env["metadata"]["data_product_id"] == "dept.engineering.events.slack"
    assert env["metadata"]["schema_version"] == "1.0.0"
    inner = env["payload"]
    assert inner["connector_id"] == "slack"
    assert inner["department"] == "engineering"
    assert inner["external_id"] == "Ev001"
    assert inner["event_type"] == "message"
    assert inner["raw"]["text"] == "hello"


def test_normalize_envelope_generates_external_id() -> None:
    raw = normalize_envelope(
        "github",
        "ops",
        "github",
        external_id="",
        event_type="push",
        event={"ref": "refs/heads/main"},
    )
    env = json.loads(raw.decode("utf-8"))
    assert env["correlation_id"]
    assert env["payload"]["external_id"] == env["correlation_id"]
    # uuid4 form
    assert len(env["correlation_id"]) >= 32


def test_normalize_envelope_validation() -> None:
    with pytest.raises(ValueError, match="connector id required"):
        normalize_envelope("", "engineering", "slack")
    with pytest.raises(ValueError, match="department required"):
        normalize_envelope("slack", "", "slack")
    with pytest.raises(ValueError, match="source required"):
        normalize_envelope("slack", "engineering", "")


def test_publish_headers() -> None:
    h = publish_headers("github", "ops", "delivery-002", "github")
    assert h == {
        "connector_id": "github",
        "department": "ops",
        "external_id": "delivery-002",
        "source": "github",
    }
    h2 = publish_headers(" slack ", " engineering ", " Ev003 ", " slack ")
    assert h2["connector_id"] == "slack"
    assert h2["department"] == "engineering"
    assert h2["external_id"] == "Ev003"
    assert h2["source"] == "slack"
