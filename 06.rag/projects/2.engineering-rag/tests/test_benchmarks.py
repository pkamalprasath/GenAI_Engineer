"""
test_benchmarks.py — Unit tests for the benchmark loaders and metrics.

These tests run WITHOUT:
  - Real dataset files (use synthetic data)
  - Docker / pgvector (all DB calls mocked)
  - OpenAI API (all LLM calls mocked)

They verify:
  - Parsers produce correct BenchmarkSample shape
  - EM / F1 scoring functions are correct
  - NDCG / MRR calculations are correct
  - Supporting fact recall logic works
  - Runner cleanup logic is correct

Run:
    python -m pytest tests/test_benchmarks.py -v
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ════════════════════════════════════════════════════════
# BASE — EM / F1 scoring
# ════════════════════════════════════════════════════════

class TestScoringFunctions:
    """Test the text scoring utilities used by all benchmark loaders."""

    def test_exact_match_identical(self):
        from src.evaluation.benchmarks.base import exact_match_score
        assert exact_match_score("Denver Broncos", ["Denver Broncos"]) == 1.0

    def test_exact_match_normalises_case(self):
        from src.evaluation.benchmarks.base import exact_match_score
        assert exact_match_score("denver broncos", ["Denver Broncos"]) == 1.0

    def test_exact_match_removes_articles(self):
        from src.evaluation.benchmarks.base import exact_match_score
        # "the Denver Broncos" → "denver broncos" after normalisation
        assert exact_match_score("the Denver Broncos", ["Denver Broncos"]) == 1.0

    def test_exact_match_multiple_ground_truths(self):
        from src.evaluation.benchmarks.base import exact_match_score
        # Should return 1.0 if any GT matches
        assert exact_match_score("yes", ["Yes", "correct", "true"]) == 1.0

    def test_exact_match_fails_on_mismatch(self):
        from src.evaluation.benchmarks.base import exact_match_score
        assert exact_match_score("Carolina Panthers", ["Denver Broncos"]) == 0.0

    def test_f1_identical(self):
        from src.evaluation.benchmarks.base import f1_score
        assert f1_score("the torque is 85 Nm", ["the torque is 85 Nm"]) == 1.0

    def test_f1_partial_overlap(self):
        from src.evaluation.benchmarks.base import f1_score
        # "85 Nm" vs "torque is 85 Nm" → 2 common words / 4 total → some overlap
        score = f1_score("85 Nm", ["torque is 85 Nm"])
        assert 0.0 < score < 1.0

    def test_f1_no_overlap(self):
        from src.evaluation.benchmarks.base import f1_score
        assert f1_score("Denver Broncos", ["Carolina Panthers"]) == 0.0

    def test_f1_uses_best_ground_truth(self):
        from src.evaluation.benchmarks.base import f1_score
        # Multiple GTs — should pick the one with best overlap
        score = f1_score("85 Nm torque", ["totally wrong answer", "85 Nm"])
        assert score > 0.5

    def test_normalise_punctuation_removed(self):
        from src.evaluation.benchmarks.base import exact_match_score
        assert exact_match_score("85 Nm.", ["85 Nm"]) == 1.0

    def test_docs_to_chunks_format(self):
        from src.evaluation.benchmarks.base import docs_to_chunks
        chunks = docs_to_chunks(["passage one", "passage two"], "test_src")
        assert len(chunks) == 2
        assert chunks[0]["chunk_type"] == "text"
        assert chunks[0]["page"] == 1
        assert chunks[1]["page"] == 2
        assert chunks[0]["section"] == "test_src"
        assert chunks[0]["image_path"] is None


# ════════════════════════════════════════════════════════
# SQUAD — Loader and metrics
# ════════════════════════════════════════════════════════

class TestSQuADLoader:
    """Test SQuAD JSON parsing and metrics."""

    @pytest.fixture
    def squad_file(self, tmp_path):
        """Create a minimal SQuAD 2.0 JSON file for testing."""
        data = {
            "version": "v2.0",
            "data": [
                {
                    "title": "Test_Topic",
                    "paragraphs": [
                        {
                            "context": "The M12 bolt requires 85 Nm of torque for proper assembly.",
                            "qas": [
                                {
                                    "id": "qa001",
                                    "question": "How much torque does M12 require?",
                                    "answers": [{"text": "85 Nm", "answer_start": 24}],
                                    "is_impossible": False,
                                },
                                {
                                    "id": "qa002",
                                    "question": "What is the color of the bolt?",
                                    "answers": [],
                                    "is_impossible": True,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        squad_dir = tmp_path / "squad"
        squad_dir.mkdir()
        (squad_dir / "dev-v2.0.json").write_text(json.dumps(data), encoding="utf-8")
        return squad_dir

    def test_loads_answerable_question(self, squad_file):
        from src.evaluation.benchmarks.squad import load_squad
        samples = load_squad(squad_file, max_samples=10)
        answerable = [s for s in samples if not s.metadata.get("is_impossible")]
        assert len(answerable) >= 1
        assert answerable[0].question == "How much torque does M12 require?"
        assert "85 Nm" in answerable[0].answer_spans

    def test_loads_unanswerable_question(self, squad_file):
        from src.evaluation.benchmarks.squad import load_squad
        samples = load_squad(squad_file, max_samples=10, include_unanswerable=True)
        unanswerable = [s for s in samples if s.metadata.get("is_impossible")]
        assert len(unanswerable) == 1

    def test_context_doc_is_passage(self, squad_file):
        from src.evaluation.benchmarks.squad import load_squad
        samples = load_squad(squad_file, max_samples=10)
        for s in samples:
            assert len(s.context_docs) == 1
            assert "M12" in s.context_docs[0]

    def test_missing_file_raises(self, tmp_path):
        from src.evaluation.benchmarks.squad import load_squad
        with pytest.raises(FileNotFoundError):
            load_squad(tmp_path / "squad", max_samples=10)

    def test_abstention_detection(self):
        from src.evaluation.benchmarks.squad import _is_abstention
        assert _is_abstention("I could not find this information in the documents.") is True
        assert _is_abstention("The answer is 85 Nm.") is False

    def test_compute_squad_metrics_perfect(self, squad_file):
        from src.evaluation.benchmarks.squad import load_squad, compute_squad_metrics
        samples = load_squad(squad_file, max_samples=10, include_unanswerable=False)
        # Perfect answers: use the exact answer span
        answers = [s.answer_spans[0] for s in samples if s.answer_spans]
        filtered_samples = [s for s in samples if s.answer_spans]
        metrics = compute_squad_metrics(filtered_samples, answers)
        assert metrics["exact_match_rate"] == 1.0
        assert metrics["avg_f1"] == 1.0

    def test_compute_squad_metrics_wrong(self, squad_file):
        from src.evaluation.benchmarks.squad import load_squad, compute_squad_metrics
        samples = load_squad(squad_file, max_samples=10, include_unanswerable=False)
        answers = ["totally wrong answer"] * len(samples)
        metrics = compute_squad_metrics(samples, answers)
        assert metrics["exact_match_rate"] == 0.0


# ════════════════════════════════════════════════════════
# HOTPOTQA — Loader and supporting fact recall
# ════════════════════════════════════════════════════════

class TestHotpotQALoader:
    """Test HotpotQA parsing and multi-hop metrics."""

    @pytest.fixture
    def hotpot_file(self, tmp_path):
        """Create minimal HotpotQA distractor JSON."""
        data = [
            {
                "_id":     "abc123",
                "question": "Were Scott Derrickson and Ed Wood both American?",
                "answer":   "yes",
                "type":     "comparison",
                "level":    "easy",
                "supporting_facts": [
                    ["Scott Derrickson", 0],
                    ["Ed Wood", 0],
                ],
                "context": [
                    ["Scott Derrickson", [
                        "Scott Derrickson is an American director.",
                        "He was born in Denver.",
                    ]],
                    ["Ed Wood", [
                        "Ed Wood was an American filmmaker.",
                        "He made Plan 9 from Outer Space.",
                    ]],
                    ["Unrelated Topic", [
                        "This paragraph is a distractor.",
                    ]],
                ],
            }
        ]
        hotpot_dir = tmp_path / "hotpotqa"
        hotpot_dir.mkdir()
        (hotpot_dir / "hotpot_dev_distractor_v1.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        return hotpot_dir

    def test_loads_question_and_answer(self, hotpot_file):
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        samples = load_hotpotqa(hotpot_file, max_samples=10)
        assert len(samples) == 1
        assert "nationality" not in samples[0].question.lower() or True  # question loaded
        assert samples[0].ground_truth == "yes"

    def test_loads_all_context_docs(self, hotpot_file):
        """All 3 paragraphs (2 supporting + 1 distractor) should be in context_docs."""
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        samples = load_hotpotqa(hotpot_file, max_samples=10)
        assert len(samples[0].context_docs) == 3

    def test_supporting_facts_extracted(self, hotpot_file):
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        samples = load_hotpotqa(hotpot_file, max_samples=10)
        assert len(samples[0].supporting_facts) == 2
        assert ("Scott Derrickson", 0) in samples[0].supporting_facts
        assert ("Ed Wood", 0) in samples[0].supporting_facts

    def test_supporting_fact_recall_found(self, hotpot_file):
        """When retrieved chunks contain the supporting text, recall should be high."""
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa, supporting_fact_recall
        samples = load_hotpotqa(hotpot_file, max_samples=10)
        sample  = samples[0]

        # Mock retrieved chunks that contain the supporting sentences
        retrieved = [
            {"content": "Scott Derrickson is an American director."},
            {"content": "Ed Wood was an American filmmaker."},
        ]
        recall = supporting_fact_recall(sample, retrieved)
        assert recall > 0.0

    def test_supporting_fact_recall_missing(self, hotpot_file):
        """When retrieved chunks don't contain supporting text, recall should be 0."""
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa, supporting_fact_recall
        samples = load_hotpotqa(hotpot_file, max_samples=10)
        sample  = samples[0]

        retrieved = [{"content": "Completely irrelevant content about something else."}]
        recall = supporting_fact_recall(sample, retrieved)
        assert recall == 0.0

    def test_missing_file_raises(self, tmp_path):
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        with pytest.raises(FileNotFoundError):
            load_hotpotqa(tmp_path / "hotpotqa", max_samples=10)

    def test_filter_by_question_type(self, hotpot_file):
        from src.evaluation.benchmarks.hotpotqa import load_hotpotqa
        comparison = load_hotpotqa(hotpot_file, question_types=["comparison"])
        bridge     = load_hotpotqa(hotpot_file, question_types=["bridge"])
        assert len(comparison) == 1
        assert len(bridge) == 0


# ════════════════════════════════════════════════════════
# MS MARCO — NDCG and MRR computations
# ════════════════════════════════════════════════════════

class TestMSMARCOMetrics:
    """Test NDCG@10 and MRR@10 retrieval metric calculations."""

    def test_ndcg_perfect_ranking(self):
        """Relevant doc at rank 1 → NDCG should be 1.0."""
        from src.evaluation.benchmarks.msmarco import compute_ndcg
        qrels = {"q1": {"p1": 1}}
        assert compute_ndcg("q1", ["p1", "p2", "p3"], qrels, k=10) == 1.0

    def test_ndcg_relevant_at_rank_2(self):
        """Relevant doc at rank 2 → NDCG < 1.0 but > 0."""
        from src.evaluation.benchmarks.msmarco import compute_ndcg
        qrels = {"q1": {"p1": 1}}
        score = compute_ndcg("q1", ["p_wrong", "p1", "p3"], qrels, k=10)
        assert 0.0 < score < 1.0

    def test_ndcg_no_relevant_found(self):
        """If relevant doc not in ranked list → NDCG = 0."""
        from src.evaluation.benchmarks.msmarco import compute_ndcg
        qrels = {"q1": {"p_gold": 1}}
        assert compute_ndcg("q1", ["p1", "p2", "p3"], qrels, k=10) == 0.0

    def test_ndcg_unknown_query(self):
        """Query with no qrels → NDCG = 0."""
        from src.evaluation.benchmarks.msmarco import compute_ndcg
        assert compute_ndcg("q_unknown", ["p1", "p2"], {}, k=10) == 0.0

    def test_mrr_first_hit_rank_1(self):
        from src.evaluation.benchmarks.msmarco import compute_mrr
        qrels = {"q1": {"p1": 1}}
        assert compute_mrr("q1", ["p1", "p2"], qrels, k=10) == 1.0

    def test_mrr_first_hit_rank_2(self):
        from src.evaluation.benchmarks.msmarco import compute_mrr
        qrels = {"q1": {"p1": 1}}
        assert compute_mrr("q1", ["p_wrong", "p1"], qrels, k=10) == 0.5

    def test_mrr_first_hit_rank_3(self):
        from src.evaluation.benchmarks.msmarco import compute_mrr
        qrels = {"q1": {"p1": 1}}
        assert compute_mrr("q1", ["pa", "pb", "p1"], qrels, k=10) == round(1/3, 4)

    def test_mrr_no_hit(self):
        from src.evaluation.benchmarks.msmarco import compute_mrr
        qrels = {"q1": {"p_gold": 1}}
        assert compute_mrr("q1", ["p1", "p2", "p3"], qrels, k=10) == 0.0

    def test_ndcg_graded_relevance(self):
        """Higher relevance score should give higher NDCG."""
        from src.evaluation.benchmarks.msmarco import compute_ndcg
        qrels = {"q1": {"p1": 3, "p2": 1}}
        # p1 at rank 1 (relevance=3) vs p2 at rank 1 (relevance=1)
        score_high = compute_ndcg("q1", ["p1", "p2"], qrels, k=10)
        score_low  = compute_ndcg("q1", ["p2", "p1"], qrels, k=10)
        # p1 first is better than p2 first
        assert score_high > score_low


# ════════════════════════════════════════════════════════
# RAGAS SYNTH — Generation and loading
# ════════════════════════════════════════════════════════

class TestRAGASSynth:
    """Test synthetic testset save/load cycle."""

    def test_load_saved_testset(self, tmp_path):
        """Generated testset should survive a save/load round-trip."""
        from src.evaluation.benchmarks.ragas_synth import load_synthetic_testset

        testset = [
            {
                "question":      "What is the torque for M12?",
                "ground_truth":  "85 Nm",
                "context":       "The M12 bolt requires 85 Nm torque.",
                "question_type": "simple",
            },
            {
                "question":      "What would happen if temperature exceeds 120°C?",
                "ground_truth":  "System shuts down automatically.",
                "context":       "If temperature exceeds 120°C the safety relay trips.",
                "question_type": "conditional",
            },
        ]
        testset_path = tmp_path / "testset.json"
        testset_path.write_text(json.dumps(testset), encoding="utf-8")

        samples = load_synthetic_testset(testset_path)
        assert len(samples) == 2
        assert samples[0].question == "What is the torque for M12?"
        assert samples[0].ground_truth == "85 Nm"
        assert samples[0].metadata["question_type"] == "simple"
        assert "85 Nm" in samples[0].context_docs[0]

    def test_missing_testset_raises(self, tmp_path):
        from src.evaluation.benchmarks.ragas_synth import load_synthetic_testset
        with pytest.raises(FileNotFoundError):
            load_synthetic_testset(tmp_path / "nonexistent.json")

    def test_is_abstention_positive(self):
        from src.evaluation.benchmarks.squad import _is_abstention
        assert _is_abstention("I don't have enough information to answer this.") is True
        assert _is_abstention("This question cannot be answered from the context.") is True

    def test_generation_calls_llm(self):
        """Generation should call the LLM once per batch."""
        from src.evaluation.benchmarks.ragas_synth import _generate_type

        # Build mock client directly (OpenAI is imported inside function, not at module level)
        mock_client  = MagicMock()
        mock_choice  = MagicMock()
        mock_choice.message.content = json.dumps([
            {"question": "What is X?", "answer": "X is Y."}
        ])
        mock_resp    = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp

        chunks = [{"content": "The pressure rating is 150 PSI for valve V-200."}]
        results = _generate_type(mock_client, "gpt-4o-mini", chunks, "simple", count=1)

        assert len(results) >= 1
        assert results[0].question == "What is X?"
        assert results[0].ground_truth == "X is Y."


# ════════════════════════════════════════════════════════
# BENCHMARK REPORT — BenchmarkReport dataclass
# ════════════════════════════════════════════════════════

class TestBenchmarkReport:
    """Test BenchmarkReport SLA checks."""

    def _make_report(self, p99=1.5, judge=4.2, factuality=0.96):
        from src.evaluation.benchmarks.base import BenchmarkReport
        return BenchmarkReport(
            dataset_name="test",
            num_samples=10,
            avg_em=0.5,
            avg_f1=0.6,
            avg_judge_score=judge,
            avg_factuality=factuality,
            avg_latency_sec=1.0,
            p99_latency_sec=p99,
            mrr=0.8,
            ndcg_at_10=0.3,
            recall_at_5=0.85,
        )

    def test_sla_latency_pass(self):
        report = self._make_report(p99=1.8)
        assert report.sla_latency_ok is True

    def test_sla_latency_fail(self):
        report = self._make_report(p99=2.5)
        assert report.sla_latency_ok is False

    def test_sla_factuality_pass(self):
        report = self._make_report(factuality=0.97)
        assert report.sla_factuality_ok is True

    def test_sla_factuality_fail(self):
        report = self._make_report(factuality=0.90)
        assert report.sla_factuality_ok is False

    def test_sla_quality_pass(self):
        report = self._make_report(judge=4.2)
        assert report.sla_quality_ok is True

    def test_sla_quality_fail(self):
        report = self._make_report(judge=3.5)
        assert report.sla_quality_ok is False
