"""
prompts.py — All prompt templates for the Engineering RAG system.

WHY THIS FILE EXISTS:
Prompt templates are the core of what the LLM receives. Keeping them
in one place makes it easy to:
- Understand what the LLM is being told
- Test different prompts without changing business logic
- Extend with new templates as needed

PROMPT CHOICE:
From your experiments, P2 (Notebook-style) scored 4.8 — the best.
It works because:
  - Gives the LLM room to "think" by extracting passages first
  - Asks for explanatory answers (not just one-liner responses)
  - Clear structure: context → query → answer format

We extend P2 with:
  - Source citation requirement (filename + page number)
  - Confidence level declaration (high/medium/low)
  - Table formatting instruction (when tables are in context)
  - Image context instruction (when images are in context)
"""


def build_rag_prompt(
    query: str,
    chunks: list[dict],
    confidence: str,
) -> str:
    """
    Build the main RAG generation prompt.

    Based on P2 (Notebook-style, winner from experiments, score 4.8)
    Extended with citation requirement, confidence level, and sub-query synthesis.

    Args:
        query      : the user's question
        chunks     : filtered, scored chunks from CRAG (retriever output)
        confidence : 'high' | 'medium' | 'low' from CRAG filter

    Returns:
        Complete prompt string ready to send to the LLM.
    """
    context_str = _format_context(chunks)
    confidence_instruction = _confidence_instruction(confidence)

    # Check if this was a decomposed multihop query
    sub_queries = chunks[0].get("_all_sub_queries") if chunks else None
    sub_query_instruction = ""
    if sub_queries and len(sub_queries) > 1:
        sq_list = "\n".join(f"  {i+1}. {sq}" for i, sq in enumerate(sub_queries))
        sub_query_instruction = f"""
This question was broken into sub-questions for retrieval. Answer each step before combining:
{sq_list}

Synthesise all sub-answers into one final answer.
"""

    # Image context instructions when image chunks are present
    has_images = any(c.get("chunk_type") == "image" for c in chunks)
    image_instruction = ""
    if has_images:
        image_instruction = """
IMAGE CONTEXT INSTRUCTIONS:
- Image descriptions above are AI-generated captions of engineering diagrams
- If the image caption mentions specific component names, symbols, or values, treat these as facts
- If answering about a diagram: describe what the diagram shows based on the caption
- If the actual image is provided alongside this text, use BOTH the caption and the image
"""

    return f"""Based on the following context items from engineering documents, please answer the query.

Give yourself room to think by extracting relevant passages from the context before answering the query.
Don't return the thinking, only return the final answer.
Make sure your answers are as explanatory as possible.
{sub_query_instruction}
IMPORTANT REQUIREMENTS:
1. Only use information from the provided context. Do not add facts from outside the context.
2. For every fact you state, cite the source: (Source: filename, Page X)
3. If a table is in the context, format relevant data as a table in your answer.
4. {confidence_instruction}
{image_instruction}
Context:
{context_str}

User query: {query}

Answer:"""


def build_self_rag_critique_prompt(query: str, context_str: str, answer: str) -> str:
    """
    Self-RAG critique prompt: ask LLM to verify its own answer is grounded.

    FROM THE IMPLEMENTATION GUIDE:
    "Self-RAG: self-reflection and critique — emit only when grounded"

    The LLM is asked to check if every factual claim in its answer
    can be verified in the provided context. This catches hallucinations
    before the answer reaches the user.

    Returns prompt string. Expected LLM response: SUPPORTED, PARTIALLY_SUPPORTED,
    or NOT_SUPPORTED.
    """
    return f"""Review the following answer and determine whether every factual claim
in the answer is supported by the provided context.

Context:
{context_str}

Question: {query}

Answer to review:
{answer}

Check each factual claim in the answer. Is every specific fact, number,
name, or technical detail verifiable in the context above?

Respond with ONLY one of:
- SUPPORTED (all claims are in the context)
- PARTIALLY_SUPPORTED (most claims are in context but some are not)
- NOT_SUPPORTED (answer contains significant facts not in the context)"""


def build_hyde_prompt(query: str) -> str:
    """
    HyDE prompt: generate a hypothetical answer document for retrieval.
    Defined here for completeness but called from hyde.py.
    """
    return f"""You are a technical document expert. Write a short technical paragraph
(80-120 words) that would be a direct answer to the following question —
as if it were text from an engineering manual, datasheet, or safety document.

Use precise technical language. Include specific values, units, and terminology.

Question: {query}

Technical paragraph:"""


def _format_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a readable context string.

    Tables get a special header to signal to the LLM that Markdown formatting
    is available. Images get an [IMAGE DESCRIPTION] label.
    """
    parts = []
    for i, chunk in enumerate(chunks, 1):
        chunk_type = chunk.get("chunk_type", "text")
        source     = chunk.get("filename", "unknown")
        page       = chunk.get("page", "?")
        # Use parent_content for generation if available — gives LLM more context
        # parent_content is the larger passage; content is the small retrieval chunk
        content    = chunk.get("parent_content") or chunk.get("content", "")
        # Show which sub-query this chunk answers (helps LLM synthesise multihop)
        sub_query  = chunk.get("sub_query", "")
        sq_label   = f" | Answers: \"{sub_query}\"" if sub_query else ""

        if chunk_type == "table":
            parts.append(
                f"[Context {i} — TABLE from {source}, Page {page}{sq_label}]\n{content}"
            )
        elif chunk_type == "image":
            parts.append(
                f"[Context {i} — IMAGE DESCRIPTION from {source}, Page {page}{sq_label}]\n{content}"
            )
        else:
            parts.append(
                f"[Context {i} — TEXT from {source}, Page {page}{sq_label}]\n{content}"
            )

    return "\n\n".join(parts)


def _confidence_instruction(confidence: str) -> str:
    """Return the confidence-appropriate instruction for the prompt."""
    if confidence == "high":
        return "The context contains clear relevant information. Answer confidently and thoroughly."
    elif confidence == "medium":
        return "The context may be partially relevant. State your confidence level in the answer."
    else:  # low
        return ("The retrieved context may not fully answer this question. "
                "State clearly what you found and what is uncertain. "
                "Do not fabricate specific values or specifications.")
