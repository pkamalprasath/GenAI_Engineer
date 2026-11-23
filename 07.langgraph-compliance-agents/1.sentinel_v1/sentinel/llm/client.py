"""
Unified LLM client — single abstraction over Anthropic and OpenAI.

All agents import get_llm_client() instead of instantiating AsyncAnthropic
or AsyncOpenAI directly. Provider is determined by configs/models.yaml:
  provider: anthropic  →  AsyncAnthropic
  provider: openai     →  AsyncOpenAI

Switching providers = one line in models.yaml, zero agent code changes.

Response is normalized to a common LLMResponse dataclass so agents
don't need provider-specific response parsing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from configs.settings import models_cfg, settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Provider-agnostic response — agents read .text and .usage regardless of provider."""
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str


@dataclass
class _ModelConfig:
    provider: str
    model: str
    max_tokens: int
    temperature: float


def _get_model_config(tier: str) -> _ModelConfig:
    """Load model config for a given tier (reasoning, synthesis, fallback)."""
    cfg = models_cfg.get("models", {}).get(tier, {})
    return _ModelConfig(
        provider=cfg.get("provider", "openai"),
        model=cfg.get("model", "gpt-4o-mini"),
        max_tokens=cfg.get("max_tokens", 2048),
        temperature=cfg.get("temperature", 0),
    )


async def chat(
    prompt: str,
    tier: str = "reasoning",
    system: str | None = None,
    override_provider: str | None = None,
) -> LLMResponse:
    """
    Send a chat message to the configured LLM provider for the given tier.

    Args:
        prompt: User message
        tier: Model tier from models.yaml — "reasoning", "synthesis", "fallback"
        system: Optional system prompt (soul file content)
        override_provider: Force a specific provider, ignoring models.yaml

    Returns:
        LLMResponse with normalized .text and .usage fields
    """
    cfg = _get_model_config(tier)
    provider = override_provider or cfg.provider

    if provider == "anthropic":
        return await _call_anthropic(prompt, cfg, system)
    elif provider == "openai":
        return await _call_openai(prompt, cfg, system)
    else:
        raise ValueError(
            f"Unknown provider '{provider}' for tier '{tier}'. "
            f"Valid providers: anthropic, openai"
        )


async def _call_anthropic(
    prompt: str, cfg: _ModelConfig, system: str | None
) -> LLMResponse:
    """Call Anthropic API and normalize to LLMResponse."""
    from anthropic import AsyncAnthropic

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to .env or switch provider to openai in models.yaml"
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = [{"role": "user", "content": prompt}]
    kwargs = dict(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        messages=messages,
    )
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)

    return LLMResponse(
        text=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=cfg.model,
        provider="anthropic",
    )


async def _call_openai(
    prompt: str, cfg: _ModelConfig, system: str | None
) -> LLMResponse:
    """Call OpenAI API and normalize to LLMResponse."""
    from openai import AsyncOpenAI

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to .env or switch provider to anthropic in models.yaml"
        )

    import os
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    client = AsyncOpenAI(api_key=api_key)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        messages=messages,
    )

    choice = response.choices[0]
    usage = response.usage

    return LLMResponse(
        text=choice.message.content or "",
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        model=cfg.model,
        provider="openai",
    )
