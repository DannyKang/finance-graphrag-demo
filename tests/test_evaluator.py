"""Tests for GraphRAG evaluation framework."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tiger_etf.graphrag.evaluator import (
    EvalQuestion,
    EvalReport,
    QuestionResult,
    evaluate_keyword_coverage,
    evaluate_keyword_hit,
    evaluate_negative,
    format_eval_report,
    load_eval_questions,
    report_to_dict,
    run_evaluation,
)


# ---------------------------------------------------------------------------
# load_eval_questions
# ---------------------------------------------------------------------------


class TestLoadEvalQuestions:
    def test_load_from_project(self):
        """Load the actual eval_questions.yaml from the project."""
        questions = load_eval_questions()
        assert len(questions) == 50

        # Check categories exist
        cats = {q.category for q in questions}
        assert cats == {
            "single_hop",
            "multi_hop_2",
            "multi_hop_3",
            "aggregation",
            "inference",
            "negative",
        }

    def test_category_counts(self):
        questions = load_eval_questions()
        counts = {}
        for q in questions:
            counts[q.category] = counts.get(q.category, 0) + 1

        assert counts["single_hop"] == 10
        assert counts["multi_hop_2"] == 10
        assert counts["multi_hop_3"] == 10
        assert counts["aggregation"] == 8
        assert counts["inference"] == 7
        assert counts["negative"] == 5

    def test_negative_questions_have_check_field(self):
        questions = load_eval_questions()
        negatives = [q for q in questions if q.category == "negative"]
        for q in negatives:
            assert q.check, f"Negative question missing check: {q.question}"

    def test_non_negative_have_keywords(self):
        questions = load_eval_questions()
        non_neg = [q for q in questions if q.category != "negative"]
        for q in non_neg:
            assert q.expected_keywords, f"Question missing keywords: {q.question}"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_eval_questions(tmp_path / "nonexistent.yaml")

    def test_load_custom_yaml(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            test_category:
              - id: T-01
                query: "테스트 질문?"
                expected_keywords: ["키워드1"]
                difficulty: easy
        """)
        p = tmp_path / "test_q.yaml"
        p.write_text(yaml_content)
        questions = load_eval_questions(p)
        assert len(questions) == 1
        assert questions[0].question == "테스트 질문?"
        assert questions[0].category == "test_category"


# ---------------------------------------------------------------------------
# keyword evaluation
# ---------------------------------------------------------------------------


class TestKeywordHit:
    def test_hit_exact(self):
        assert evaluate_keyword_hit("S&P 500 지수를 추적합니다", ["S&P 500"])

    def test_hit_case_insensitive(self):
        assert evaluate_keyword_hit("apple은 주요 보유종목입니다", ["Apple"])

    def test_hit_any_keyword(self):
        assert evaluate_keyword_hit(
            "NVIDIA가 포함됩니다", ["Apple", "Microsoft", "NVIDIA"]
        )

    def test_miss(self):
        assert not evaluate_keyword_hit("해당 정보를 찾을 수 없습니다", ["S&P 500"])

    def test_empty_keywords(self):
        assert not evaluate_keyword_hit("어떤 응답", [])


class TestKeywordCoverage:
    def test_full_coverage(self):
        assert evaluate_keyword_coverage(
            "S&P500 지수의 총보수는 0.07%입니다", ["S&P500", "총보수", "%"]
        ) == pytest.approx(1.0)

    def test_partial_coverage(self):
        assert evaluate_keyword_coverage(
            "S&P500 지수를 추적합니다", ["S&P500", "총보수", "%"]
        ) == pytest.approx(1 / 3)

    def test_no_coverage(self):
        assert evaluate_keyword_coverage("관련 없는 응답", ["S&P500", "총보수"]) == 0.0

    def test_empty_keywords(self):
        assert evaluate_keyword_coverage("어떤 응답", []) == 0.0


# ---------------------------------------------------------------------------
# negative detection
# ---------------------------------------------------------------------------


class TestNegativeDetection:
    def test_should_not_hallucinate_pass(self):
        assert evaluate_negative(
            "해당 상품이 존재하지 않거나 정보를 찾을 수 없습니다.",
            "should_not_hallucinate",
        )

    def test_should_not_hallucinate_fail(self):
        assert not evaluate_negative(
            "TIGER 비트코인 ETF의 수익률은 연 15%입니다.",
            "should_not_hallucinate",
        )

    def test_should_correct_premise(self):
        assert evaluate_negative(
            "TIGER ETF는 미래에셋자산운용의 브랜드입니다.",
            "should_correct_premise",
        )

    def test_should_correct_premise_fail(self):
        assert not evaluate_negative(
            "삼성자산운용이 운용하는 TIGER ETF는 다음과 같습니다.",
            "should_correct_premise",
        )

    def test_should_not_fabricate(self):
        assert evaluate_negative(
            "해당 시점의 데이터를 확인할 수 없습니다.",
            "should_not_fabricate_data",
        )

    def test_should_provide_disclaimer(self):
        assert evaluate_negative(
            "ETF는 원금 보장 상품이 아니며, 원금 손실 위험이 있습니다.",
            "should_provide_accurate_disclaimer",
        )

    def test_should_provide_disclaimer_fail(self):
        assert not evaluate_negative(
            "네, 원금이 안전하게 보장됩니다.",
            "should_provide_accurate_disclaimer",
        )


# ---------------------------------------------------------------------------
# run_evaluation (without LLM judge)
# ---------------------------------------------------------------------------


class TestRunEvaluation:
    def _make_questions(self) -> list[EvalQuestion]:
        return [
            EvalQuestion(
                question="S&P 500 벤치마크는?",
                category="single_hop",
                difficulty="easy",
                expected_keywords=["S&P 500", "S&P500"],
            ),
            EvalQuestion(
                question="환헤지 여부?",
                category="single_hop",
                difficulty="easy",
                expected_keywords=["환헤지", "환율"],
            ),
            EvalQuestion(
                question="비트코인 ETF?",
                category="negative",
                difficulty="medium",
                check="should_not_hallucinate",
                expected_answer="존재하지 않음",
            ),
        ]

    def _make_results(self) -> list[dict]:
        return [
            {
                "query": "S&P 500 벤치마크는?",
                "response": "이 ETF는 S&P 500 지수를 추적합니다.",
                "latency_seconds": 5.0,
                "status": "success",
            },
            {
                "query": "환헤지 여부?",
                "response": "이 상품은 환율 변동 위험이 있습니다.",
                "latency_seconds": 6.0,
                "status": "success",
            },
            {
                "query": "비트코인 ETF?",
                "response": "해당 상품이 존재하지 않습니다.",
                "latency_seconds": 4.0,
                "status": "success",
            },
        ]

    def test_automated_metrics_only(self):
        report = run_evaluation(
            self._make_results(),
            self._make_questions(),
            use_llm_judge=False,
        )
        assert report.total_questions == 3
        # Both keyword questions hit
        assert report.keyword_hit_rate == 1.0
        # Negative detection passes
        assert report.negative_detection_rate == 1.0
        # No LLM scores
        assert report.avg_correctness == 0.0

    def test_keyword_miss(self):
        results = self._make_results()
        results[0]["response"] = "관련 정보를 찾을 수 없습니다."
        report = run_evaluation(results, self._make_questions(), use_llm_judge=False)
        assert report.keyword_hit_rate == 0.5  # 1 of 2

    def test_category_breakdown(self):
        report = run_evaluation(
            self._make_results(),
            self._make_questions(),
            use_llm_judge=False,
        )
        assert "single_hop" in report.by_category
        assert "negative" in report.by_category
        assert report.by_category["single_hop"].count == 2
        assert report.by_category["negative"].count == 1

    def test_error_status_skipped(self):
        results = self._make_results()
        results[0]["status"] = "error"
        report = run_evaluation(results, self._make_questions(), use_llm_judge=False)
        # Only 1 successful non-negative question
        assert report.keyword_hit_rate == 1.0  # 1 success out of 1

    def test_unknown_question_handled(self):
        results = [
            {
                "query": "알려지지 않은 질문",
                "response": "답변",
                "latency_seconds": 1.0,
                "status": "success",
            }
        ]
        report = run_evaluation(results, self._make_questions(), use_llm_judge=False)
        assert report.total_questions == 1
        assert report.details[0].category == "unknown"


# ---------------------------------------------------------------------------
# report_to_dict
# ---------------------------------------------------------------------------


class TestReportToDict:
    def test_serializable(self):
        import json

        report = run_evaluation(
            [
                {
                    "query": "S&P 500 벤치마크는?",
                    "response": "S&P 500 지수를 추적",
                    "latency_seconds": 3.0,
                    "status": "success",
                }
            ],
            [
                EvalQuestion(
                    question="S&P 500 벤치마크는?",
                    category="single_hop",
                    difficulty="easy",
                    expected_keywords=["S&P 500"],
                ),
            ],
            use_llm_judge=False,
        )
        d = report_to_dict(report)
        # Must be JSON-serializable
        json_str = json.dumps(d, ensure_ascii=False)
        assert "keyword_hit_rate" in json_str

    def test_keys_present(self):
        report = EvalReport()
        d = report_to_dict(report)
        assert "keyword_hit_rate" in d
        assert "keyword_coverage" in d
        assert "negative_detection_rate" in d
        assert "llm_judge" in d
        assert "overall_score" in d
        assert "by_category" in d
        assert "details" in d


# ---------------------------------------------------------------------------
# format_eval_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_format_returns_string(self):
        report = EvalReport(total_questions=3, keyword_hit_rate=0.8)
        text = format_eval_report(report)
        assert "Keyword Hit Rate" in text
        assert isinstance(text, str)
