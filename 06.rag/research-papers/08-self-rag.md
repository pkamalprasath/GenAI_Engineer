# Paper 08 — Self-RAG: Learning to Retrieve, Generate, and Critique

**Authors:** Asai et al.
**Year:** 2023

---

## The Problem It Solved

RAG retrieves and generates but never questions itself. What if the retrieved documents aren't helpful? What if the generated answer contradicts the sources? Standard RAG has no self-awareness.

## Core Idea

Fine-tune the LLM to generate special **reflection tokens** inline with the answer:

```
Reflection token types:
  [Retrieve]     -->  should I retrieve now?
  [IsRel]        -->  is this document relevant?
  [IsSup]        -->  does my answer follow from the document?
  [IsUse]        -->  is my overall response useful?
```

The model interleaves these tokens with generation — deciding when to retrieve, evaluating what it retrieved, and critiquing what it generated. All in one forward pass.

## Key Results

- Outperforms ChatGPT and Llama2-chat on factual QA tasks
- Better citation accuracy than standard RAG
- More controllable — you can adjust which reflection tokens to weight

## Why It Matters

Self-RAG is the first paper to treat **self-critique as a first-class component** of RAG. It foreshadowed the agentic RAG direction — models that plan and evaluate their own retrieval rather than following a fixed pipeline.

## Connection to My Experiments

> RAGAS, as planned in `experiments/05_evaluation.py`, would evaluate from outside what Self-RAG handles internally: faithfulness (IsSup), relevance (IsRel) and answer quality (IsUse). (The RAGAS scores were not computed; the study used an LLM judge.) The engineering RAG project's generator runs a Self-RAG-style grounding check and retries once if the answer is not supported.

---

**Key Takeaway:** The best RAG systems are self-aware. They know what they know, what they retrieved, and whether it helps.
