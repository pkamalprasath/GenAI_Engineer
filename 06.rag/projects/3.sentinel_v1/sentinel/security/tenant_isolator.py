"""
Tenant isolation enforcer — from Ranjan Kumar's multi-tenant MCP pattern.

Tenant ID is injected from authenticated session credentials.
It is NEVER accepted from request parameters or user-supplied data.

All data access is namespaced: sentinel://{tenant_id}/resource/id
Cross-tenant access is detected and raises IsolationBreachError.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IsolationBreachError(Exception):
    """Raised when a cross-tenant data access is detected."""


def make_namespace(tenant_id: str, resource_type: str, resource_id: str) -> str:
    """Build the canonical tenant-scoped URI for any resource."""
    return f"sentinel://{tenant_id}/{resource_type}/{resource_id}"


def verify_namespace(namespace: str, expected_tenant_id: str) -> None:
    """
    Verify that a namespace URI belongs to the expected tenant.
    Raises IsolationBreachError if it doesn't — caller should treat as fatal.
    """
    expected_prefix = f"sentinel://{expected_tenant_id}/"
    if not namespace.startswith(expected_prefix):
        logger.error(
            '{"event":"isolation_breach","expected_tenant":"%s","namespace":"%s"}',
            expected_tenant_id, namespace[:50],
        )
        raise IsolationBreachError(
            f"Namespace {namespace!r} does not belong to tenant {expected_tenant_id!r}"
        )


def verify_record_list(records: list[dict], tenant_id: str, tenant_id_field: str = "tenant_id") -> None:
    """
    Verify all records in a list belong to the expected tenant.
    Used after any bulk DB query to catch misconfigured queries.
    """
    for record in records:
        record_tenant = record.get(tenant_id_field)
        if record_tenant and record_tenant != tenant_id:
            logger.error(
                '{"event":"isolation_breach","expected":"%s","found":"%s"}',
                tenant_id, record_tenant,
            )
            raise IsolationBreachError(
                f"Record tenant {record_tenant!r} does not match expected {tenant_id!r}"
            )


def tenant_scoped_query_params(tenant_id: str, extra_params: dict) -> dict:
    """
    Add tenant_id to query parameters.
    Convenience function to ensure tenant_id is always included in DB queries.
    """
    return {"tenant_id": tenant_id, **extra_params}
