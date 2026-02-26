# GraphRAG 평가(Evaluation) 프레임워크 구현 계획

## 1. 현황 분석

### 현재 상태
- `experiments/eval_questions.yaml`: 6개 카테고리, 총 50문항의 평가 질문셋 준비 완료
- `experiment.py`: 실험 실행 프레임워크 존재하나 **품질 평가 기능 없음**
  - 현재는 query 실행 → response/latency 기록만 수행
  - `run_eval_queries()`가 config의 `eval_queries` (5개 간단 질문)만 사용
- `eval_questions.yaml`의 `expected_keywords`, `expected_answer`, `check` 필드가 활용되지 않고 있음

### 평가 질문셋 구조
| 카테고리 | 문항수 | 난이도 | 특징 |
|---------|--------|--------|------|
| single_hop | 10 | easy | `expected_keywords` 포함 |
| multi_hop_2 | 10 | medium | `expected_keywords` + `hops` |
| multi_hop_3 | 10 | hard | `expected_keywords` + `hops` |
| aggregation | 8 | medium/hard | `expected_keywords` + `aggregation_type` |
| inference | 7 | hard | `expected_keywords` + `inference_type` |
| negative | 5 | easy/medium | `expected_answer` + `check` 타입 |

---

## 2. 평가 지표 설계

### 2.1 자동 평가 지표 (Automated Metrics)

#### (A) Keyword Hit Rate (키워드 적중률)
- **정의**: 응답에 `expected_keywords` 중 하나 이상 포함되었는지 여부
- **적용 대상**: single_hop, multi_hop_2, multi_hop_3, aggregation, inference (총 45문항)
- **계산**: `hit_count / total_count` (카테고리별 + 전체)
- **장점**: 간단, 빠름, 재현성 100%
- **한계**: 키워드가 있어도 정답이 아닐 수 있음

#### (B) Keyword Coverage (키워드 커버리지)
- **정의**: `expected_keywords` 중 몇 개가 응답에 포함되었는지 비율
- **계산**: `matched_keywords / total_keywords`
- **적용 대상**: 위와 동일
- **장점**: Hit Rate보다 세밀한 평가

#### (C) Negative Detection Rate (부정 질문 탐지율)
- **정의**: negative 카테고리 질문에 대해 시스템이 올바르게 거부/교정했는지
- **적용 대상**: negative 5문항
- **검증 로직** (check 타입별):
  - `should_not_hallucinate`: 응답에 "없", "찾을 수 없", "존재하지 않" 등 포함
  - `should_correct_premise`: "미래에셋" 포함 (전제 교정)
  - `should_not_fabricate_data`: "없", "확인 불가" 등 포함
  - `should_provide_accurate_disclaimer`: "보장" + "아니" 또는 "없" 포함

#### (D) Response Latency (응답 지연시간)
- **이미 구현됨**: 쿼리별 latency_seconds + 평균
- **추가**: 카테고리별 평균 latency 집계

### 2.2 LLM-as-Judge 평가 지표

외부 LLM(Claude)을 평가자로 활용하여 응답 품질을 1-5점 척도로 채점.

#### (E) Correctness (정확성)
- **정의**: 응답이 질문에 대해 사실적으로 정확한 정보를 제공하는지
- **프롬프트**: 질문 + expected_keywords/expected_answer + 실제 응답 → 1-5점
- **채점 기준**:
  - 5: 완전히 정확하고 충분한 정보 제공
  - 4: 대부분 정확, 사소한 누락
  - 3: 부분적으로 정확, 주요 정보 일부 누락
  - 2: 정확한 내용이 일부만 포함
  - 1: 부정확하거나 관련 없는 응답

#### (F) Faithfulness (충실성)
- **정의**: 응답이 소스 문서에 근거한 정보만 제공하는지 (hallucination 없는지)
- **프롬프트**: 응답 내용이 [Source:] 인용과 일치하는지, 근거 없는 주장이 있는지
- **채점 기준**:
  - 5: 모든 내용이 소스에 근거
  - 3: 일부 내용의 근거가 불분명
  - 1: 근거 없는 주장이 다수 포함

#### (G) Completeness (완전성)
- **정의**: 질문이 요구하는 모든 측면에 대해 답변했는지
- **프롬프트**: 질문의 각 요구사항 대비 응답 커버리지
- **채점 기준**:
  - 5: 모든 요구사항을 완전히 다룸
  - 3: 주요 부분만 다루고 세부사항 누락
  - 1: 거의 답변하지 못함

### 2.3 종합 점수

```
overall_score = (
    keyword_hit_rate * 0.15 +
    keyword_coverage * 0.10 +
    negative_detection_rate * 0.15 +
    avg_correctness / 5 * 0.25 +
    avg_faithfulness / 5 * 0.20 +
    avg_completeness / 5 * 0.15
)
```

---

## 3. 구현 계획

### 3.1 파일 구조

```
src/tiger_etf/graphrag/
├── evaluator.py          # [NEW] 평가 엔진 (핵심)
├── experiment.py          # [MODIFY] eval_questions.yaml 연동 + evaluator 호출
├── query.py               # [NO CHANGE]
├── indexer.py             # [NO CHANGE]
└── loader.py              # [NO CHANGE]

experiments/
├── eval_questions.yaml    # [NO CHANGE] 기존 질문셋 활용
├── configs/*.yaml         # [MODIFY] eval_queries 필드 제거 (eval_questions.yaml로 통합)
└── results/*.json         # 결과에 evaluation 점수 추가
```

### 3.2 `evaluator.py` 구현 내용

```python
# 주요 클래스/함수:

def load_eval_questions(path: Path) -> list[EvalQuestion]
    """eval_questions.yaml 로드 → 카테고리 플랫하게 풀어서 리스트 반환"""

def evaluate_keyword_hit(response: str, expected_keywords: list[str]) -> bool
    """expected_keywords 중 하나라도 응답에 포함되면 True"""

def evaluate_keyword_coverage(response: str, expected_keywords: list[str]) -> float
    """매칭된 키워드 비율 반환 (0.0 ~ 1.0)"""

def evaluate_negative(response: str, check_type: str) -> bool
    """negative 카테고리 전용: check 타입별 규칙 기반 검증"""

async def evaluate_with_llm(question: str, response: str, expected: dict, model: str) -> dict
    """LLM-as-Judge: correctness, faithfulness, completeness 각각 1-5점 반환"""

def run_evaluation(eval_results: list[dict], eval_questions: list[EvalQuestion], use_llm_judge: bool = True) -> EvalReport
    """전체 평가 실행 → 카테고리별 + 전체 점수 산출"""

def format_eval_report(report: EvalReport) -> str
    """Rich 테이블로 평가 결과 포맷팅"""
```

### 3.3 `experiment.py` 수정 사항

1. `run_eval_queries()` → eval_questions.yaml 전체 50문항 사용하도록 변경
2. 쿼리 실행 후 `evaluator.run_evaluation()` 호출
3. 결과 JSON에 `evaluation` 섹션 추가:
   ```json
   {
     "evaluation": {
       "keyword_hit_rate": 0.78,
       "keyword_coverage": 0.62,
       "negative_detection_rate": 0.80,
       "llm_judge": {
         "avg_correctness": 3.8,
         "avg_faithfulness": 4.2,
         "avg_completeness": 3.5
       },
       "overall_score": 0.72,
       "by_category": { ... },
       "details": [ ... ]
     }
   }
   ```
4. `compare` 명령에 evaluation 점수 비교 컬럼 추가

### 3.4 CLI 확장

```bash
# 기존 실험 실행 (인덱싱 + 평가 포함)
tiger-etf experiment run baseline_claude37_cohere

# 인덱싱 스킵하고 평가만 재실행
tiger-etf experiment run baseline_claude37_cohere --skip-indexing

# LLM Judge 비활성화 (키워드 기반 평가만)
tiger-etf experiment run baseline_claude37_cohere --skip-indexing --no-llm-judge

# 실험 결과 비교 (evaluation 점수 포함)
tiger-etf experiment compare
```

### 3.5 LLM-as-Judge 구현 방식

- Amazon Bedrock의 Claude 모델을 `boto3` (`bedrock-runtime`)로 직접 호출
- 이미 프로젝트에서 boto3를 사용 중이므로 추가 의존성 없음
- 평가용 LLM은 config.yaml의 `response_llm`을 재사용 (또는 별도 `judge_llm` 설정 가능)
- 비용 절감을 위해 `--no-llm-judge` 옵션 제공

### 3.6 테스트

```
tests/
└── test_evaluator.py      # [NEW]
    - test_keyword_hit / test_keyword_coverage
    - test_negative_detection (check 타입별)
    - test_load_eval_questions
    - test_eval_report_aggregation
```

---

## 4. 구현 순서

1. **`evaluator.py`** 생성 — 평가 로직 전체
2. **`experiment.py`** 수정 — eval_questions.yaml 연동 + evaluator 호출
3. **CLI 수정** (`cli.py`) — `--no-llm-judge` 옵션 추가
4. **`test_evaluator.py`** 작성 — 단위 테스트
5. 테스트 실행 및 통과 확인

---

## 5. 의존성

- **추가 패키지 없음**: boto3 (이미 있음), yaml (이미 있음)
- LLM-as-Judge는 Bedrock `invoke_model` API 사용
