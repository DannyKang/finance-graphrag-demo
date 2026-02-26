"""Evaluation framework for GraphRAG experiments.

Provides automated metrics (keyword hit/coverage, negative detection)
and LLM-as-Judge scoring (correctness, faithfulness, completeness).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

EVAL_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "experiments" / "eval_questions.yaml"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EvalQuestion:
    """A single evaluation question with expected answers."""

    question: str
    category: str
    difficulty: str
    expected_keywords: list[str] = field(default_factory=list)
    expected_answer: str = ""
    check: str = ""
    hops: list[str] = field(default_factory=list)
    aggregation_type: str = ""
    inference_type: str = ""


@dataclass
class QuestionResult:
    """Evaluation result for a single question."""

    question: str
    category: str
    difficulty: str
    response: str
    latency_seconds: float
    status: str
    # Automated metrics
    keyword_hit: bool = False
    keyword_coverage: float = 0.0
    negative_pass: bool | None = None
    # LLM-as-Judge scores (1-5)
    correctness: float = 0.0
    faithfulness: float = 0.0
    completeness: float = 0.0


@dataclass
class CategoryScore:
    """Aggregated scores for a category."""

    category: str
    count: int = 0
    keyword_hit_rate: float = 0.0
    keyword_coverage: float = 0.0
    negative_detection_rate: float | None = None
    avg_correctness: float = 0.0
    avg_faithfulness: float = 0.0
    avg_completeness: float = 0.0
    avg_latency: float = 0.0


@dataclass
class EvalReport:
    """Full evaluation report."""

    # Overall automated metrics
    keyword_hit_rate: float = 0.0
    keyword_coverage: float = 0.0
    negative_detection_rate: float = 0.0
    # Overall LLM-as-Judge
    avg_correctness: float = 0.0
    avg_faithfulness: float = 0.0
    avg_completeness: float = 0.0
    # Overall
    overall_score: float = 0.0
    avg_latency: float = 0.0
    total_questions: int = 0
    # Breakdown
    by_category: dict[str, CategoryScore] = field(default_factory=dict)
    details: list[QuestionResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Load eval questions
# ---------------------------------------------------------------------------

def load_eval_questions(path: Path | None = None) -> list[EvalQuestion]:
    """Load evaluation questions from YAML file.

    Supports the flat-category YAML layout used in eval_questions.yaml::

        single_hop:
          - id: SH-01
            query: "..."
            expected_keywords: [...]
            difficulty: easy
        multi_hop_2:
          - ...
    """
    path = path or EVAL_QUESTIONS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Eval questions not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    questions: list[EvalQuestion] = []

    # Each top-level key is a category name mapping to a list of questions
    for cat_name, items in raw.items():
        if not isinstance(items, list):
            continue
        for q in items:
            if not isinstance(q, dict):
                continue
            question_text = q.get("query", q.get("question", ""))
            if not question_text:
                continue
            questions.append(EvalQuestion(
                question=question_text,
                category=cat_name,
                difficulty=q.get("difficulty", "medium"),
                expected_keywords=q.get("expected_keywords", []),
                expected_answer=q.get("expected_answer", ""),
                check=q.get("check", ""),
                hops=q.get("hops", []),
                aggregation_type=q.get("aggregation_type", ""),
                inference_type=q.get("inference_type", ""),
            ))

    return questions


# ---------------------------------------------------------------------------
# Automated metrics
# ---------------------------------------------------------------------------

def evaluate_keyword_hit(response: str, expected_keywords: list[str]) -> bool:
    """Check if at least one expected keyword appears in the response."""
    if not expected_keywords:
        return False
    resp_lower = response.lower()
    return any(kw.lower() in resp_lower for kw in expected_keywords)


def evaluate_keyword_coverage(response: str, expected_keywords: list[str]) -> float:
    """Return fraction of expected keywords found in the response."""
    if not expected_keywords:
        return 0.0
    resp_lower = response.lower()
    matched = sum(1 for kw in expected_keywords if kw.lower() in resp_lower)
    return matched / len(expected_keywords)


# Patterns for negative question detection
_REFUSAL_PATTERNS = [
    r"없", r"찾을\s*수\s*없", r"존재하지\s*않", r"확인할\s*수\s*없",
    r"확인\s*불가", r"제공되지\s*않", r"포함되어\s*있지\s*않",
    r"해당.*없", r"정보가\s*없",
]

_CORRECTION_PATTERNS_MIRAE = [r"미래에셋"]

_DISCLAIMER_PATTERNS = [
    r"보장.*(?:않|없|아니)",
    r"(?:않|없|아니).*보장",
    r"원금.*(?:손실|위험)",
]


def evaluate_negative(response: str, check_type: str) -> bool:
    """Evaluate negative/hallucination detection questions."""
    if check_type == "should_not_hallucinate":
        return any(re.search(p, response) for p in _REFUSAL_PATTERNS)

    if check_type == "should_correct_premise":
        return any(re.search(p, response) for p in _CORRECTION_PATTERNS_MIRAE)

    if check_type == "should_not_fabricate_data":
        return any(re.search(p, response) for p in _REFUSAL_PATTERNS)

    if check_type == "should_provide_accurate_disclaimer":
        return any(re.search(p, response) for p in _DISCLAIMER_PATTERNS)

    # Unknown check type — treat as pass if any refusal pattern matched
    return any(re.search(p, response) for p in _REFUSAL_PATTERNS)


# ---------------------------------------------------------------------------
# LLM-as-Judge
# ---------------------------------------------------------------------------

_JUDGE_PROMPT_TEMPLATE = """\
당신은 GraphRAG 시스템의 응답 품질을 평가하는 전문 평가자입니다.

## 평가 대상
- **질문**: {question}
- **기대 키워드**: {expected_keywords}
- **기대 답변**: {expected_answer}
- **시스템 응답**: {response}

## 평가 기준 (각 항목 1~5점)

### Correctness (정확성)
- 5: 완전히 정확하고 충분한 정보 제공
- 4: 대부분 정확, 사소한 누락
- 3: 부분적으로 정확, 주요 정보 일부 누락
- 2: 정확한 내용이 일부만 포함
- 1: 부정확하거나 관련 없는 응답

### Faithfulness (충실성)
- 5: 모든 내용이 소스에 근거하며 hallucination 없음
- 4: 대부분 소스 기반, 극소수 불확실한 부분
- 3: 일부 내용의 근거가 불분명
- 2: 근거 없는 주장이 상당수 포함
- 1: 대부분 hallucination

### Completeness (완전성)
- 5: 질문의 모든 요구사항을 완전히 다룸
- 4: 대부분 다루고 사소한 세부사항만 누락
- 3: 주요 부분만 다루고 세부사항 누락
- 2: 일부만 답변
- 1: 거의 답변하지 못함

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.
{{"correctness": <1-5>, "faithfulness": <1-5>, "completeness": <1-5>}}
"""


def evaluate_with_llm(
    question: str,
    response: str,
    expected_keywords: list[str],
    expected_answer: str,
    model_id: str | None = None,
) -> dict[str, float]:
    """Use LLM-as-Judge to score a response.

    Returns dict with correctness, faithfulness, completeness (each 1-5).
    """
    import boto3
    from tiger_etf.config import settings

    model_id = model_id or settings.graphrag_response_llm

    prompt = _JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        expected_keywords=", ".join(expected_keywords) if expected_keywords else "(없음)",
        expected_answer=expected_answer or "(없음)",
        response=response[:3000],
    )

    client = boto3.client("bedrock-runtime", region_name=settings.graphrag_aws_region)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    })

    try:
        resp = client.invoke_model(modelId=model_id, body=body)
        result_body = json.loads(resp["body"].read())
        text = result_body["content"][0]["text"].strip()

        # Extract JSON from response
        match = re.search(r"\{[^}]+\}", text)
        if match:
            scores = json.loads(match.group())
            return {
                "correctness": float(scores.get("correctness", 0)),
                "faithfulness": float(scores.get("faithfulness", 0)),
                "completeness": float(scores.get("completeness", 0)),
            }
    except Exception as e:
        logger.warning("LLM judge failed: %s", e)

    return {"correctness": 0.0, "faithfulness": 0.0, "completeness": 0.0}


# ---------------------------------------------------------------------------
# Run full evaluation
# ---------------------------------------------------------------------------

def run_evaluation(
    eval_results: list[dict[str, Any]],
    eval_questions: list[EvalQuestion],
    use_llm_judge: bool = True,
    judge_model_id: str | None = None,
) -> EvalReport:
    """Run evaluation on query results against expected answers.

    Args:
        eval_results: List of dicts with keys: query, response, latency_seconds, status
        eval_questions: Parsed EvalQuestion list from YAML
        use_llm_judge: Whether to run LLM-as-Judge scoring
        judge_model_id: Optional Bedrock model ID for judge LLM

    Returns:
        EvalReport with all scores
    """
    # Build question lookup by question text
    q_lookup: dict[str, EvalQuestion] = {q.question: q for q in eval_questions}

    details: list[QuestionResult] = []

    for r in eval_results:
        query_text = r["query"]
        response = r.get("response", "")
        eq = q_lookup.get(query_text)

        if eq is None:
            # Question not in eval set — skip evaluation
            details.append(QuestionResult(
                question=query_text,
                category="unknown",
                difficulty="unknown",
                response=response,
                latency_seconds=r.get("latency_seconds", 0),
                status=r.get("status", "unknown"),
            ))
            continue

        qr = QuestionResult(
            question=query_text,
            category=eq.category,
            difficulty=eq.difficulty,
            response=response,
            latency_seconds=r.get("latency_seconds", 0),
            status=r.get("status", "unknown"),
        )

        if r.get("status") != "success":
            details.append(qr)
            continue

        # Automated metrics
        if eq.category == "negative":
            qr.negative_pass = evaluate_negative(response, eq.check)
        else:
            qr.keyword_hit = evaluate_keyword_hit(response, eq.expected_keywords)
            qr.keyword_coverage = evaluate_keyword_coverage(response, eq.expected_keywords)

        # LLM-as-Judge
        if use_llm_judge:
            logger.info("LLM judge scoring: %s", query_text[:50])
            scores = evaluate_with_llm(
                question=query_text,
                response=response,
                expected_keywords=eq.expected_keywords,
                expected_answer=eq.expected_answer,
                model_id=judge_model_id,
            )
            qr.correctness = scores["correctness"]
            qr.faithfulness = scores["faithfulness"]
            qr.completeness = scores["completeness"]

        details.append(qr)

    return _aggregate_report(details)


def _aggregate_report(details: list[QuestionResult]) -> EvalReport:
    """Aggregate individual question results into an EvalReport."""
    report = EvalReport(details=details, total_questions=len(details))

    # Group by category
    by_cat: dict[str, list[QuestionResult]] = {}
    for d in details:
        by_cat.setdefault(d.category, []).append(d)

    # Non-negative questions (for keyword metrics)
    non_neg = [d for d in details if d.category != "negative" and d.status == "success"]
    neg = [d for d in details if d.category == "negative" and d.status == "success"]
    successful = [d for d in details if d.status == "success"]

    # Overall keyword metrics
    if non_neg:
        report.keyword_hit_rate = sum(1 for d in non_neg if d.keyword_hit) / len(non_neg)
        report.keyword_coverage = sum(d.keyword_coverage for d in non_neg) / len(non_neg)

    # Negative detection rate
    if neg:
        report.negative_detection_rate = sum(
            1 for d in neg if d.negative_pass
        ) / len(neg)

    # LLM-as-Judge averages
    judged = [d for d in successful if d.correctness > 0]
    if judged:
        report.avg_correctness = sum(d.correctness for d in judged) / len(judged)
        report.avg_faithfulness = sum(d.faithfulness for d in judged) / len(judged)
        report.avg_completeness = sum(d.completeness for d in judged) / len(judged)

    # Overall score (weighted)
    report.overall_score = (
        report.keyword_hit_rate * 0.15
        + report.keyword_coverage * 0.10
        + report.negative_detection_rate * 0.15
        + (report.avg_correctness / 5) * 0.25
        + (report.avg_faithfulness / 5) * 0.20
        + (report.avg_completeness / 5) * 0.15
    )

    # Latency
    if successful:
        report.avg_latency = sum(d.latency_seconds for d in successful) / len(successful)

    # Per-category scores
    for cat_name, cat_items in by_cat.items():
        cs = CategoryScore(category=cat_name, count=len(cat_items))
        cat_success = [d for d in cat_items if d.status == "success"]

        if cat_name == "negative":
            if cat_success:
                cs.negative_detection_rate = sum(
                    1 for d in cat_success if d.negative_pass
                ) / len(cat_success)
        else:
            if cat_success:
                cs.keyword_hit_rate = sum(
                    1 for d in cat_success if d.keyword_hit
                ) / len(cat_success)
                cs.keyword_coverage = sum(
                    d.keyword_coverage for d in cat_success
                ) / len(cat_success)

        cat_judged = [d for d in cat_success if d.correctness > 0]
        if cat_judged:
            cs.avg_correctness = sum(d.correctness for d in cat_judged) / len(cat_judged)
            cs.avg_faithfulness = sum(d.faithfulness for d in cat_judged) / len(cat_judged)
            cs.avg_completeness = sum(d.completeness for d in cat_judged) / len(cat_judged)

        if cat_success:
            cs.avg_latency = sum(d.latency_seconds for d in cat_success) / len(cat_success)

        report.by_category[cat_name] = cs

    return report


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_eval_report(report: EvalReport) -> str:
    """Format EvalReport as a Rich-renderable string table."""
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)

    # Overall summary
    summary = Table(title="Evaluation Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Score", justify="right", style="green")
    summary.add_row("Overall Score", f"{report.overall_score:.3f}")
    summary.add_row("Keyword Hit Rate", f"{report.keyword_hit_rate:.1%}")
    summary.add_row("Keyword Coverage", f"{report.keyword_coverage:.1%}")
    summary.add_row("Negative Detection", f"{report.negative_detection_rate:.1%}")
    summary.add_row("Avg Correctness", f"{report.avg_correctness:.2f}/5")
    summary.add_row("Avg Faithfulness", f"{report.avg_faithfulness:.2f}/5")
    summary.add_row("Avg Completeness", f"{report.avg_completeness:.2f}/5")
    summary.add_row("Avg Latency", f"{report.avg_latency:.2f}s")
    summary.add_row("Total Questions", str(report.total_questions))
    console.print(summary)

    # Per-category breakdown
    cat_table = Table(title="Score by Category")
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Count", justify="right")
    cat_table.add_column("KW Hit", justify="right")
    cat_table.add_column("KW Cov", justify="right")
    cat_table.add_column("Neg Det", justify="right")
    cat_table.add_column("Correct", justify="right")
    cat_table.add_column("Faithful", justify="right")
    cat_table.add_column("Complete", justify="right")
    cat_table.add_column("Latency", justify="right")

    for cat_name in sorted(report.by_category):
        cs = report.by_category[cat_name]
        cat_table.add_row(
            cs.category,
            str(cs.count),
            f"{cs.keyword_hit_rate:.0%}" if cs.category != "negative" else "-",
            f"{cs.keyword_coverage:.0%}" if cs.category != "negative" else "-",
            f"{cs.negative_detection_rate:.0%}" if cs.negative_detection_rate is not None else "-",
            f"{cs.avg_correctness:.1f}" if cs.avg_correctness > 0 else "-",
            f"{cs.avg_faithfulness:.1f}" if cs.avg_faithfulness > 0 else "-",
            f"{cs.avg_completeness:.1f}" if cs.avg_completeness > 0 else "-",
            f"{cs.avg_latency:.1f}s",
        )
    console.print(cat_table)

    return console.export_text()


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    """Convert EvalReport to a JSON-serializable dict for experiment results."""
    return {
        "keyword_hit_rate": round(report.keyword_hit_rate, 4),
        "keyword_coverage": round(report.keyword_coverage, 4),
        "negative_detection_rate": round(report.negative_detection_rate, 4),
        "llm_judge": {
            "avg_correctness": round(report.avg_correctness, 2),
            "avg_faithfulness": round(report.avg_faithfulness, 2),
            "avg_completeness": round(report.avg_completeness, 2),
        },
        "overall_score": round(report.overall_score, 4),
        "avg_latency": round(report.avg_latency, 2),
        "total_questions": report.total_questions,
        "by_category": {
            name: {
                "count": cs.count,
                "keyword_hit_rate": round(cs.keyword_hit_rate, 4),
                "keyword_coverage": round(cs.keyword_coverage, 4),
                "negative_detection_rate": (
                    round(cs.negative_detection_rate, 4)
                    if cs.negative_detection_rate is not None
                    else None
                ),
                "avg_correctness": round(cs.avg_correctness, 2),
                "avg_faithfulness": round(cs.avg_faithfulness, 2),
                "avg_completeness": round(cs.avg_completeness, 2),
                "avg_latency": round(cs.avg_latency, 2),
            }
            for name, cs in report.by_category.items()
        },
        "details": [
            {
                "question": d.question,
                "category": d.category,
                "difficulty": d.difficulty,
                "status": d.status,
                "latency_seconds": d.latency_seconds,
                "keyword_hit": d.keyword_hit,
                "keyword_coverage": round(d.keyword_coverage, 4),
                "negative_pass": d.negative_pass,
                "correctness": d.correctness,
                "faithfulness": d.faithfulness,
                "completeness": d.completeness,
            }
            for d in report.details
        ],
    }
