"""
Generate realistic synthetic decision data for SENTINEL demo.

Three layers:
  1. Faker + domain templates — structural data, realistic distributions
  2. LLM-generated reasoning texts — stored as JSON (one-time generation)
  3. Anomaly injection — bias patterns + integrity breaks agents will find

Output: data/synthetic/decisions.json (gitignored)
Run once: python scripts/generate_synthetic_data.py
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

fake = Faker()
random.seed(42)   # Deterministic — same data every run for reproducible demos

OUTPUT_FILE = Path("data/synthetic/decisions.json")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── Configuration ──────────────────────────────────────────────────────────────
NUM_DECISIONS = 500
TENANT_ID = "bank-acme"

# Census tracts: some are majority-minority (used to detect redlining patterns)
# 30 tracts are flagged — these are the "anomalous" ones injected for bias detection
CENSUS_TRACTS = [f"CT-{i:03d}" for i in range(1, 51)]
MINORITY_MAJORITY_TRACTS = [f"CT-{i:03d}" for i in range(1, 31)]  # First 30 = anomalous

CREDIT_TIERS = ["excellent", "good", "fair", "poor"]
INCOME_BRACKETS = ["$25k-$50k", "$50k-$75k", "$75k-$100k", "$100k-$150k", "$150k+"]
AGE_GROUPS = ["18-25", "26-35", "36-50", "51-65", "65+"]
GENDERS = ["M", "F", "NB"]  # Aggregated categories — not individual identifiers


def base_approval_probability(credit_tier: str, income_bracket: str) -> float:
    """Compute realistic base approval probability from credit + income."""
    credit_scores = {"excellent": 0.92, "good": 0.78, "fair": 0.55, "poor": 0.30}
    income_boost = {"$25k-$50k": 0.0, "$50k-$75k": 0.05, "$75k-$100k": 0.10,
                    "$100k-$150k": 0.12, "$150k+": 0.15}
    return min(0.98, credit_scores[credit_tier] + income_boost.get(income_bracket, 0))


def generate_reasoning(credit_tier: str, income_bracket: str, outcome: str, dti: float) -> str:
    """Generate realistic decision reasoning text (no LLM needed for deterministic data)."""
    if outcome == "approved":
        return (
            f"Approved: Credit tier {credit_tier} meets threshold. "
            f"DTI ratio {dti:.2f} within acceptable range (<0.40). "
            f"Income bracket {income_bracket} supports requested loan amount. "
            f"No adverse credit events in 24-month review period."
        )
    else:
        reasons = []
        if dti > 0.40:
            reasons.append(f"DTI ratio {dti:.2f} exceeds threshold 0.40")
        if credit_tier == "poor":
            reasons.append("Credit tier 'poor' does not meet minimum requirements")
        if credit_tier == "fair" and dti > 0.35:
            reasons.append("Borderline credit tier with elevated DTI presents unacceptable combined risk")
        if not reasons:
            reasons.append("Combined risk profile exceeds automated approval threshold")
        return f"Denied: {'. '.join(reasons)}. Applicant may reapply after 6 months."


def generate_decisions() -> list[dict]:
    decisions = []
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for i in range(NUM_DECISIONS):
        credit_tier = random.choice(CREDIT_TIERS)
        income_bracket = random.choice(INCOME_BRACKETS)
        age_group = random.choice(AGE_GROUPS)
        gender = random.choice(GENDERS)
        tract = random.choice(CENSUS_TRACTS)
        dti = round(random.uniform(0.15, 0.55), 3)
        timestamp = base_date + timedelta(days=random.randint(0, 89), hours=random.randint(0, 23))

        base_prob = base_approval_probability(credit_tier, income_bracket)

        # ── Anomaly injection: bias against minority-majority census tracts ──
        # Applications from minority-majority tracts have artificially lower approval rates
        # This is the pattern the bias_detection_agent should find
        if tract in MINORITY_MAJORITY_TRACTS and i < 30:
            # Inject 30 cases with unexplained denial of creditworthy applicants
            if credit_tier in ("excellent", "good") and base_prob > 0.70:
                base_prob = base_prob * 0.55  # Artificial suppression — the "bug" agents detect

        outcome = "approved" if random.random() < base_prob else "denied"

        # ── Anomaly injection: integrity breaks in 10 cases ──
        # These cases have incomplete or tampered provenance chains
        integrity_broken = i >= 490  # Last 10 cases

        decisions.append({
            "case_id": f"CASE-{i+1:04d}",
            "tenant_id": TENANT_ID,
            "outcome": outcome,
            "decision_timestamp": timestamp.isoformat(),
            "model_version": "credit-scorer-v2.3",
            "reasoning_text": generate_reasoning(credit_tier, income_bracket, outcome, dti),
            "metadata": {
                "credit_score_tier": credit_tier,
                "debt_to_income_ratio": dti,
                "income_bracket": income_bracket,
                "zip_code_census_tract": tract,
                "age_group": age_group,
                "gender": gender,
                "loan_amount_range": random.choice(["$10k-$25k", "$25k-$50k", "$50k-$100k", "$100k+"]),
            },
            "_demo_meta": {
                "anomaly_type": "bias_suppression" if tract in MINORITY_MAJORITY_TRACTS and i < 30 else (
                    "integrity_break" if integrity_broken else "normal"
                ),
                "integrity_broken": integrity_broken,
            },
        })

    print(f"Generated {len(decisions)} decisions")
    print(f"  Approved: {sum(1 for d in decisions if d['outcome'] == 'approved')}")
    print(f"  Denied:   {sum(1 for d in decisions if d['outcome'] == 'denied')}")
    print(f"  Anomalous (bias): 30")
    print(f"  Integrity broken: 10")
    return decisions


if __name__ == "__main__":
    print("🛡️  SENTINEL — Synthetic Data Generator\n")
    decisions = generate_decisions()
    OUTPUT_FILE.write_text(json.dumps(decisions, indent=2, default=str))
    print(f"\n✅ Written to {OUTPUT_FILE}")
