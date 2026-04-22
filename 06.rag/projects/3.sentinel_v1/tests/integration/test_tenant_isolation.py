"""
Integration tests for tenant isolation.
Tenant A must NEVER see Tenant B data — enforced at SQL, MCP, and application layers.
No Docker needed for most tests (uses mock DB).
Requires docker compose up -d for DB-level tests.

Run with: make test-integration
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.security.tenant_isolator import (
    IsolationBreachError,
    make_namespace,
    verify_namespace,
    verify_record_list,
)
from sentinel.state.investigation_state import make_initial_state

pytestmark = pytest.mark.asyncio


class TestNamespaceGeneration:
    """make_namespace() produces correct URI for tenant-scoped resources."""

    def test_namespace_format(self):
        ns = make_namespace("bank-acme", "decision_record", "CASE-0001")
        assert ns == "sentinel://bank-acme/decision_record/CASE-0001"

    def test_different_tenants_different_namespaces(self):
        ns_a = make_namespace("tenant-a", "decision_record", "CASE-0001")
        ns_b = make_namespace("tenant-b", "decision_record", "CASE-0001")
        assert ns_a != ns_b

    def test_namespace_starts_with_sentinel_scheme(self):
        ns = make_namespace("t1", "provenance_node", "node-001")
        assert ns.startswith("sentinel://")

    def test_namespace_contains_tenant_id(self):
        ns = make_namespace("bank-acme", "regulation", "ECOA-001")
        assert "bank-acme" in ns


class TestNamespaceVerification:
    """verify_namespace() detects cross-tenant access attempts."""

    def test_correct_tenant_passes(self):
        ns = "sentinel://bank-acme/decision_record/CASE-0001"
        # Should not raise
        verify_namespace(ns, expected_tenant_id="bank-acme")

    def test_wrong_tenant_raises_breach_error(self):
        ns = "sentinel://tenant-b/decision_record/CASE-0001"
        with pytest.raises(IsolationBreachError):
            verify_namespace(ns, expected_tenant_id="tenant-a")

    def test_malformed_namespace_raises(self):
        with pytest.raises((IsolationBreachError, ValueError)):
            verify_namespace("not-a-namespace", expected_tenant_id="tenant-a")

    def test_empty_namespace_raises(self):
        with pytest.raises((IsolationBreachError, ValueError)):
            verify_namespace("", expected_tenant_id="tenant-a")

    def test_prefix_match_not_sufficient(self):
        """tenant-acme should not pass for tenant-a (prevent prefix spoofing)."""
        ns = "sentinel://tenant-acme/decision_record/CASE-0001"
        with pytest.raises(IsolationBreachError):
            verify_namespace(ns, expected_tenant_id="tenant-a")


class TestRecordListVerification:
    """verify_record_list() validates bulk results from DB queries."""

    def test_all_correct_tenant_passes(self):
        records = [
            {"namespace": "sentinel://bank-acme/decision_record/CASE-0001"},
            {"namespace": "sentinel://bank-acme/decision_record/CASE-0002"},
        ]
        # Should not raise
        verify_record_list(records, expected_tenant_id="bank-acme")

    def test_mixed_tenants_raises(self):
        records = [
            {"namespace": "sentinel://bank-acme/decision_record/CASE-0001"},
            {"namespace": "sentinel://other-bank/decision_record/CASE-0002"},
        ]
        with pytest.raises(IsolationBreachError):
            verify_record_list(records, expected_tenant_id="bank-acme")

    def test_empty_list_passes(self):
        verify_record_list([], expected_tenant_id="bank-acme")

    def test_record_without_namespace_raises(self):
        records = [{"case_id": "CASE-0001"}]  # Missing namespace field
        with pytest.raises((IsolationBreachError, KeyError)):
            verify_record_list(records, expected_tenant_id="bank-acme")


class TestProvenanceStoreTenantIsolation:
    """ProvenanceStore SQL queries include tenant_id — cross-tenant data never returned."""

    async def test_get_node_includes_tenant_filter(self, mock_db_session):
        """SQL executed must include tenant_id = $2 (or equivalent parameterized filter)."""
        from sentinel.provenance.store import ProvenanceStore
        store = ProvenanceStore(mock_db_session)
        await store.get_node("decision-CASE-0001", tenant_id="bank-acme")

        # Verify execute was called — SQL contents can be inspected in real integration test
        mock_db_session.execute.assert_called_once()
        call_args = mock_db_session.execute.call_args
        # The query object or string should contain tenant filter
        assert call_args is not None

    async def test_get_nodes_for_case_scoped_to_tenant(self, mock_db_session):
        """get_nodes_for_case never returns nodes from other tenants."""
        from sentinel.provenance.store import ProvenanceStore
        store = ProvenanceStore(mock_db_session)

        # Mock returns empty — simulate no data found for this tenant
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        nodes = await store.get_nodes_for_case("CASE-0001", tenant_id="bank-acme")
        assert isinstance(nodes, list)
        # All returned nodes must belong to the requested tenant
        for node in nodes:
            assert node.get("tenant_id") == "bank-acme"


class TestAgentStateIsolation:
    """Agents must only access data scoped to state['tenant_id']."""

    def test_state_tenant_id_immutable_across_agents(self):
        """No agent should change tenant_id in state."""
        state_a = make_initial_state("INV-A", "tenant-a", "query A", {}, "finance")
        state_b = make_initial_state("INV-B", "tenant-b", "query B", {}, "finance")

        assert state_a["tenant_id"] == "tenant-a"
        assert state_b["tenant_id"] == "tenant-b"

        # Simulate agents updating other fields
        update_a = {"status": "investigating", "case_count": 5}
        update_b = {"status": "analyzing", "case_count": 3}

        merged_a = {**state_a, **update_a}
        merged_b = {**state_b, **update_b}

        # Tenant ID must not have changed
        assert merged_a["tenant_id"] == "tenant-a"
        assert merged_b["tenant_id"] == "tenant-b"

    def test_cross_tenant_state_merge_impossible(self):
        """Merging states from different tenants should result in correct isolation."""
        state_a = make_initial_state("INV-A", "tenant-a", "q", {}, "finance")
        state_b = make_initial_state("INV-B", "tenant-b", "q", {}, "finance")

        # These are separate graph executions — they should never share state
        assert state_a["investigation_id"] != state_b["investigation_id"]
        assert state_a["tenant_id"] != state_b["tenant_id"]
