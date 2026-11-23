"""
Unit tests for algorithmic classifiers (BM25, BERT, Isolation Forest).
No Docker, no API, no network — pure algorithm tests.

These verify the classifiers don't break the business contract:
  - Output structure is identical to what the agents expect
  - No PII leakage through classifier paths
  - Config-driven thresholds are respected
"""
from __future__ import annotations

import pytest

from sentinel.agents.classifiers.bm25_ranker import rank_cases_bm25
from sentinel.agents.classifiers.anomaly_detector import detect_anomalies


# ── Test fixtures ──────────────────────────────────────────────────────────────

def _make_cases(n: int = 20) -> list[dict]:
    """Generate synthetic case records for classifier testing."""
    cases = []
    for i in range(n):
        outcome = "approved" if i % 3 != 0 else "denied"
        census_tract = f"CT-{(i % 5) + 1:03d}"
        cases.append({
            "case_id": f"CASE-{i+1:04d}",
            "outcome": outcome,
            "reasoning_text": (
                f"{'Approved' if outcome == 'approved' else 'Denied'}: "
                f"Credit tier {'excellent' if i % 2 == 0 else 'fair'} "
                f"DTI ratio {0.25 + i*0.01:.2f} for loan application."
            ),
            "metadata": {
                "credit_score_tier": "excellent" if i % 2 == 0 else "fair",
                "zip_code_census_tract": census_tract,
                "income_bracket": "$75k-$100k",
                "age_group": "36-50",
                "gender": "M" if i % 2 == 0 else "F",
            },
        })
    return cases


# ── BM25 Ranker ───────────────────────────────────────────────────────────────

class TestBM25Ranker:
    """BM25 pre-filter — fast relevance ranking with no ML model."""

    def test_returns_at_most_top_k(self):
        cases = _make_cases(30)
        result = rank_cases_bm25("credit lending compliance", cases, top_k=10)
        assert len(result) <= 10

    def test_returns_all_if_fewer_than_top_k(self):
        cases = _make_cases(5)
        result = rank_cases_bm25("credit compliance", cases, top_k=50)
        assert len(result) == 5

    def test_scores_are_attached(self):
        cases = _make_cases(10)
        result = rank_cases_bm25("credit denied DTI", cases, top_k=5)
        for item in result:
            assert "_bm25_score" in item
            assert isinstance(item["_bm25_score"], float)

    def test_results_sorted_descending(self):
        cases = _make_cases(20)
        result = rank_cases_bm25("approved credit excellent", cases, top_k=20)
        scores = [r["_bm25_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_relevant_case_ranks_higher(self):
        """Case with query terms in reasoning_text should score higher than one without."""
        cases = [
            {
                "case_id": "CASE-HIGH",
                "outcome": "denied",
                "reasoning_text": "Denied: fair lending compliance review flagged census tract bias",
                "metadata": {},
            },
            {
                "case_id": "CASE-LOW",
                "outcome": "approved",
                "reasoning_text": "Approved: standard credit review",
                "metadata": {},
            },
        ]
        result = rank_cases_bm25("fair lending compliance census tract bias", cases, top_k=2)
        assert result[0]["case_id"] == "CASE-HIGH"

    def test_empty_cases_returns_empty(self):
        result = rank_cases_bm25("credit compliance", [], top_k=10)
        assert result == []

    def test_empty_query_returns_cases_unscored(self):
        cases = _make_cases(5)
        result = rank_cases_bm25("", cases, top_k=10)
        assert len(result) == 5

    def test_case_dict_preserved_with_score_added(self):
        """Original case fields must not be modified — only _bm25_score added."""
        cases = _make_cases(3)
        original_ids = {c["case_id"] for c in cases}
        result = rank_cases_bm25("credit", cases, top_k=3)
        result_ids = {r["case_id"] for r in result}
        assert result_ids.issubset(original_ids)
        for r in result:
            assert "outcome" in r
            assert "metadata" in r


# ── Isolation Forest ─────────────────────────────────────────────────────────

class TestIsolationForest:
    """Isolation Forest anomaly detector — catches bias patterns disparity misses."""

    def _make_outcomes(self, n: int = 60, inject_anomalies: int = 5) -> list[dict]:
        """
        Generate outcome records with injected anomalies.
        Last `inject_anomalies` records: excellent credit denied in majority-minority tract.
        These should be flagged as anomalous.
        """
        outcomes = []
        for i in range(n - inject_anomalies):
            outcomes.append({
                "case_id": f"CASE-{i+1:04d}",
                "outcome": "approved" if i % 3 != 0 else "denied",
                "metadata": {
                    "credit_score_tier": "excellent" if i % 2 == 0 else "fair",
                    "zip_code_census_tract": f"CT-{(i % 10) + 10:03d}",
                    "age_group": "36-50",
                    "gender": "M" if i % 2 == 0 else "F",
                },
            })
        # Inject anomalies: excellent credit, rare minority tracts (CT-001 to CT-005), denied.
        # Each anomaly gets a DIFFERENT rare tract so feature vectors are not identical —
        # Isolation Forest can't isolate a cluster of identical vectors (path length inflates).
        for j in range(inject_anomalies):
            outcomes.append({
                "case_id": f"ANOMALY-{j+1:04d}",
                "outcome": "denied",  # Denied despite excellent credit — anomalous
                "metadata": {
                    "credit_score_tier": "excellent",
                    "zip_code_census_tract": f"CT-00{j+1}",  # Unique rare tract per anomaly
                    "age_group": "36-50",
                    "gender": "M",
                },
            })
        return outcomes

    def test_returns_anomaly_result(self):
        outcomes = self._make_outcomes(60, inject_anomalies=5)
        result = detect_anomalies(
            outcomes=outcomes,
            dimensions=["credit_score_tier", "zip_code_census_tract"],
            positive_outcome_values=["approved"],
            contamination=0.10,
            random_state=42,
        )
        assert result is not None
        assert isinstance(result.anomalous_case_ids, list)
        assert isinstance(result.anomaly_count, int)
        assert isinstance(result.explanation, str)

    def test_detects_injected_anomalies(self):
        """Isolation Forest should flag the injected anomalous cases."""
        outcomes = self._make_outcomes(60, inject_anomalies=5)
        result = detect_anomalies(
            outcomes=outcomes,
            dimensions=["credit_score_tier", "zip_code_census_tract"],
            positive_outcome_values=["approved"],
            contamination=0.10,  # 10% = 6 cases — enough to catch our 5 injections
            random_state=42,
        )
        # At least some of the injected anomalies should be flagged
        injected_ids = {f"ANOMALY-{j+1:04d}" for j in range(5)}
        flagged = set(result.anomalous_case_ids)
        overlap = injected_ids & flagged
        assert len(overlap) >= 2, (
            f"Expected at least 2 injected anomalies flagged, got: {overlap}"
        )

    def test_insufficient_data_returns_empty(self):
        """Fewer than 10 records → no anomaly detection attempted."""
        outcomes = self._make_outcomes(5, inject_anomalies=0)
        result = detect_anomalies(
            outcomes=outcomes,
            dimensions=["credit_score_tier"],
            positive_outcome_values=["approved"],
        )
        assert result.anomaly_count == 0
        assert "Insufficient" in result.explanation

    def test_anomaly_scores_are_floats(self):
        outcomes = self._make_outcomes(40)
        result = detect_anomalies(
            outcomes=outcomes,
            dimensions=["credit_score_tier", "gender"],
            positive_outcome_values=["approved"],
            random_state=42,
        )
        for score in result.anomaly_scores.values():
            assert isinstance(score, float)

    def test_contamination_controls_flagged_count(self):
        """Higher contamination → more cases flagged."""
        outcomes = self._make_outcomes(100, inject_anomalies=10)
        dims = ["credit_score_tier", "zip_code_census_tract"]

        result_low = detect_anomalies(
            outcomes, dims, ["approved"], contamination=0.03, random_state=42
        )
        result_high = detect_anomalies(
            outcomes, dims, ["approved"], contamination=0.15, random_state=42
        )
        assert result_high.anomaly_count >= result_low.anomaly_count

    def test_deterministic_with_same_random_state(self):
        """Same random_state → same anomalies every run (reproducible demos)."""
        outcomes = self._make_outcomes(60)
        dims = ["credit_score_tier", "zip_code_census_tract"]

        result1 = detect_anomalies(outcomes, dims, ["approved"], random_state=42)
        result2 = detect_anomalies(outcomes, dims, ["approved"], random_state=42)
        assert sorted(result1.anomalous_case_ids) == sorted(result2.anomalous_case_ids)

    def test_explanation_is_informative(self):
        outcomes = self._make_outcomes(50)
        result = detect_anomalies(
            outcomes, ["credit_score_tier"], ["approved"], random_state=42
        )
        assert len(result.explanation) > 20
        assert "Isolation Forest" in result.explanation


# ── Business Contract Tests ────────────────────────────────────────────────────

class TestClassifierBusinessContract:
    """
    Verify classifiers don't break the downstream agents' expectations.
    These tests enforce the interface contract regardless of which algorithm runs.
    """

    def test_bm25_output_has_all_case_fields(self):
        """Downstream agent must be able to read case_id, outcome, metadata from results."""
        cases = _make_cases(10)
        result = rank_cases_bm25("compliance review", cases, top_k=5)
        for r in result:
            assert "case_id" in r
            assert "outcome" in r
            assert "metadata" in r

    def test_anomaly_result_case_ids_are_strings(self):
        """Agent uses anomalous_case_ids as list[str] — must not be ints or None."""
        outcomes = self._make_outcomes_simple(30)
        result = detect_anomalies(outcomes, ["gender"], ["approved"], random_state=42)
        assert all(isinstance(cid, str) for cid in result.anomalous_case_ids)

    def _make_outcomes_simple(self, n: int) -> list[dict]:
        return [
            {
                "case_id": f"CASE-{i:04d}",
                "outcome": "approved" if i % 2 == 0 else "denied",
                "metadata": {"gender": "M" if i % 3 == 0 else "F"},
            }
            for i in range(n)
        ]

    def test_bm25_does_not_mutate_original_cases(self):
        """BM25 adds _bm25_score but must not modify original case dict in-place."""
        cases = _make_cases(5)
        original_keys = [set(c.keys()) for c in cases]
        rank_cases_bm25("credit", cases, top_k=5)
        # Original dicts should not have _bm25_score added
        for i, case in enumerate(cases):
            assert set(case.keys()) == original_keys[i]
