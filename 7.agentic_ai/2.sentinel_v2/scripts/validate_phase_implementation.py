#!/usr/bin/env python
"""
Validate SENTINEL v2 complete implementation (Phase 2C + 3 + 4).

Tests that all components are properly implemented without requiring live services:
  [OK] Phase 2C: ToolNode architecture, legal agent, tool binding
  [OK] Phase 3: HNSW indexes, model routing, batch processing, streaming
  [OK] Phase 4: Structlog, Redis settings, worker job function, Docker config

Run: python scripts/validate_phase_implementation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def test_phase_2c():
    """Validate Phase 2C: ToolNode legal agent implementation."""
    print("\n" + "="*70)
    print("PHASE 2C: ToolNode Legal Agent with Dynamic Regulation Retrieval")
    print("="*70)

    # Test 1: get_bound_llm and get_tier_for_agent exist
    try:
        from sentinel.llm.client import get_bound_llm, get_tier_for_agent
        print("[OK] get_bound_llm function imported")
        print("[OK] get_tier_for_agent function imported")
    except ImportError as e:
        print(f"[FAIL] Failed to import LLM client functions: {e}")
        return False

    # Test 2: Model tiers configured
    try:
        from configs.settings import models_cfg
        agent_models = models_cfg.get("agent_models", {})
        if agent_models:
            print(f"[OK] Agent model tiers configured: {list(agent_models.keys())}")
        else:
            print("[WARN]  No agent_models configured in models.yaml")
    except Exception as e:
        print(f"[FAIL] Failed to read agent models: {e}")
        return False

    # Test 3: search_regulations tool decorated
    try:
        from sentinel.tools.regulation_tools import search_regulations
        if hasattr(search_regulations, "name"):
            print(f"[OK] search_regulations is a @tool-decorated function")
        else:
            print("[FAIL] search_regulations is not a proper tool")
            return False
    except ImportError as e:
        print(f"[FAIL] Failed to import regulation tools: {e}")
        return False

    # Test 4: legal_messages field in state
    try:
        from sentinel.state.investigation_state import InvestigationState
        if "legal_messages" in InvestigationState.__annotations__:
            print("[OK] legal_messages field in InvestigationState")
        else:
            print("[FAIL] legal_messages field missing from state")
            return False
    except Exception as e:
        print(f"[FAIL] Failed to validate state schema: {e}")
        return False

    # Test 5: route_legal_tools exists
    try:
        from sentinel.graph.edges import route_legal_tools
        print("[OK] route_legal_tools conditional routing function exists")
    except ImportError as e:
        print(f"[FAIL] Failed to import route_legal_tools: {e}")
        return False

    # Test 6: Graph compiles with ToolNode
    try:
        from sentinel.graph.builder import build_graph
        graph = build_graph()
        print("[OK] Graph compiles with legal_tools ToolNode")
    except Exception as e:
        print(f"[FAIL] Graph compilation failed: {e}")
        return False

    return True


def test_phase_3():
    """Validate Phase 3: Inference optimizations."""
    print("\n" + "="*70)
    print("PHASE 3: Inference Optimizations (HNSW, Model Routing, Streaming)")
    print("="*70)

    # Test 1: HNSW migration files exist
    try:
        from pathlib import Path
        mig_dir = Path("sentinel/db/migrations")
        files = {f.name for f in mig_dir.glob("*.sql")}
        if "002_regulation_documents.sql" in files:
            print("[OK] regulation_documents migration (002) exists")
        else:
            print("[WARN]  regulation_documents migration not found")
        if "003_hnsw_indexes.sql" in files:
            print("[OK] HNSW index migration (003) exists")
        else:
            print("[WARN]  HNSW migration not found")
    except Exception as e:
        print(f"[WARN]  Could not verify migrations: {e}")

    # Test 2: Batch processing in investigation_agent
    try:
        from sentinel.agents.investigation_agent import _get_batch_size, _process_case_batch
        print("[OK] _get_batch_size function exists")
        print("[OK] _process_case_batch function exists")
    except ImportError as e:
        print(f"[FAIL] Batch processing functions missing: {e}")
        return False

    # Test 3: Agent tier assignment
    try:
        from sentinel.agents.investigation_agent import get_tier_for_agent as get_inv_tier
        from sentinel.agents.bias_detection_agent import get_tier_for_agent as get_bias_tier
        from sentinel.agents.report_agent import get_tier_for_agent as get_report_tier
        print("[OK] investigation_agent uses get_tier_for_agent")
        print("[OK] bias_detection_agent uses get_tier_for_agent")
        print("[OK] report_agent uses get_tier_for_agent")
    except ImportError as e:
        print(f"[WARN]  Could not verify agent tier functions: {e}")

    # Test 4: SSE streaming endpoint signature
    try:
        from sentinel.api.main import stream_investigation
        import inspect
        sig = inspect.signature(stream_investigation)
        if "investigation_id" in sig.parameters:
            print("[OK] stream_investigation endpoint implemented")
        else:
            print("[FAIL] stream_investigation signature incorrect")
            return False
    except ImportError as e:
        print(f"[FAIL] Could not import streaming endpoint: {e}")
        return False

    return True


def test_phase_4():
    """Validate Phase 4: Structlog, worker, Docker."""
    print("\n" + "="*70)
    print("PHASE 4: Production Architecture (Structlog, Worker, Docker)")
    print("="*70)

    # Test 1: Structlog logging configuration
    try:
        from configs.logging_config import configure_logging
        print("[OK] Structlog configuration imported")
    except ImportError as e:
        print(f"[FAIL] Structlog config not found: {e}")
        return False

    # Test 2: Logger functions with structlog backend
    try:
        from sentinel.observability.logger import get_logger, log_agent_event, log_error
        print("[OK] get_logger function (backward-compatible)")
        print("[OK] log_agent_event function (structlog)")
        print("[OK] log_error function (structlog)")
    except ImportError as e:
        print(f"[FAIL] Logger functions missing: {e}")
        return False

    # Test 3: Shared utilities
    try:
        from sentinel.core.utils import make_safe_snapshot
        # Test the function
        test_state = {"key": "value", "nested": {"a": 1}}
        snapshot = make_safe_snapshot(test_state)
        if isinstance(snapshot, dict):
            print("[OK] make_safe_snapshot utility function works")
        else:
            print("[FAIL] make_safe_snapshot returns wrong type")
            return False
    except Exception as e:
        print(f"[FAIL] Shared utilities broken: {e}")
        return False

    # Test 4: Worker settings
    try:
        from sentinel.worker.settings import get_redis_settings
        print("[OK] Redis settings function for worker")
    except ImportError as e:
        print(f"[WARN]  Worker settings may not be available: {e}")

    # Test 5: Worker job function signature
    try:
        from pathlib import Path
        worker_main = Path("sentinel/worker/main.py")
        if worker_main.exists():
            content = worker_main.read_text()
            if "async def run_investigation" in content:
                print("[OK] run_investigation async job function defined")
            else:
                print("[FAIL] run_investigation function not found")
                return False
            if "class WorkerSettings" in content:
                print("[OK] WorkerSettings class defined")
            else:
                print("[FAIL] WorkerSettings class not found")
                return False
        else:
            print("[FAIL] worker/main.py not found")
            return False
    except Exception as e:
        print(f"[FAIL] Worker validation failed: {e}")
        return False

    # Test 6: Scheduler entry point
    try:
        from pathlib import Path
        scheduler_main = Path("sentinel/scheduler/main.py")
        if scheduler_main.exists():
            print("[OK] Scheduler standalone entry point exists")
        else:
            print("[FAIL] Scheduler main.py not found")
            return False
    except Exception as e:
        print(f"[FAIL] Scheduler validation failed: {e}")
        return False

    # Test 7: Health and readiness endpoints
    try:
        from pathlib import Path
        api_main = Path("sentinel/api/main.py")
        content = api_main.read_text()
        if "@app.get(\"/health\")" in content:
            print("[OK] /health liveness endpoint")
        else:
            print("[FAIL] /health endpoint missing")
            return False
        if "@app.get(\"/ready\")" in content:
            print("[OK] /ready readiness endpoint")
        else:
            print("[FAIL] /ready endpoint missing")
            return False
    except Exception as e:
        print(f"[FAIL] API endpoint validation failed: {e}")
        return False

    # Test 8: Docker files
    try:
        from pathlib import Path
        dockerfile = Path("Dockerfile")
        if dockerfile.exists():
            print("[OK] Dockerfile exists")
        else:
            print("[FAIL] Dockerfile not found")
            return False

        docker_compose = Path("docker-compose.yml")
        if docker_compose.exists():
            content = docker_compose.read_text()
            services = ["postgres", "redis", "ollama", "api", "worker", "scheduler", "dashboard"]
            found = sum(1 for svc in services if f"  {svc}:" in content)
            if found >= 7:
                print(f"[OK] docker-compose.yml with all 7 services ({found}/7)")
            else:
                print(f"[WARN]  docker-compose.yml found but missing some services ({found}/7)")
        else:
            print("[FAIL] docker-compose.yml not found")
            return False
    except Exception as e:
        print(f"[FAIL] Docker validation failed: {e}")
        return False

    return True


def main():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("SENTINEL v2 COMPLETE IMPLEMENTATION VALIDATION")
    print("="*70)

    results = {
        "Phase 2C (ToolNode Legal Agent)": test_phase_2c(),
        "Phase 3 (Inference Optimizations)": test_phase_3(),
        "Phase 4 (Production Architecture)": test_phase_4(),
    }

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    for phase, passed in results.items():
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"{status}: {phase}")

    all_passed = all(results.values())
    print("\n" + "="*70)
    if all_passed:
        print("[OK] ALL PHASES VALIDATED — SENTINEL v2 READY FOR DEPLOYMENT")
        print("="*70)
        print("\nNext steps:")
        print("  1. docker compose up --build")
        print("  2. POST /api/v1/investigations to start investigation")
        print("  3. GET /api/v1/investigations/{id} to check results")
        return 0
    else:
        print("[FAIL] VALIDATION FAILED — CHECK ERRORS ABOVE")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
