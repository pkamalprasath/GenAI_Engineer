"""
image_captioner.py — Generate text descriptions of images using GPT-4o vision.

WHY WE DO THIS:
Images (wiring diagrams, safety labels, schematics) are invisible to text search.
By generating a rich caption, we make each image searchable with natural language.

Example:
  Input:  [PNG bytes of a wiring diagram]
  Output: "This is a three-phase electrical wiring diagram for panel A3.
           The diagram shows L1, L2, L3 power lines connected to circuit breakers
           CB-1 through CB-6 (rated at 16A each). Motor M1 is connected via
           contactor K1. A safety interlock relay R4 is visible in the bottom-left.
           Warning label: 'HIGH VOLTAGE - DO NOT OPEN WHILE ENERGISED'."

PROVIDER PRIORITY:
GPT-4o (OpenAI) is the primary vision provider. Anthropic Claude is the fallback
if OpenAI is unavailable.

COST NOTE:
GPT-4o vision costs more than GPT-4o-mini.
We call it ONCE per image during ingestion (not on every query).
Incremental indexing (in vectorstore.py) ensures each image is captioned only once.

For large deployments with many images, consider batching or rate limiting.
"""

import base64
import io
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from PIL import Image

from configs.settings import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    HAS_ANTHROPIC,
    HAS_OPENAI,
    VISION_LLM,
    MAX_IMAGE_PIXELS,
    MAX_ANSWER_TOKENS,
    PII_REDACTION_ENABLED,
)


# Prompt designed to extract maximum useful information from engineering images.
# Structured by image type so GPT-4o gives specific, searchable descriptions
# rather than generic "this is a diagram" responses.
CAPTION_PROMPT = """You are an expert engineering document analyst. Your job is to describe
this image so completely that an engineer can find it by searching for ANY element in it.

First, identify the image type, then follow the matching instructions:

── DIAGRAM / SCHEMATIC / ASSEMBLY DRAWING ──
- List EVERY labeled component by exact name (e.g., "Motor M1", "Contactor K1", "Bearing B2")
- Describe connections: what is connected to what, and how (e.g., "L1 line connects to CB-1 breaker via bus bar")
- Note flow direction arrows, rotation direction, positional labels (top/bottom/left/right)
- Copy all callout text, part numbers, tolerances, and dimension values verbatim
- Describe SPATIAL RELATIONSHIPS explicitly: use left/right/above/below/inside/outside/connected-to
  e.g., "Housing cover (left side) bolts onto bearing block (centre). Shaft (horizontal) passes
        through bearing inner race. Seal ring sits between shaft and housing cover on the left face."

── SAFETY LABEL / GHS HAZARD LABEL ──
- Name each pictogram symbol explicitly:
    exclamation mark (!) = irritant/harmful, skull and crossbones = toxic/fatal,
    flame = flammable, flame over circle = oxidiser, corrosion = corrosive,
    health hazard (silhouette with starburst) = serious health hazard,
    dead tree and fish = environmental hazard, gas cylinder = compressed gas,
    exploding bomb = explosive
- Copy the signal word verbatim (DANGER / WARNING / CAUTION)
- List all H-codes (hazard statements) and P-codes (precautionary statements) visible
- Copy product name, supplier, and emergency contact if visible

── TABLE / CHART IN IMAGE ──
- Extract every cell value as plain text (treat it as OCR)
- Preserve row and column headers exactly as written

── TECHNICAL SPECIFICATION DIAGRAM (thread, tolerance, gear) ──
- State the standard referenced (e.g., ISO, ANSI, DIN)
- List all labeled dimensions, tolerances, and parameter names with their values
- Describe the profile shape (e.g., "60-degree V-thread with flat crest and root")

── PHOTOGRAPH / REAL COMPONENT ──
- Name visible components and their spatial arrangement
- Note any labels, nameplates, or markings visible on the equipment
- Describe condition indicators if visible (e.g., wear marks, seal condition)

Also copy ALL visible text anywhere in the image verbatim.

Write 150–300 words. Be specific — avoid phrases like "the diagram shows various components".

EXAMPLE of the level of detail required for a mechanical assembly diagram:
"Bearing housing assembly cross-section. Components labeled:
 (1) Outer bearing ring — top right, bolted to housing cover with 4× M8 hex bolts
 (2) Inner bearing ring — surrounds shaft at centre
 (3) Housing cover — left face, cast iron GG25, label visible top-left
 (4) Shaft seal — between shaft and housing cover on the left face
 (5) Grease nipple — top of housing, labeled 'G1/4 DIN 71412'
 (6) Shaft — horizontal, Ø45mm, passes through both bearing rings
Spatial layout: cover (left) → seal → bearing → housing body (right).
All visible text: 'GG25', 'G1/4', 'DIN 71412', 'Ø45', 'M8×25'."

If the image is decorative (logo, page border, blank space, pure geometric icon with no text),
respond with exactly: DECORATIVE_IMAGE
"""


def caption_images(
    images: list[dict],
    document_filename: str,
    image_save_dir: Path,
) -> list[dict]:
    """
    Generate captions for a list of images from one document.

    Args:
        images           : list of {page, bytes, index, width, height}
                           from document_parser._extract_images()
        document_filename: source filename (used in caption context)
        image_save_dir   : directory to save image files for later retrieval

    Returns:
        list of {page, index, caption, image_path}
        Decorative images (GPT-4o returns "DECORATIVE_IMAGE") are excluded.
    """
    if not HAS_OPENAI and not HAS_ANTHROPIC:
        # No vision API key — skip image captioning
        return []

    image_save_dir.mkdir(parents=True, exist_ok=True)

    results = []
    decorative_count = 0
    failed_count = 0
    total = len(images)

    for img_num, img in enumerate(images, 1):
        page    = img["page"]
        idx     = img["index"]
        raw_bytes = img["bytes"]

        # Progress report every 50 images
        if img_num == 1 or img_num % 50 == 0 or img_num == total:
            logger.info(
                "Captioning progress [%s]: %d/%d images | captioned=%d decorative=%d failed=%d",
                document_filename, img_num, total, len(results), decorative_count, failed_count,
            )

        # Save image to disk (so retriever can include it in vision calls later)
        img_filename = f"page{page}_img{idx}.png"
        img_path     = image_save_dir / img_filename
        _save_image(raw_bytes, img_path)

        # Resize if too large
        resized_bytes = _resize_image(raw_bytes, max_pixels=MAX_IMAGE_PIXELS)

        logger.debug(
            "Captioning image page=%s idx=%s size=%dx%d",
            page, idx, img.get("width", 0), img.get("height", 0),
        )

        # Use GPT-4o if available, fall back to Claude (Anthropic)
        caption = _call_vision_llm(resized_bytes, document_filename)

        if caption == "DECORATIVE_IMAGE":
            logger.debug("Image page=%s idx=%s skipped as decorative", page, idx)
            decorative_count += 1
            continue

        if not caption.strip():
            logger.debug("Image page=%s idx=%s produced empty caption — skipping", page, idx)
            failed_count += 1
            continue

        logger.debug("Image page=%s idx=%s captioned (%d chars)", page, idx, len(caption))

        if PII_REDACTION_ENABLED:
            from src.guardrails.pii_detector import redact_pii
            caption = redact_pii(caption)

        results.append({
            "page":       page,
            "index":      idx,
            "caption":    caption,
            "image_path": str(img_path),
        })

    logger.info(
        "Captioned %d/%d images for %s (skipped %d decorative, %d failed)",
        len(results), len(images), document_filename, decorative_count, failed_count,
    )
    return results


def _call_vision_llm(image_bytes: bytes, doc_name: str) -> str:
    """
    Send one image to a vision LLM and get a description.
    Prefers GPT-4o (OpenAI) — falls back to Claude (Anthropic) if OpenAI unavailable.
    """
    # Detect actual format to avoid media_type mismatch errors
    if image_bytes[:3] == b"\xff\xd8\xff":
        media_type = "image/jpeg"
    elif image_bytes[:4] == b"\x89PNG":
        media_type = "image/png"
    elif image_bytes[:4] in (b"GIF8", b"GIF9"):
        media_type = "image/gif"
    else:
        media_type = "image/png"  # fallback

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt_text = f"Document: {doc_name}\n\n{CAPTION_PROMPT}"

    if HAS_OPENAI:
        return _call_openai_vision(b64_image, prompt_text, media_type)
    elif HAS_ANTHROPIC:
        return _call_claude_vision(b64_image, prompt_text, media_type)
    return ""


def _call_claude_vision(b64_image: str, prompt_text: str, media_type: str = "image/png") -> str:
    """Call Claude Haiku vision — less strict content filtering than Sonnet, better image coverage."""
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_image,
                                },
                            },
                            {"type": "text", "text": prompt_text},
                        ],
                    }
                ],
            )
            return response.content[0].text.strip()
        except Exception as e:
            err_str = str(e).lower()
            # Content filter / output blocked — do not retry
            if "400" in err_str and "output blocked" in err_str:
                logger.warning("Claude vision: content policy block — skipping image")
                return ""
            # Transient errors — retry
            if attempt < max_attempts:
                logger.warning(
                    "Claude vision attempt %d/%d failed: %s — retrying in 2s",
                    attempt, max_attempts, e,
                )
                time.sleep(2)
            else:
                logger.warning("Claude vision captioning failed after %d attempts: %s", max_attempts, e, exc_info=True)
                return ""
    return ""


def _call_openai_vision(b64_image: str, prompt_text: str, media_type: str = "image/png") -> str:
    """Call GPT-4o vision."""
    from openai import OpenAI, RateLimitError, APIConnectionError
    try:
        from openai import ContentFilterFinishReasonError as _ContentFilterError
        _content_filter_exceptions: tuple = (_ContentFilterError,)
    except ImportError:
        _content_filter_exceptions = ()

    client = OpenAI(api_key=OPENAI_API_KEY)
    data_url = f"data:{media_type};base64,{b64_image}"

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=VISION_LLM,
                max_tokens=600,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                        ],
                    }
                ],
            )
            # Check for content filter finish reason
            choice = response.choices[0]
            if choice.finish_reason == "content_filter":
                logger.warning("OpenAI vision: content policy block — skipping image")
                return ""
            return choice.message.content.strip()
        except _content_filter_exceptions:
            logger.warning("OpenAI vision: content filter raised — skipping image")
            return ""
        except (RateLimitError, APIConnectionError) as e:
            if attempt < max_attempts:
                logger.warning(
                    "OpenAI vision attempt %d/%d transient error: %s — retrying in 2s",
                    attempt, max_attempts, e,
                )
                time.sleep(2)
            else:
                logger.warning("OpenAI vision captioning failed after %d attempts: %s", max_attempts, e, exc_info=True)
                return ""
        except Exception as e:
            logger.warning("OpenAI vision captioning failed: %s", e, exc_info=True)
            return ""
    return ""


def _resize_image(image_bytes: bytes, max_pixels: int) -> bytes:
    """
    Resize image if it exceeds max_pixels total pixels.

    Smaller images = cheaper GPT-4o calls + faster processing.
    We preserve aspect ratio during resize.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Convert CMYK/P modes to RGB before any processing (save to PNG will fail otherwise)
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        w, h = img.size
        total = w * h

        if total <= max_pixels:
            # Still need to return the (possibly mode-converted) image
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        # Scale down proportionally
        scale = (max_pixels / total) ** 0.5
        new_w = int(w * scale)
        new_h = int(h * scale)
        img   = img.resize((new_w, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return image_bytes   # return original if resize fails


def _save_image(image_bytes: bytes, path: Path) -> None:
    """Save image bytes to disk as PNG, converting CMYK/P modes to RGB first."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        img.save(str(path), format="PNG")
    except Exception as e:
        logger.warning("Could not save image to %s: %s", path, e, exc_info=True)
