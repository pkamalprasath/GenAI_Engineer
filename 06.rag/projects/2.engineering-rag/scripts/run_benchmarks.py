"""
run_benchmarks.py — CLI to run industrial dataset evaluations.

USAGE:
    # Test against SQuAD (place dev-v2.0.json in data/benchmarks/squad/)
    python run_benchmarks.py --datasets squad

    # Multiple benchmarks
    python run_benchmarks.py --datasets squad hotpotqa

    # All available benchmarks
    python run_benchmarks.py --datasets all

    # Generate synthetic questions first, then evaluate
    python run_benchmarks.py --datasets ragas_synth --generate

    # Control sample count
    python run_benchmarks.py --datasets squad --samples 50

    # Skip cleanup (keep benchmark docs in DB for inspection)
    python run_benchmarks.py --datasets squad --no-cleanup

    # Save results to CSV
    python run_benchmarks.py --datasets squad hotpotqa --output results/

DATASETS:
    squad          → SQuAD 2.0 (Simple QA + unanswerable)
    natural_questions → Real Google queries (open retrieval)
    hotpotqa       → Multi-hop reasoning across two docs
    msmarco        → Pure retrieval benchmark (NDCG@10, MRR@10)
    ragas_synth    → Synthetic trick questions from your own docs
    custom         → Your own questions in data/benchmarks/custom/questions.json

WHAT EACH BENCHMARK TESTS:
    squad          → Fact extraction accuracy (EM/F1), CRAG abstention on unanswerable
    natural_questions → Real-world query handling, HyDE effectiveness
    hotpotqa       → Multi-document reasoning, RRF surface quality
    msmarco        → Raw retrieval quality vs BM25 baseline
    ragas_synth    → Hallucination detection, faithfulness, domain coverage
    custom         → Your specific use case
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingest.vectorstore import VectorStore
from src.evaluation.benchmarks.runner import BenchmarkRunner, compare_reports
from src.evaluation.benchmarks.base import print_report


DATA_DIR = Path(__file__).parent.parent / "data" / "benchmarks"


def main():
    parser = argparse.ArgumentParser(
        description="Run industrial benchmark evaluations against the Engineering RAG system"
    )
    parser.add_argument(
        "--datasets", nargs="+",
        choices=["squad", "natural_questions", "hotpotqa", "msmarco", "ragas_synth", "custom", "all"],
        required=True,
        help="Which benchmark datasets to evaluate"
    )
    parser.add_argument("--samples",    type=int, default=100,
                        help="Number of samples per dataset (default: 100)")
    parser.add_argument("--generate",  action="store_true",
                        help="Generate synthetic testset before evaluating (ragas_synth)")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="Keep benchmark docs in DB after evaluation (for inspection)")
    parser.add_argument("--output",    type=str, default=None,
                        help="Directory to save CSV reports")
    parser.add_argument("--verbose",   action="store_true", default=True)
    parser.add_argument("--quiet",     action="store_true",
                        help="Suppress per-sample output")
    args = parser.parse_args()

    verbose = args.verbose and not args.quiet

    # Expand "all"
    datasets = args.datasets
    if "all" in datasets:
        datasets = ["squad", "natural_questions", "hotpotqa", "msmarco", "ragas_synth", "custom"]

    # Connect to DB
    print("[Setup] Connecting to PostgreSQL + pgvector...")
    try:
        vs = VectorStore()
        vs.init_schema()
        print("[Setup] Database connected ✓")
    except Exception as e:
        print(f"[Setup] Database connection failed: {e}")
        print("[Setup] Make sure Docker is running: docker compose up -d")
        sys.exit(1)

    runner  = BenchmarkRunner(vectorstore=vs)
    reports = []

    for dataset in datasets:
        try:
            samples = _load_dataset(dataset, args.samples, args.generate)
            if not samples:
                print(f"[Skip] {dataset}: no samples loaded")
                continue

            report = runner.run(
                dataset_name=dataset,
                samples=samples,
                cleanup_after=not args.no_cleanup,
                verbose=verbose,
            )
            reports.append(report)
            print_report(report)

            # Save CSV
            if args.output:
                _save_report_csv(report, Path(args.output))

        except FileNotFoundError as e:
            print(f"\n[Skip] {dataset}: {e}\n")
        except Exception as e:
            print(f"\n[Error] {dataset} failed: {e}\n")
            import traceback
            traceback.print_exc()

    # Cross-benchmark comparison table
    if len(reports) > 1:
        compare_reports(reports)

    vs.close()
    print("\n[Done] Benchmark evaluation complete.")


def _load_dataset(
    name: str,
    max_samples: int,
    generate: bool,
) -> list:
    """Load samples for a given dataset name."""

    if name == "squad":
        from src.evaluation.benchmarks.squad import load_squad
        return load_squad(DATA_DIR / "squad", max_samples=max_samples)

    elif name == "natural_questions":
        from src.evaluation.benchmarks.natural_questions import load_natural_questions
        return load_natural_questions(DATA_DIR / "natural_questions", max_samples=max_samples)

    elif name == "hotpotqa":
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        return load_hotpotqa(DATA_DIR / "hotpotqa", max_samples=max_samples)

    elif name == "msmarco":
        from src.evaluation.benchmarks.msmarco import load_msmarco
        samples, _ = load_msmarco(DATA_DIR / "msmarco", max_queries=max_samples)
        return samples

    elif name == "ragas_synth":
        testset_path = DATA_DIR / "ragas_synth" / "testset.json"

        if generate or not testset_path.exists():
            return _generate_ragas_synth(testset_path, max_samples)
        else:
            from src.evaluation.benchmarks.ragas_synth import load_synthetic_testset
            print(f"[RAGAS Synth] Loading existing testset from {testset_path}")
            return load_synthetic_testset(testset_path)

    elif name == "custom":
        return _load_custom(DATA_DIR / "custom", max_samples)

    return []


def _generate_ragas_synth(testset_path: Path, num_questions: int) -> list:
    """Generate RAGAS synthetic testset from your own ingested documents."""
    from src.evaluation.benchmarks.ragas_synth import generate_synthetic_testset
    from src.ingest.vectorstore import VectorStore

    print("[RAGAS Synth] Generating synthetic testset from your documents...")

    vs = VectorStore()
    vs.init_schema()

    # Pull a sample of chunks from the DB as source material
    try:
        with vs._conn.cursor() as cur:
            cur.execute("""
                SELECT c.content, c.chunk_type, c.page, d.filename
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                WHERE c.chunk_type = 'text'
                  AND d.doc_type NOT LIKE 'bench_%'
                ORDER BY RANDOM()
                LIMIT 200
            """)
            rows = cur.fetchall()
    finally:
        vs.close()

    if not rows:
        print("[RAGAS Synth] No documents in DB. Ingest some docs first:")
        print("  python ingest_docs.py data/sample_docs/")
        return []

    source_chunks = [
        {"content": row[0], "chunk_type": row[1], "page": row[2], "filename": row[3]}
        for row in rows
    ]

    return generate_synthetic_testset(
        source_chunks=source_chunks,
        num_questions=num_questions,
        output_path=testset_path,
    )


def _load_custom(custom_dir: Path, max_samples: int) -> list:
    """
    Load custom questions from data/benchmarks/custom/questions.json.

    Format of questions.json:
    [
      {
        "question": "What is the maximum operating pressure of valve V-200?",
        "ground_truth": "150 PSI",
        "context": "Optional: paste relevant passage here"
      }
    ]

    If context is empty, the system will retrieve from your indexed documents.
    """
    from src.evaluation.benchmarks.base import BenchmarkSample

    questions_file = custom_dir / "questions.json"
    if not questions_file.exists():
        print(f"[Custom] No questions.json found at {questions_file}")
        print("[Custom] Create a questions.json file with your domain-specific questions")
        print('[Custom] Format: [{"question": "...", "ground_truth": "...", "context": ""}]')
        return []

    with open(questions_file, encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for item in data[:max_samples]:
        q   = item.get("question", "").strip()
        gt  = item.get("ground_truth", "").strip()
        ctx = item.get("context", "").strip()
        if not q:
            continue
        samples.append(BenchmarkSample(
            question=q,
            ground_truth=gt,
            context_docs=[ctx] if ctx else [],
            metadata={"dataset": "custom"},
        ))

    print(f"[Custom] Loaded {len(samples)} questions from {questions_file}")
    return samples


def _save_report_csv(report, output_dir: Path) -> None:
    """Save per-sample results to CSV."""
    import csv
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"results_{report.dataset_name}.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "question", "ground_truth", "answer", "exact_match", "f1_score",
            "judge_score", "factuality", "confidence", "latency_sec",
            "dataset", "question_type",
        ])
        writer.writeheader()
        for r in report.results:
            writer.writerow({
                "question":      r.sample.question[:120],
                "ground_truth":  r.sample.ground_truth[:120],
                "answer":        r.answer[:120],
                "exact_match":   r.exact_match,
                "f1_score":      r.f1_score,
                "judge_score":   r.judge_score,
                "factuality":    r.factuality,
                "confidence":    r.confidence,
                "latency_sec":   r.latency_sec,
                "dataset":       r.sample.metadata.get("dataset", ""),
                "question_type": r.sample.metadata.get("question_type", ""),
            })
    print(f"[Output] Results saved to {output_file}")


if __name__ == "__main__":
    main()
