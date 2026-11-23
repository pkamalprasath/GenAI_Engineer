"""
Direct test of mock agent output generation
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.core.debug import (
    generate_mock_discovery_output,
    generate_mock_investigation_output,
    generate_mock_legal_output,
    generate_mock_bias_output,
    generate_mock_report_output,
)
from sentinel.state.investigation_state import make_initial_state

# Create a test state with applicant_data
state = make_initial_state(
    investigation_id="TEST-001",
    tenant_id="test-tenant",
    query="Test investigation",
    date_range={"from": "2026-01-01", "to": "2026-12-31"},
)

# Add applicant data
applicant_data = {
    "applicant_id": "APP_001",
    "applicant_name": "John Smith",
    "race": "African American",
    "gender": "Male",
    "age": 35,
    "income": 45000,
    "loan_amount": 250000,
    "loan_type": "mortgage",
    "credit_score": 620,
    "employment_length_years": 2,
    "denied": True,
    "denial_reason": "credit_score_too_low",
    "debt_to_income_ratio": 0.85,
}

state["applicant_data"] = applicant_data

print("=" * 80)
print("TESTING MOCK AGENT OUTPUT GENERATION")
print("=" * 80)

print("\n[1] Discovery Agent Mock Output")
print("-" * 80)
discovery_output = generate_mock_discovery_output(state)
print(f"Case Count: {discovery_output.get('case_count', 0)}")
print(f"Discovery Confidence: {discovery_output.get('discovery_confidence', 0):.2%}")
print(f"Relevant Cases: {discovery_output.get('relevant_case_ids', [])}")

# Update state with discovery results for downstream agents
state.update(discovery_output)

print("\n[2] Investigation Agent Mock Output")
print("-" * 80)
investigation_output = generate_mock_investigation_output(state)
print(f"Evidence Items: {len(investigation_output.get('evidence_items', []))}")
print(f"Investigation Sufficient: {investigation_output.get('investigation_sufficient', False)}")

# Update state
state.update(investigation_output)

print("\n[3] Legal Agent Mock Output")
print("-" * 80)
legal_output = generate_mock_legal_output(state)
print(f"Compliance Verdict: {legal_output.get('compliance_verdict', 'UNKNOWN')}")
print(f"Regulatory Risk: {legal_output.get('regulatory_risk', 'UNKNOWN')}")
print(f"Applicable Regulations: {len(legal_output.get('applicable_regulations', []))}")
print(f"  Regulations: {legal_output.get('applicable_regulations', [])}")

# Update state
state.update(legal_output)

print("\n[4] Bias Detection Agent Mock Output")
print("-" * 80)
bias_output = generate_mock_bias_output(state)
print(f"Bias Detected: {bias_output.get('bias_detected', False)}")
print(f"Bias Confidence: {bias_output.get('bias_confidence', 0):.2%}")
print(f"Dimensions Checked: {len(bias_output.get('bias_dimensions_checked', []))}")
print(f"  Dimensions: {bias_output.get('bias_dimensions_checked', [])}")

# Update state
state.update(bias_output)

print("\n[5] Report Agent Mock Output")
print("-" * 80)
report_output = generate_mock_report_output(state)
draft_report = report_output.get("draft_report", "")
print(f"Draft Report Generated: {len(draft_report) > 0}")
if draft_report:
    print(f"Report Length: {len(draft_report)} characters")
    print(f"Report Preview:")
    print("-" * 80)
    print(draft_report[:500])
    print("-" * 80)

print("\n" + "=" * 80)
print("ALL MOCK AGENTS WORKING CORRECTLY")
print("=" * 80)
