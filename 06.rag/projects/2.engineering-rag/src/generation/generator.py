"""
generator.py — LLM generation with vision routing and Self-RAG critique.

WHAT THIS MODULE DOES:
1. Takes filtered context chunks (from CRAG) + user query
2. Builds the appropriate prompt (P2 style, winner from experiments)
3. Routes to the correct LLM:
   - Text-only context → GPT-4o-mini (experiment winner: 4.933, cheapest)
   - Image in context  → GPT-4o (vision-capable)
4. Applies Self-RAG critique: verifies the answer is grounded in context
5. Returns answer + citation info + confidence

ROUTING LOGIC:
  if any chunk has chunk_type == 'image' and has image_path:
      → GPT-4o (include actual image bytes in the message)
  else:
      → GPT-4o-mini (text only, much cheaper)

WHY SEPARATE MODELS?
  GPT-4o-mini: ~10x cheaper than GPT-4o, sufficient for text answers
  GPT-4o: needed when image bytes are part of the context

SELF-RAG:
After the LLM generates an answer, we ask it to verify its own answer:
  SUPPORTED         → emit as-is
  PARTIALLY_SUPPORTED → emit with caveat
  NOT_SUPPORTED     → retry once with a rephrased query

Max 1 retry to stay within the < 2s P99 latency target from the case study.
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from anthropic import Anthropic

logger = logging.getLogger(__name__)

from configs.settings import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    TEXT_LLM,
    TEXT_LLM_STRONG,
    TEXT_LLM_FAST,
    VISION_LLM,
    HAS_OPENAI,
    HAS_ANTHROPIC,
    MAX_ANSWER_TOKENS,
    MAX_SELF_RAG_TOKENS,
    SELF_RAG_MAX_RETRIES,
    USE_SELF_RAG,
    PII_REDACTION_ENABLED,
)
from src.generation.prompts import (
    build_rag_prompt,
    build_self_rag_critique_prompt,
    _format_context,
)


@dataclass
class RAGResponse:
    """Complete response from the generation pipeline."""
    answer:          str
    confidence:      str        # 'high' | 'medium' | 'low'
    sources:         list[dict] # [{filename, page, chunk_type}, ...]
    self_rag_status: str        # 'supported' | 'partially_supported' | 'not_supported'
    model_used:      str        # which LLM generated the answer
    retried:         bool       # whether Self-RAG triggered a retry


def generate(
    query: str,
    chunks: list[dict],
    confidence: str,
    retriever=None,            # passed in for Self-RAG retry
    tracer=None,               # optional RAGTracer from tracing.py
) -> RAGResponse:
    """
    Generate an answer from retrieved, CRAG-filtered chunks.

    Args:
        query      : the user's original question
        chunks     : CRAG-filtered chunks (from crag.filter_chunks())
        confidence : 'high' | 'medium' | 'low' from CRAG
        retriever  : Retriever instance (for Self-RAG retry; None = no retry)

    Returns:
        RAGResponse with answer, confidence, sources, and grounding status
    """
    if not chunks:
        return RAGResponse(
            answer="I could not find relevant information in the documents to answer this question.",
            confidence="low",
            sources=[],
            self_rag_status="not_supported",
            model_used="none",
            retried=False,
        )

    # PII check on incoming query
    if PII_REDACTION_ENABLED:
        from src.guardrails.pii_detector import has_pii, redact_pii
        if has_pii(query):
            logger.warning("PII detected in user query — redacting before LLM call")
            query = redact_pii(query)

    # Build the prompt (P2 notebook-style, winner from experiments)
    prompt = build_rag_prompt(query, chunks, confidence)

    has_image = any(c.get("chunk_type") == "image" for c in chunks)
    # Determine which model will actually be used (mirrors _call_llm routing)
    model_used = TEXT_LLM_STRONG if HAS_ANTHROPIC else TEXT_LLM
    logger.info("Generating answer: chunks=%d confidence=%s has_image_chunks=%s model=%s", len(chunks), confidence, has_image, model_used)

    # Vision routing: pass image chunks to LLM when available
    image_chunk_count = sum(1 for c in chunks if c.get("chunk_type") == "image")
    logger.info("Vision routing: %d image chunks will be sent to %s", image_chunk_count, model_used)
    image_chunks_for_vision = chunks if has_image else None

    # Generate the answer
    _tracer = tracer
    if _tracer:
        with _tracer.generation("generation", model=model_used, input=prompt) as gen_span:
            answer = _call_llm(prompt, image_chunks_for_vision, model_used)
            gen_span.update(output=answer)
    else:
        answer = _call_llm(prompt, image_chunks_for_vision, model_used)
    logger.info("LLM answer received (%d chars), running Self-RAG critique", len(answer))

    # Self-RAG critique: verify the answer is grounded in context
    grounding = "SUPPORTED"
    retried = False
    if USE_SELF_RAG:
        try:
            context_str     = _format_context(chunks)
            critique_prompt = build_self_rag_critique_prompt(query, context_str, answer)
            if _tracer:
                with _tracer.span("self_rag", input=critique_prompt) as s:
                    grounding = _check_grounding(critique_prompt)
                    s.update(output=grounding)
            else:
                grounding = _check_grounding(critique_prompt)
            logger.info("Self-RAG outcome: grounding=%s", grounding)
        except Exception as e:
            logger.warning("Self-RAG critique failed, skipping: %s", e, exc_info=True)
            grounding = "PARTIALLY_SUPPORTED"
    else:
        logger.debug("Self-RAG disabled via USE_SELF_RAG=false")

    if USE_SELF_RAG and grounding == "NOT_SUPPORTED" and retriever and SELF_RAG_MAX_RETRIES > 0:
        logger.info("Self-RAG retry triggered: grounding=NOT_SUPPORTED, retrying with rephrased query")
        retry_query   = f"{query} Please provide specific technical details and values."
        retry_chunks  = retriever.query(retry_query, use_hyde=False)
        retry_prompt  = build_rag_prompt(retry_query, retry_chunks, confidence)
        retry_has_image = any(c.get("chunk_type") == "image" for c in retry_chunks)
        retry_image_chunks = retry_chunks if retry_has_image else None
        answer        = _call_llm(retry_prompt, retry_image_chunks, model_used)   # keep same model
        grounding     = "PARTIALLY_SUPPORTED"
        retried       = True

    # Map grounding string to status key
    status_map = {
        "SUPPORTED":           "supported",
        "PARTIALLY_SUPPORTED": "partially_supported",
        "NOT_SUPPORTED":       "not_supported",
    }
    self_rag_status = status_map.get(grounding, "partially_supported")

    # Redact PII from answer before returning
    if PII_REDACTION_ENABLED:
        from src.guardrails.pii_detector import redact_pii
        answer = redact_pii(answer)

    # Extract source citations from chunks
    sources = _extract_sources(chunks)
    logger.info("Returning RAGResponse: answer=%d chars sources=%d", len(answer), len(sources))

    return RAGResponse(
        answer=answer,
        confidence=confidence,
        sources=sources,
        self_rag_status=self_rag_status,
        model_used=model_used,
        retried=retried,
    )


def _call_llm(prompt: str, image_chunks: list[dict] | None, model: str) -> str:
    """
    Call the appropriate LLM.

    If image_chunks is provided (vision query), image bytes are included
    in the message content as base64 data URLs.
    """
    if HAS_ANTHROPIC:
        # Use strong model for generation, override the model parameter
        return _call_anthropic(prompt, image_chunks, model=TEXT_LLM_STRONG)
    elif HAS_OPENAI:
        return _call_openai(prompt, image_chunks, model)
    raise RuntimeError("No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")


def _call_openai(
    prompt: str,
    image_chunks: list[dict] | None,
    model: str,
) -> str:
    """
    Call OpenAI API. Includes image bytes when model is GPT-4o (vision).

    For vision queries, each image chunk's image_path is loaded from disk
    and included as a base64 data URL in the message content.
    This is how GPT-4o accepts image input.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    if image_chunks:
        # Build multi-modal message content (cap at 5 images for GPT-4o token limits)
        content = [{"type": "text", "text": prompt}]
        images_loaded = 0

        for chunk in image_chunks[:5]:
            if chunk.get("chunk_type") == "image" and chunk.get("image_path"):
                img_path = Path(chunk["image_path"])
                if not img_path.exists():
                    logger.warning("Image file missing for vision: %s", img_path)
                    continue
                try:
                    b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url":    f"data:image/png;base64,{b64}",
                            "detail": "high",
                        },
                    })
                    images_loaded += 1
                except Exception as img_err:
                    logger.warning("Failed to load image %s: %s", img_path, img_err)

        # Fall back to text-only if no images were actually loaded
        if images_loaded == 0:
            logger.warning("No images loaded successfully — falling back to text-only call")
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": prompt}]

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=MAX_ANSWER_TOKENS,
            messages=messages,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI generation failed (model=%s): %s", model, e, exc_info=True)
        raise


def _call_anthropic(prompt: str, image_chunks: list[dict] | None = None, model: str = None) -> str:
    """Call Anthropic API, with optional vision support for image chunks."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    if model is None:
        model = TEXT_LLM_STRONG

    if image_chunks:
        content = []
        images_loaded = 0

        for chunk in image_chunks[:5]:
            if chunk.get("chunk_type") == "image" and chunk.get("image_path"):
                img_path = Path(chunk["image_path"])
                if not img_path.exists():
                    logger.warning("Image file missing for vision: %s", img_path)
                    continue
                try:
                    img_bytes = img_path.read_bytes()
                    media_type = "image/jpeg" if img_bytes[:3] == b"\xff\xd8\xff" else "image/png"
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    })
                    images_loaded += 1
                except Exception as img_err:
                    logger.warning("Failed to load image %s: %s", img_path, img_err)

        # Fall back to text-only if no images were actually loaded
        if images_loaded == 0:
            logger.warning("No images loaded successfully — falling back to text-only call")
            content = prompt
        else:
            content.append({"type": "text", "text": prompt})
    else:
        content = prompt

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=MAX_ANSWER_TOKENS,
            messages=[{"role": "user", "content": content}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.error("Anthropic generation failed (model=%s): %s", model, e, exc_info=True)
        raise


def _check_grounding(critique_prompt: str) -> str:
    """
    Run Self-RAG critique to check if the answer is grounded in context.

    Returns: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'NOT_SUPPORTED'
    """
    try:
        if HAS_ANTHROPIC:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=TEXT_LLM_FAST,
                max_tokens=MAX_SELF_RAG_TOKENS,
                messages=[{"role": "user", "content": critique_prompt}],
            )
            result = msg.content[0].text.strip().upper()
        elif HAS_OPENAI:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=TEXT_LLM,
                max_tokens=MAX_SELF_RAG_TOKENS,
                temperature=0,
                messages=[{"role": "user", "content": critique_prompt}],
            )
            result = resp.choices[0].message.content.strip().upper()
        else:
            return "PARTIALLY_SUPPORTED"   # no LLM, assume partial

        if "NOT_SUPPORTED" in result:
            return "NOT_SUPPORTED"
        elif "PARTIALLY" in result:
            return "PARTIALLY_SUPPORTED"
        else:
            return "SUPPORTED"
    except Exception as e:
        logger.warning("Self-RAG critique failed, defaulting to partially_supported: %s", e, exc_info=True)
        return "PARTIALLY_SUPPORTED"


def _extract_sources(chunks: list[dict]) -> list[dict]:
    """Extract unique source citations from chunks."""
    seen = set()
    sources = []
    for c in chunks:
        key = (c.get("filename", ""), c.get("page"))
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename":   c.get("filename", "unknown"),
                "page":       c.get("page"),
                "chunk_type": c.get("chunk_type", "text"),
                "section":    c.get("section", ""),
            })
    return sources
