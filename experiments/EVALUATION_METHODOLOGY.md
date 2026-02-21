# GraphRAG 체계적 성능 평가 방법론

## 1. 평가 프레임워크 개요

### 1.1 평가 축 (Evaluation Dimensions)

| 축 | 측정 대상 | 도구 |
|---|---------|-----|
| **Retrieval Quality** | 관련 컨텍스트를 얼마나 잘 가져오는가 | RAGAS context metrics |
| **Generation Quality** | 응답이 얼마나 정확하고 충실한가 | RAGAS answer metrics |
| **Graph Quality** | 추출된 엔티티/관계가 얼마나 정확한가 | 수동 샘플링 + F1 |
| **Operational** | 비용, 지연시간, 처리량 | 자체 계측 |

### 1.2 실험 변수 (Independent Variables)

```
실험 매트릭스:
├── Extraction LLM: Claude 3.7 Sonnet / Claude 4 Sonnet / Claude 4.5 Sonnet / Haiku 4.5
├── Embedding Model: Cohere Multilingual v3 / Amazon Titan Text v2
├── Ontology: 현재 17타입 / 축소 10타입 / 확장 25타입
├── Chunk Size: 256 / 512 / 1024 chars
└── PDF Limit: 50 / 100 / 전체(887)
```

---

## 2. RAGAS 기반 자동 평가

### 2.1 RAGAS란?

RAGAS(Retrieval Augmented Generation Assessment)는 RAG 파이프라인을 평가하는 프레임워크.
각 질문에 대해 `question`, `answer`, `contexts`, `ground_truth`를 입력하면 여러 메트릭을 자동 산출.

### 2.2 적용할 RAGAS 메트릭

| 메트릭 | 설명 | 범위 |
|-------|------|-----|
| **Faithfulness** | 응답이 검색된 컨텍스트에 얼마나 충실한가 (hallucination 탐지) | 0-1 |
| **Answer Relevancy** | 응답이 질문에 얼마나 관련 있는가 | 0-1 |
| **Context Precision** | 검색된 컨텍스트 중 관련 있는 것의 비율 | 0-1 |
| **Context Recall** | ground truth를 답변하기 위해 필요한 컨텍스트를 얼마나 가져왔는가 | 0-1 |
| **Answer Correctness** | 응답이 ground truth와 얼마나 일치하는가 | 0-1 |

### 2.3 구현 방법

```python
# pip install ragas langchain-aws

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness,
)
from datasets import Dataset

# 1) 질문별로 GraphRAG 시스템에서 응답 + 컨텍스트 수집
eval_data = {
    "question": [],       # 질문
    "answer": [],         # GraphRAG 응답
    "contexts": [],       # 검색된 컨텍스트 (list of strings)
    "ground_truth": [],   # 사람이 작성한 정답
}

for q in eval_questions:
    response, contexts = query_with_contexts(q["query"])
    eval_data["question"].append(q["query"])
    eval_data["answer"].append(response)
    eval_data["contexts"].append(contexts)
    eval_data["ground_truth"].append(q["ground_truth"])

dataset = Dataset.from_dict(eval_data)

# 2) 평가 실행
results = evaluate(
    dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness,
    ],
    llm=bedrock_llm,        # 평가용 LLM (실험 LLM과 다른 모델 권장)
    embeddings=embeddings,
)

print(results)  # DataFrame with per-question scores
```

### 2.4 컨텍스트 수집을 위한 코드 수정

현재 `query.py`는 최종 응답만 반환. RAGAS 평가를 위해 검색된 컨텍스트도 반환하도록 수정 필요:

```python
# query.py에 추가
def query_with_contexts(question: str) -> tuple[str, list[str]]:
    """응답과 검색 컨텍스트를 함께 반환."""
    engine = get_query_engine()
    response = engine.query(question)

    # source_nodes에서 컨텍스트 텍스트 추출
    contexts = []
    if hasattr(response, 'source_nodes'):
        for node in response.source_nodes:
            contexts.append(node.node.get_content())

    return str(response), contexts
```

---

## 3. Ground Truth 생성 전략

### 3.1 Semi-Automatic 접근법

완전한 수동 작성은 비효율적. 다음 혼합 방식 권장:

1. **RDB 기반 자동 생성 (Single-Hop, Aggregation)**
   - DB 쿼리로 정확한 정답 추출 가능
   - 예: "S&P500 ETF의 총보수" → `SELECT total_expense_ratio FROM etf_products WHERE ...`

2. **PDF 기반 수동 확인 (Multi-Hop, Inference)**
   - PDF 투자설명서에서 관련 구절 직접 발췌
   - 전문가가 검증

3. **LLM-assisted + Human-in-the-loop (Negative)**
   - LLM이 초안 작성 → 사람이 검증/수정

### 3.2 Ground Truth 스키마

```yaml
- id: SH-01
  query: "TIGER 미국S&P500 ETF의 벤치마크 지수는 무엇인가요?"
  ground_truth: "TIGER 미국S&P500 ETF의 벤치마크 지수는 S&P 500 Total Return Index입니다."
  source: "etf_products.benchmark_index (RDB)"
  verified_by: "human"
```

---

## 4. 그래프 품질 평가 (Graph Quality)

RAGAS는 최종 응답 품질만 측정. 그래프 자체의 품질도 별도로 평가해야 함.

### 4.1 Entity Extraction F1

```
1. 50개 PDF에서 랜덤 20개 선택
2. 각 PDF에서 수동으로 엔티티 10-20개 라벨링 (gold standard)
3. 시스템이 추출한 엔티티와 비교
4. Precision / Recall / F1 산출
```

### 4.2 Relationship Extraction Accuracy

```
1. 추출된 관계 중 랜덤 100개 샘플링
2. 사람이 올바른지 판별 (correct / incorrect / partially correct)
3. Accuracy = correct / total
```

### 4.3 Graph Completeness

```
Neo4j Cypher 쿼리로 측정:

-- 고립 노드 비율 (연결 없는 엔티티)
MATCH (e:__Entity__) WHERE NOT (e)--() RETURN count(e)

-- 엔티티당 평균 관계 수
MATCH (e:__Entity__)-[r]-() RETURN avg(count(r))

-- 소스 문서 커버리지 (엔티티가 추출된 소스 비율)
MATCH (s:__Source__)
OPTIONAL MATCH (s)<-[:__EXTRACTED_FROM__]-(:__Chunk__)-[:__MENTIONED_IN__]-(:__Entity__)
RETURN count(DISTINCT s) as covered, count(s) as total
```

---

## 5. 실험 실행 프로토콜

### 5.1 단일 실험 수행 절차

```
1. Clear stores (Neo4j + pgvector)
2. Index documents (측정: 시간, 비용)
3. Collect graph metrics (노드/엣지 분포)
4. Graph quality sampling (F1 on subset)
5. Run eval queries → 응답 + 컨텍스트 수집
6. RAGAS 평가 실행
7. 결과 저장 (JSON)
```

### 5.2 비교 매트릭스

| 실험 | Extraction LLM | Embedding | Ontology | RAGAS Avg | Latency | Cost |
|-----|---------------|-----------|----------|-----------|---------|------|
| baseline | Claude 3.7 | Cohere v3 | 17types | ? | 11.95s | $X |
| exp01 | Claude 4.5 | Cohere v3 | 17types | ? | ? | $X |
| exp02 | Claude 4 | Cohere v3 | 17types | ? | ? | $X |
| exp03 | Claude 3.7 | Titan v2 | 17types | ? | ? | $X |
| exp04 | Haiku 4.5 | Cohere v3 | 17types | ? | ? | $X |

### 5.3 통계적 유의성

- 각 실험을 최소 3회 반복 실행 (LLM 비결정성 고려)
- 평균 ± 표준편차 보고
- 실험 간 비교 시 paired t-test 또는 Wilcoxon signed-rank test

---

## 6. 비용 추적

### 6.1 측정 항목

```yaml
cost_tracking:
  indexing:
    llm_input_tokens: 0     # extraction LLM 입력
    llm_output_tokens: 0    # extraction LLM 출력
    embedding_requests: 0   # embedding API 호출 횟수
  querying:
    llm_input_tokens: 0     # response LLM 입력 (per query)
    llm_output_tokens: 0    # response LLM 출력 (per query)
    embedding_requests: 0   # vector search 호출 (per query)
```

### 6.2 비용 대비 성능 (Cost-Performance Ratio)

```
CPR = RAGAS_avg_score / total_cost_usd
```

Haiku 4.5 같은 저비용 모델이 비용 대비 더 효율적일 수 있음.

---

## 7. 카테고리별 분석 가이드

질문셋이 카테고리별로 구분되어 있으므로, 실험 결과를 다음과 같이 분석:

| 카테고리 | 평가 포인트 |
|---------|-----------|
| **Single-Hop** | 기본 검색 정확도. 여기서 낮으면 extraction 자체에 문제. |
| **Multi-Hop 2** | 2단계 관계 추론. Graph traversal 효과 측정. |
| **Multi-Hop 3** | 3단계 관계 추론. GraphRAG vs naive RAG 차이가 가장 큰 영역. |
| **Aggregation** | 전체 그래프 활용도. 커버리지와 직결. |
| **Inference** | LLM 추론 능력. response LLM 변경 시 차이 큰 영역. |
| **Negative** | Hallucination 방지. Faithfulness 메트릭과 직결. |

---

## 8. 추천 도구 스택

| 용도 | 도구 | 비고 |
|-----|------|-----|
| RAG 평가 | [RAGAS](https://github.com/explodinggradients/ragas) | 핵심 프레임워크 |
| 데이터셋 관리 | HuggingFace Datasets | RAGAS 입력 포맷 |
| LLM 평가자 | Amazon Bedrock (Claude) | RAGAS judge LLM |
| 실험 추적 | MLflow 또는 Weights & Biases | 실험 비교/시각화 |
| 통계 분석 | scipy.stats | 유의성 검정 |
| 시각화 | matplotlib / seaborn | 결과 차트 |

---

## 9. 구현 우선순위

1. **Ground truth 작성** - eval_questions.yaml의 50문항에 대해 정답 작성
2. **query_with_contexts 구현** - 컨텍스트 반환 기능 추가
3. **RAGAS 파이프라인 구축** - evaluate() 실행 스크립트
4. **baseline 재측정** - 50문항 + RAGAS 메트릭으로 baseline 확보
5. **실험 순차 실행** - exp01~04 + RAGAS 비교
6. **그래프 품질 평가** - Entity F1 샘플링 (1회)
