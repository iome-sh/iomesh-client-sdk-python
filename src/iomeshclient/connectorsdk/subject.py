"""Broker subject builders for department / document / embedding / warehouse / metric."""

from __future__ import annotations


def subject_for_department(department: str, source: str) -> str:
    """e.g. dept.engineering.events.slack"""
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")
    return f"dept.{dept}.events.{src}"


def subject_for_document(department: str, source: str) -> str:
    """e.g. dept.product.events.docs.notion"""
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")
    return f"dept.{dept}.events.docs.{src}"


def subject_for_embedding(department: str, source: str) -> str:
    """e.g. dept.engineering.events.embeddings.memory"""
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")
    return f"dept.{dept}.events.embeddings.{src}"


def subject_for_warehouse(department: str, source: str) -> str:
    """e.g. dept.finance.views.warehouse.snowflake"""
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")
    return f"dept.{dept}.views.warehouse.{src}"


def subject_for_metric(department: str, source: str) -> str:
    """e.g. dept.finance.views.metrics.dbt"""
    dept = (department or "").strip()
    if not dept:
        raise ValueError("connectorsdk: department required")
    src = (source or "").strip()
    if not src:
        raise ValueError("connectorsdk: source required")
    return f"dept.{dept}.views.metrics.{src}"
