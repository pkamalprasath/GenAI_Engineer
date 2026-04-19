"""
ragas_synth.py — RAGAS synthetic test generation + evaluation.

WHAT IS RAGAS?
RAGAS (Retrieval Augmented Generation Assessment) is a framework that:
1. GENERATES synthetic test questions from your OWN documents
2. EVALUATES RAG outputs on dimensions standard LLM-judge misses

WHY GENERATE SYNTHETIC TESTS?
Your own documents ARE your production data. Testing on SQuAD/NQ tells you
about general QA ability, but NOT whether your specific docs are indexed well.

RAGAS generation creates:
  - Simple questions  → basic fact extraction ("What is the torque for M12 bolts?")
  - Reasoning questions → multi-step ("Given the maintenance interval and current hours,
                           is service due?")
  - Multi-context     → requires combining two chunks
  - Conditional       → "What if the temperature exceeds the limit?"
  - Trick questions   → intentionally hard, designed to expose hallucination

WHY RAGAS METRICS GO BEYOND LLM-JUDGE:

  Faithfulness (0-1):
    "Does every claim in the answer appear in the retrieved context?"
    LLM-judge says "good answer" even if the answer contains hallucinated facts.
    Faithfulness catches those. Target: > 0.95

  Answer Relevancy (0-1):
    "Does the answer actually address the question asked?"
    A long, factually correct answer that doesn't answer the QUESTION scores low.
    Target: > 0.85

  Context Recall (0-1):
    "Does the retrieved context contain everything needed to answer?"
    If context recall is low, the retriever is failing (not the generator).
    Target: > 0.90

  Context Precision (0-1):
    "Are the retrieved chunks relevant? Or are there a lot of noise chunks?"
    Low precision → irrelevant context is being passed to the LLM → confusion.
    Target: > 0.85

TWO MODES OF THIS MODULE:

  Mode 1: GENERATE — create synthetic test questions from your documents
    Input:  PDF files in data/benchmarks/custom/ (or data/sample_docs/)
    Output: data/benchmarks/ragas_synth/testset.json
    Cost:   Uses GPT-4o-mini for generation (~ $0.01 per question)

  Mode 2: EVALUATE — run RAGAS metrics on pipeline outputs
    Input:  questions, answers, retrieved contexts
    Output: {faithfulness, answer_relevancy, context_recall, context_precision}

WHAT TO PROVIDE:
  Place your PDF/TXT documents in: data/benchmarks/custom/
  Then run: python run_benchmarks.py --datasets ragas_synth --generate
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass

from src.evaluation.benchmarks.base import BenchmarkSample


# ── Synthetic generation ────────────────────────────────────────────────────

@dataclass
class SynthQuestion:
    question:     str
    ground_truth: str
    context:      str
    question_type: str    # "simple", "reasoning", "multi_context", "conditional", "trick"


def generate_synthetic_testset(
    source_chunks: list[dict],
    num_questions: int = 25,
    question_types: list[str] | None = None,
    output_path: Path | None = None,
) -> list[BenchmarkSample]:
    """
    Generate synthetic test questions from your own document chunks.

    This function asks an LLM to create questions that:
    - Have a clear, verifiable answer IN the provided chunks
    - Cover different difficulty levels (simple → trick)
    - Are designed to probe for hallucination

    Args:
        source_chunks  : list of chunk dicts from your vectorstore (content + metadata)
        num_questions  : how many questions to generate per type
        question_types : which types to generate (None = all 5 types)
        output_path    : save generated testset to JSON (optional)

    Returns:
        list of BenchmarkSample ready for the runner
    """
    from openai import OpenAI
    from configs.settings import OPENAI_API_KEY, TEXT_LLM

    if question_types is None:
        question_types = ["simple", "reasoning", "multi_context", "conditional", "trick"]

    client = OpenAI(api_key=OPENAI_API_KEY)
    samples = []

    # Distribute questions across types
    per_type = max(1, num_questions // len(question_types))

    for q_type in question_types:
        print(f"[RAGAS Synth] Generating {per_type} {q_type} questions...")
        type_samples = _generate_type(client, TEXT_LLM, source_chunks, q_type, per_type)
        samples.extend(type_samples)
        time.sleep(0.5)  # Rate limit buffer

    print(f"[RAGAS Synth] Generated {len(samples)} questions total")

    # Save to disk for reuse (expensive to regenerate)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                [_sample_to_dict(s) for s in samples],
                f, indent=2, ensure_ascii=False
            )
        print(f"[RAGAS Synth] Saved testset to {output_path}")

    return samples


def load_synthetic_testset(testset_path: Path) -> list[BenchmarkSample]:
    """Load a previously generated synthetic testset from JSON."""
    if not testset_path.exists():
        raise FileNotFoundError(
            f"Synthetic testset not found: {testset_path}\n"
            "Run with --generate flag first: python run_benchmarks.py --datasets ragas_synth --generate"
        )

    with open(testset_path, encoding="utf-8") as f:
        data = json.load(f)

    return [
        BenchmarkSample(
            question=d["question"],
            ground_truth=d["ground_truth"],
            context_docs=[d["context"]],
            metadata={
                "question_type": d.get("question_type", "unknown"),
                "dataset":       "ragas_synth",
            },
        )
        for d in data
    ]


def _generate_type(
    client,
    model: str,
    chunks: list[dict],
    q_type: str,
    count: int,
) -> list[BenchmarkSample]:
    """Generate `count` questions of a given type from random chunks."""
    import random

    prompts = {
        "simple": """Given this text passage, generate {n} simple factual questions.
Each question should:
- Have a single, clear answer that appears directly in the passage
- Be answerable by finding one specific fact
- NOT require inference or combining multiple facts

Format as JSON array: [{{"question": "...", "answer": "..."}}]""",

        "reasoning": """Given this text passage, generate {n} reasoning questions.
Each question should:
- Require understanding relationships or implications in the text
- NOT be directly stated — reader must infer
- Have a clear, verifiable answer

Format as JSON array: [{{"question": "...", "answer": "..."}}]""",

        "multi_context": """Given these TWO passages, generate {n} questions that require BOTH passages to answer.
The question should be unanswerable from either passage alone.
Format as JSON array: [{{"question": "...", "answer": "..."}}]""",

        "conditional": """Given this text passage, generate {n} conditional/hypothetical questions.
Example: "What would happen if the temperature exceeds the maximum?"
The answer should be grounded in the text.
Format as JSON array: [{{"question": "...", "answer": "..."}}]""",

        "trick": """Given this text passage, generate {n} TRICK questions designed to expose hallucination.
These should be questions where:
- A naive system might make up a plausible-sounding answer
- The answer is specifically NOT in the passage (and the correct answer is "I don't know")
OR questions where:
- A small detail is easy to get wrong (wrong number, wrong unit, wrong entity)
Format as JSON array: [{{"question": "...", "answer": "..."}}]""",
    }

    template = prompts.get(q_type, prompts["simple"])
    samples = []

    # For multi_context, use two chunks; others use one
    chunk_sample_size = 2 if q_type == "multi_context" else 1
    attempts_per_batch = max(1, count // 5) + 1  # generate in batches of 5

    generated = 0
    max_attempts = count * 3  # retry budget

    for attempt in range(max_attempts):
        if generated >= count:
            break

        selected = random.sample(chunks, min(chunk_sample_size, len(chunks)))
        context  = "\n\n---\n\n".join(c.get("content", "") for c in selected)

        if not context.strip():
            continue

        batch_size = min(5, count - generated)
        prompt = (
            f"Passage:\n{context[:3000]}\n\n"
            + template.format(n=batch_size)
        )

        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.7,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content.strip()

            # Parse JSON response
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                continue

            items = json.loads(raw[start:end])
            for item in items:
                q = item.get("question", "").strip()
                a = item.get("answer", "").strip()
                if q and a and len(q) >= 10:
                    samples.append(BenchmarkSample(
                        question=q,
                        ground_truth=a,
                        context_docs=[context],
                        metadata={
                            "question_type": q_type,
                            "dataset":       "ragas_synth",
                        },
                    ))
                    generated += 1
                    if generated >= count:
                        break

        except Exception as e:
            print(f"  [RAGAS Synth] Generation failed (attempt {attempt}): {e}")
            time.sleep(1)
            continue

    return samples[:count]


def _sample_to_dict(s: BenchmarkSample) -> dict:
    return {
        "question":      s.question,
        "ground_truth":  s.ground_truth,
        "context":       s.context_docs[0] if s.context_docs else "",
        "question_type": s.metadata.get("question_type", "unknown"),
    }


# ── RAGAS evaluation metrics ────────────────────────────────────────────────

def compute_ragas_metrics(
    questions:  list[str],
    answers:    list[str],
    contexts:   list[list[str]],    # retrieved chunks per question
    ground_truths: list[str],
) -> dict:
    """
    Compute RAGAS faithfulness, answer relevancy, context recall, context precision.

    Uses the RAGAS library (pip install ragas).

    Args:
        questions     : list of question strings
        answers       : list of generated answers
        contexts      : list of lists (retrieved chunk contents per question)
        ground_truths : list of ground truth answers

    Returns:
        {faithfulness, answer_relevancy, context_recall, context_precision,
         avg_score}
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
        )
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from configs.settings import OPENAI_API_KEY, TEXT_LLM

        data = {
            "question":     questions,
            "answer":       answers,
            "contexts":     contexts,
            "ground_truth": ground_truths,
        }
        dataset = Dataset.from_dict(data)

        llm        = ChatOpenAI(model=TEXT_LLM, api_key=OPENAI_API_KEY)
        embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
            llm=llm,
            embeddings=embeddings,
        )

        scores = {
            "faithfulness":       round(float(result["faithfulness"]), 4),
            "answer_relevancy":   round(float(result["answer_relevancy"]), 4),
            "context_recall":     round(float(result["context_recall"]), 4),
            "context_precision":  round(float(result["context_precision"]), 4),
        }
        scores["avg_score"] = round(
            sum(scores.values()) / len(scores), 4
        )
        return scores

    except ImportError:
        print("[RAGAS] ragas or datasets not installed — skipping RAGAS metrics")
        return {}
    except Exception as e:
        print(f"[RAGAS] Evaluation failed: {e}")
        return {}
