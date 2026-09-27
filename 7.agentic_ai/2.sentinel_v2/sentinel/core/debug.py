"""
Debug utilities for SENTINEL agent execution.
Provides detailed logging and mock response generation for testing.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def log_agent_input(agent_name: str, inv_id: str, state_keys: list[str], values: dict) -> None:
    """Log agent inputs in structured format."""
    logger.info(
        f"[{agent_name.upper()}] INPUT: inv_id={inv_id}, keys={state_keys}",
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "input_keys": state_keys,
            "input_summary": {k: v for k, v in values.items() if k in state_keys},
        }
    )


def log_agent_output(agent_name: str, inv_id: str, output: dict) -> None:
    """Log agent outputs in structured format."""
    output_keys = list(output.keys())
    logger.info(
        f"[{agent_name.upper()}] OUTPUT: inv_id={inv_id}, keys={output_keys}",
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "output_keys": output_keys,
            "output_summary": {k: str(v)[:100] if not isinstance(v, (int, float, bool)) else v
                              for k, v in output.items()},
        }
    )


def log_agent_exception(agent_name: str, inv_id: str, exc: Exception) -> None:
    """Log agent exceptions with full context."""
    logger.error(
        f"[{agent_name.upper()}] EXCEPTION: {type(exc).__name__}: {str(exc)[:200]}",
        exc_info=True,
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:200],
        }
    )


def generate_mock_discovery_output(state: dict) -> dict:
    """DISABLED: Use real discovery agent instead.
    Generate mock discovery agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}


def generate_mock_investigation_output(state: dict) -> dict:
    """DISABLED: Use real investigation agent instead.
    Generate mock investigation agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}


def generate_mock_legal_output(state: dict) -> dict:
    """DISABLED: Use real legal agent instead.
    Generate mock legal analysis agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}


def generate_mock_bias_output(state: dict) -> dict:
    """DISABLED: Use real bias detection agent instead.
    Generate mock bias detection agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}


def generate_mock_report_output(state: dict) -> dict:
    """DISABLED: Use real report agent instead.
    Generate mock report agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}
