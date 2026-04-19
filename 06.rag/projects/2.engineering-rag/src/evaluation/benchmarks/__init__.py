"""
benchmarks/ — Industrial dataset evaluation for the Engineering RAG system.

WHAT THIS PACKAGE DOES:
Each module loads a standard benchmark dataset from local files in data/benchmarks/,
runs every question through the RAG pipeline, and measures performance.

WHY EACH BENCHMARK TESTS SOMETHING DIFFERENT:

  SQuAD        → Tests: Can we find a specific fact buried in a passage?
                 Format: question + passage → extractive span answer
                 Metric: Exact Match (EM) and F1 score (word overlap)
                 Challenge: Answer is usually a direct quote, not generated

  Natural Questions → Tests: Can we handle real Google searches?
                 Format: real user queries → long-form Wikipedia answers
                 Metric: EM on short answers, judge on long answers
                 Challenge: Questions are naturally phrased (not expert-written)

  HotpotQA     → Tests: Can we reason across TWO documents at once?
                 Format: question requires combining facts from 2 passages
                 Metric: EM + supporting fact recall (did we use both docs?)
                 Challenge: RRF must surface BOTH relevant chunks, not just one

  MS MARCO     → Tests: Pure retrieval quality (not generation)
                 Format: query + 1000 candidate passages → ranked retrieval
                 Metric: NDCG@10, MRR@10, Recall@100
                 Challenge: Measures whether pgvector + HyDE beats BM25 baseline

  RAGAS Synthetic → Tests: Does our system hallucinate on trick questions?
                 Format: questions generated FROM our own documents
                 Metric: faithfulness (RAGAS), answer relevancy, context recall
                 Challenge: Questions designed to probe for hallucination

  Custom       → Tests: Domain-specific documents (PDFs placed in data/benchmarks/custom/)
                 Format: user-provided questions + documents
                 Metric: Full LLM-judge suite

HOW TO USE:
  1. Download dataset files (see README in each data/benchmarks/<name>/ folder)
  2. python run_benchmarks.py --datasets squad hotpotqa
  3. Results written to data/benchmarks/results/
"""
