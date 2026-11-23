"""
Isolation Forest anomaly detector for bias detection.

Isolation Forest (Liu et al., 2008) detects anomalies by measuring how
quickly a data point can be isolated from the rest of the population.
Anomalous points (unusual decision patterns) are isolated faster.

Used as Stage 2 in the hybrid bias detection pipeline:
  Statistical disparity (thresholds) → Isolation Forest (population anomalies)
  → Haiku LLM (only if anomalies found that disparity doesn't explain)

Business value: catches non-obvious bias patterns that approval rate
disparity comparisons miss — e.g., unusual DTI/income combinations that
only appear in specific census tracts.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    anomalous_case_ids: list[str]
    anomaly_scores: dict[str, float]          # case_id → score (more negative = more anomalous)
    anomaly_count: int
    total_cases: int
    contamination_used: float
    explanation: str                           # Plain text for LLM / report
    feature_columns: list[str] = field(default_factory=list)


def _build_feature_matrix(
    outcomes: list[dict],
    dimensions: list[str],
    positive_outcome_values: list[str],
) -> tuple[list[list[float]], list[str], list[str]]:
    """
    Convert outcome records to numeric feature matrix for Isolation Forest.

    Features encoded:
      - Binary outcome (1 = positive/approved, 0 = denied)
      - One-hot encoding for each categorical dimension value
      - Numeric fields passed through directly

    Returns:
      (feature_matrix, case_ids, feature_names)
    """
    # Build vocabulary for one-hot encoding
    vocabularies: dict[str, set] = {dim: set() for dim in dimensions}
    for record in outcomes:
        meta = record.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        for dim in dimensions:
            val = str(meta.get(dim, "unknown"))
            vocabularies[dim].append(val) if hasattr(vocabularies[dim], 'append') else vocabularies[dim].add(val)

    # Sort vocab for deterministic column order
    sorted_vocab: dict[str, list[str]] = {
        dim: sorted(vocabularies[dim]) for dim in dimensions
    }

    feature_names = ["outcome_binary"]
    for dim in dimensions:
        for val in sorted_vocab[dim]:
            feature_names.append(f"{dim}__{val}")

    matrix = []
    case_ids = []
    for record in outcomes:
        meta = record.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        row = [1.0 if record.get("outcome", "") in positive_outcome_values else 0.0]
        for dim in dimensions:
            val = str(meta.get(dim, "unknown"))
            for vocab_val in sorted_vocab[dim]:
                row.append(1.0 if val == vocab_val else 0.0)

        matrix.append(row)
        case_ids.append(record.get("case_id", ""))

    return matrix, case_ids, feature_names


def detect_anomalies(
    outcomes: list[dict],
    dimensions: list[str],
    positive_outcome_values: list[str],
    contamination: float = 0.05,
    n_estimators: int = 100,
    random_state: int = 42,
) -> AnomalyResult:
    """
    Run Isolation Forest on the outcome population to detect anomalous decisions.

    Anomalies here mean: decisions that are statistically unusual compared
    to the rest of the population when their demographic features are considered.
    These may indicate hidden bias not captured by simple disparity thresholds.

    Args:
        outcomes: List of decision records with outcome + metadata
        dimensions: Demographic dimensions to include as features (from domain config)
        positive_outcome_values: Which outcome values count as "positive" (e.g., ["approved"])
        contamination: Expected fraction of anomalies (0.05 = 5%)
        n_estimators: Number of trees in the forest
        random_state: Seed for reproducibility

    Returns:
        AnomalyResult with anomalous case IDs and scores
    """
    if len(outcomes) < 10:
        # Not enough data for meaningful anomaly detection
        return AnomalyResult(
            anomalous_case_ids=[],
            anomaly_scores={},
            anomaly_count=0,
            total_cases=len(outcomes),
            contamination_used=contamination,
            explanation="Insufficient data for anomaly detection (minimum 10 records required).",
            feature_columns=[],
        )

    try:
        from sklearn.ensemble import IsolationForest
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn not installed. Run: pip install scikit-learn"
        ) from exc

    matrix, case_ids, feature_names = _build_feature_matrix(
        outcomes, dimensions, positive_outcome_values
    )

    X = np.array(matrix, dtype=float)

    clf = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1,  # Use all available CPUs
    )
    clf.fit(X)

    # predict: 1 = normal, -1 = anomaly
    predictions = clf.predict(X)
    # decision_function: more negative = more anomalous
    raw_scores = clf.decision_function(X)

    anomalous_indices = [i for i, p in enumerate(predictions) if p == -1]
    anomalous_case_ids = [case_ids[i] for i in anomalous_indices]
    anomaly_scores = {
        case_ids[i]: round(float(raw_scores[i]), 4)
        for i in range(len(case_ids))
    }

    logger.info(
        "Isolation Forest: %d/%d cases flagged as anomalous (contamination=%.2f)",
        len(anomalous_case_ids), len(outcomes), contamination,
    )

    explanation = (
        f"Isolation Forest detected {len(anomalous_case_ids)} anomalous decisions "
        f"out of {len(outcomes)} total cases ({contamination*100:.0f}% contamination threshold). "
        f"Features analyzed: {', '.join(dimensions)}. "
        f"Anomalous cases may represent decisions inconsistent with the general population "
        f"pattern — requires investigator review to determine if bias-driven."
    )

    return AnomalyResult(
        anomalous_case_ids=anomalous_case_ids,
        anomaly_scores=anomaly_scores,
        anomaly_count=len(anomalous_case_ids),
        total_cases=len(outcomes),
        contamination_used=contamination,
        explanation=explanation,
        feature_columns=feature_names,
    )
