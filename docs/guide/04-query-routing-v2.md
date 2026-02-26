# 5. Query Routing: Intent 기반 검색 채널 선택

## 5.1 문제: 모든 질문에 동일한 검색 경로?

현재 TIGER ETF GraphRAG 시스템은 모든 질문을 **Traversal-Based Search** 한 가지 경로로 처리합니다.

```python
# 현재 구현: 모든 질문 → 동일한 GraphRAG traversal
def query(question: str) -> str:
    engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, vector_store
    )
    response = engine.query(question)
    return str(response)
```

하지만 실제 고객 질문은 **성격이 매우 다릅니다**:

| 질문 유형 | 예시 | 최적 데이터 소스 |
|----------|------|-----------------|
| 수치/속성 조회 | "TIGER 미국S&P500의 총보수는?" | **RDB** (Source of Truth) |
| 조건 기반 목록 | "채권형 ETF 중 보수가 낮은 순으로" | **RDB** (SQL 필터/정렬) |
| 관계 탐색 | "TIGER 미국S&P500의 수탁회사는?" | **Graph DB** (관계 순회) |
| 서술형/위험 분석 | "TIGER 미국S&P500의 투자위험은?" | **Vector + Graph** (비정형 문서) |
| 복합 질문 | "S&P500을 추적하는 ETF 중 보수가 가장 낮은 상품의 보유종목은?" | **Graph + RDB** (다단계) |

> **핵심 인사이트**: 상품의 정형 정보(보수, AUM, 보유종목 비중 등)는 RDB에 **Source of Truth**로 저장되어 있습니다. 이런 질문에 Graph 검색을 하면 PDF에서 추출한 근사치가 반환되어 정확도가 떨어집니다.

---

## 5.2 Query Routing 아키텍처

고객 질문의 **Intent(의도)**를 인식하여 최적의 검색 채널을 선택하는 Agent를 구현합니다.

```
사용자 질문
  │
  ▼
┌──────────────────────────────────────────────┐
│            Intent Classifier (LLM)            │
│    질문 분석 → Intent 분류 + 엔티티 추출        │
└──────────────┬───────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────────┐
    │          │          │              │
    ▼          ▼          ▼              ▼
┌────────┐ ┌────────┐ ┌────────┐  ┌──────────┐
│ATTRIBUTE│ │RELATION│ │  OPEN  │  │MULTI_HOP │
│FILTER   │ │        │ │        │  │COMPARISON│
│AGGREGATE│ │        │ │        │  │          │
└────┬───┘ └────┬───┘ └────┬───┘  └────┬─────┘
     │          │          │           │
     ▼          ▼          ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐  ┌──────────┐
│  RDB   │ │ Graph  │ │Vector +│  │Graph+RDB │
│Text2SQL│ │Traversal│ │ Graph │  │  복합     │
└────┬───┘ └────┬───┘ └────┬───┘  └────┬─────┘
     │          │          │           │
     └──────────┼──────────┼───────────┘
                ▼
     ┌──────────────────────┐
     │  Context Assembly    │
     │  (결과 통합 + 랭킹)    │
     └──────────┬───────────┘
                ▼
     ┌──────────────────────┐
     │  LLM Response Gen    │
     │  (Claude 3.7 Sonnet)  │
     └──────────────────────┘
```

---

## 5.3 Intent 분류 체계

### 8가지 Intent 유형

| Intent | 설명 | 예시 질문 | 검색 채널 |
|--------|------|---------|----------|
| **ATTRIBUTE** | 특정 상품의 수치/속성 조회 | "S&P500 ETF의 총보수는?" | RDB 우선 |
| **FILTER** | 조건 기반 상품 목록 | "해외주식 ETF 중 보수 낮은 순" | RDB + Graph |
| **RELATION** | 엔티티 간 관계 탐색 | "수탁회사는 어디?" | Graph 우선 |
| **MULTI_HOP** | 2~3단계 관계 추론 | "S&P500 ETF 보유종목의 섹터?" | Graph 필수 |
| **COMPARISON** | 복수 엔티티 비교 | "S&P500 vs 나스닥100 차이?" | Graph + RDB |
| **AGGREGATION** | 집계/통계 | "섹터별 ETF 수는?" | RDB 우선 |
| **OPEN** | 서술형/의견/분석 | "투자위험을 설명해줘" | Vector + Graph |
| **NEGATIVE** | 없는 정보 확인 | "비트코인 ETF 있어?" | 전체 검색 → 부재 확인 |

### Intent별 검색 채널 매핑

```
ATTRIBUTE ──────▶ RDB (Text2SQL)
FILTER ─────────▶ RDB (Text2SQL) + Graph (필터 보완)
AGGREGATION ────▶ RDB (Text2SQL)
RELATION ───────▶ Graph (Traversal)
MULTI_HOP ──────▶ Graph (Traversal) + RDB (정형 데이터 보완)
COMPARISON ─────▶ Graph + RDB (복수 엔티티 병렬 조회)
OPEN ───────────▶ Vector Search + Graph Traversal
NEGATIVE ───────▶ 전체 3채널 검색 → 부재 확인
```

---

## 5.4 구현 방안: 3-Channel Hybrid Retrieval

### 채널 1: RDB — Text2SQL (정형 데이터)

> 참조: [아이지에이웍스 AI 에이전트 클레어: Amazon Bedrock 기반 Text-to-SQL 에이전트](https://aws.amazon.com/ko/blogs/tech/iganetworks-text2sql-agent-with-bedrock-1/)

RDB에는 ETF 상품의 **Source of Truth** 정보가 저장되어 있습니다. 수치/속성 질문은 Text2SQL로 정확한 답변을 제공합니다.

**저장된 정형 데이터**:

| 테이블 | 주요 컬럼 | 레코드 수 |
|--------|----------|----------|
| `etf_products` | name_ko, ticker, benchmark_index, total_expense_ratio, aum, nav | 221 |
| `etf_holdings` | holding_name, weight_pct, holding_ticker | ~14,700 |
| `etf_distributions` | amount_per_share, record_date | ~2,200 |
| `etf_performance` | return_1m, return_3m, return_1y | ~221 |

**Text2SQL 구현 방식**:

```python
# intent.py — Intent 분류기
INTENT_CLASSIFICATION_PROMPT = """
사용자의 질문을 분석하여 Intent를 분류하고, 관련 엔티티를 추출하세요.

## Intent 유형
- ATTRIBUTE: 특정 상품의 수치/속성 질문 (보수, AUM, NAV, 상장일 등)
- FILTER: 조건 기반 상품 목록 (카테고리, 정렬 등)
- RELATION: 엔티티 간 관계 탐색 (운용사, 수탁회사, 추적 지수 등)
- MULTI_HOP: 2단계 이상 관계 추론
- COMPARISON: 복수 상품/엔티티 비교
- AGGREGATION: 집계/통계 (개수, 합계, 평균 등)
- OPEN: 서술형/분석 (투자위험, 운용전략 설명 등)
- NEGATIVE: 존재 여부 확인

## 응답 형식 (JSON)
{
  "intent": "ATTRIBUTE",
  "entities": ["TIGER 미국S&P500"],
  "attributes": ["총보수"],
  "confidence": 0.95
}

사용자 질문: {question}
"""

def classify_intent(question: str) -> dict:
    """LLM 기반 Intent 분류."""
    response = bedrock_client.invoke_model(
        modelId="anthropic.claude-3-7-sonnet-...",
        body=json.dumps({
            "messages": [{"role": "user",
                          "content": INTENT_CLASSIFICATION_PROMPT.format(question=question)}],
            "max_tokens": 256,
        })
    )
    return json.loads(response["body"].read())
```

```python
# rdb_query.py — Text2SQL 채널

# 방법 1: 템플릿 기반 SQL 매핑 (안전, 빠름)
QUERY_TEMPLATES = {
    "holdings": """
        SELECT h.holding_name, h.weight_pct
        FROM etf_holdings h
        JOIN etf_products p ON h.ksd_fund_code = p.ksd_fund_code
        WHERE p.name_ko LIKE :product_name
        ORDER BY h.weight_pct DESC LIMIT 20
    """,
    "fee_comparison": """
        SELECT name_ko, ticker, total_expense_ratio
        FROM etf_products
        WHERE category_l1 = :category
        ORDER BY total_expense_ratio ASC
    """,
    "aum_ranking": """
        SELECT name_ko, ticker, aum
        FROM etf_products
        ORDER BY aum DESC LIMIT :top_k
    """,
}

# 방법 2: LLM 기반 Text2SQL (유연, 검증 필요)
TEXT2SQL_PROMPT = """
다음 ETF 데이터베이스 스키마를 참고하여 SQL을 생성하세요.

## 테이블 스키마
- etf_products(name_ko, ticker, ksd_fund_code, benchmark_index,
               category_l1, category_l2, total_expense_ratio,
               aum, nav, listing_date, currency_hedge)
- etf_holdings(ksd_fund_code, holding_name, holding_ticker,
               weight_pct, shares, market_value, as_of_date)
- etf_distributions(ksd_fund_code, record_date, amount_per_share)

## 규칙
- SELECT 문만 허용 (INSERT/UPDATE/DELETE 금지)
- LIMIT 100 이하만 허용
- 테이블 이름은 정확히 사용

질문: {question}
SQL:
"""

def text2sql_query(question: str, intent_result: dict) -> list[dict]:
    """자연어 질문 → SQL 생성 → 실행 → 결과 반환."""
    # 1. LLM으로 SQL 생성
    sql = generate_sql(question)
    # 2. SQL 검증 (SELECT만, LIMIT 확인)
    validated_sql = validate_sql(sql)
    # 3. Aurora PostgreSQL에서 실행
    with get_session() as session:
        result = session.execute(text(validated_sql))
        return [dict(row) for row in result]
```

### 채널 2: Graph DB — Traversal Search (관계 추론)

기존 GraphRAG Toolkit의 Traversal-Based Search를 활용합니다. 관계 탐색, Multi-hop 추론에 최적화되어 있습니다.

```python
# graph_query.py — Graph Traversal 채널

def graph_traversal_query(question: str) -> str:
    """기존 GraphRAG traversal-based search 실행."""
    engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, vector_store
    )
    response = engine.query(question)
    return str(response)
```

### 채널 3: Vector Search (의미 검색)

OpenSearch Serverless에서 Chunk/Statement 임베딩 기반 유사도 검색을 수행합니다. 서술형 질문(OPEN)에서 관련 문서 컨텍스트를 찾는 데 효과적입니다.

```python
# vector_query.py — Vector Search 채널

def vector_search(question: str, top_k: int = 10) -> list[dict]:
    """OpenSearch에서 질문 임베딩 기반 유사도 검색."""
    # 1. 질문 임베딩 생성
    embedding = embed_model.get_text_embedding(question)
    # 2. OpenSearch KNN 검색
    results = opensearch_client.search(
        index="statement",
        body={
            "size": top_k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": top_k
                    }
                }
            }
        }
    )
    return results["hits"]["hits"]
```

---

## 5.5 Query Router Agent 구현

### 전체 흐름

> 참조: [아이지에이웍스 Text-to-SQL/Chart 에이전트 Part 2](https://aws.amazon.com/ko/blogs/tech/iganetworks-text2sql-agent-with-bedrock-2/)

```python
# router.py — Query Router Agent

class QueryRouter:
    """Intent 기반으로 최적의 검색 채널을 선택하고 실행하는 Agent."""

    # Intent → 검색 채널 매핑
    ROUTING_TABLE = {
        "ATTRIBUTE":   ["rdb"],
        "FILTER":      ["rdb", "graph"],
        "AGGREGATION": ["rdb"],
        "RELATION":    ["graph"],
        "MULTI_HOP":   ["graph", "rdb"],
        "COMPARISON":  ["graph", "rdb"],
        "OPEN":        ["vector", "graph"],
        "NEGATIVE":    ["vector", "graph", "rdb"],
    }

    def route_and_execute(self, question: str) -> str:
        # Step 1: Intent 분류
        intent_result = classify_intent(question)
        intent = intent_result["intent"]
        entities = intent_result["entities"]

        # Step 2: 채널 선택
        channels = self.ROUTING_TABLE.get(intent, ["vector", "graph"])

        # Step 3: 각 채널 실행
        contexts = []
        for channel in channels:
            if channel == "rdb":
                rdb_result = text2sql_query(question, intent_result)
                contexts.append({"source": "rdb", "data": rdb_result})
            elif channel == "graph":
                graph_result = graph_traversal_query(question)
                contexts.append({"source": "graph", "data": graph_result})
            elif channel == "vector":
                vector_result = vector_search(question)
                contexts.append({"source": "vector", "data": vector_result})

        # Step 4: 컨텍스트 조합 + 응답 생성
        response = generate_response(question, contexts, intent_result)
        return response
```

### 응답 생성 프롬프트

```python
RESPONSE_PROMPT = """
다음 검색 결과를 바탕으로 사용자 질문에 답변하세요.

## 규칙
- 검색 결과에 있는 정보만 사용하세요.
- 수치 데이터는 RDB 결과를 우선 사용하세요 (Source of Truth).
- 정보가 없으면 "해당 정보를 찾을 수 없습니다"라고 답변하세요.
- 출처를 명시하세요 (예: "투자설명서에 따르면...", "RDB 기준 현재 AUM은...")

## Intent: {intent}
## 사용자 질문: {question}

## 검색 결과
{formatted_contexts}
"""
```

---

## 5.6 실행 예시: 질문별 라우팅 경로

### 예시 1: ATTRIBUTE — "TIGER 미국S&P500의 총보수는?"

```
① Intent 분류 → ATTRIBUTE (confidence: 0.97)
   entities: ["TIGER 미국S&P500"], attributes: ["총보수"]
② 채널 선택 → [RDB]
③ RDB 실행:
   SELECT name_ko, total_expense_ratio
   FROM etf_products WHERE name_ko LIKE '%TIGER 미국S&P500%'
   → {"name_ko": "TIGER 미국S&P500", "total_expense_ratio": 0.07}
④ 응답: "TIGER 미국S&P500 ETF의 총보수는 연 0.07%입니다."
```

### 예시 2: OPEN — "TIGER 미국S&P500의 주요 투자위험은?"

```
① Intent 분류 → OPEN (confidence: 0.92)
   entities: ["TIGER 미국S&P500"]
② 채널 선택 → [Vector, Graph]
③ Vector 실행: OpenSearch에서 "투자위험" 관련 Statement 검색
   → "환율변동위험: 해외 자산에 투자하므로...", "시장위험: 주식시장의 변동에..."
④ Graph 실행: Traversal-Based Search
   → TIGER 미국S&P500 → HAS_RISK → 환율변동위험, 시장위험, 추적오차위험
⑤ 응답: "투자설명서에 따르면 TIGER 미국S&P500의 주요 투자위험은
         1) 환율변동위험 - 환헤지를 실시하지 않아...
         2) 시장위험 - 주식시장 변동에 따라...
         3) 추적오차위험 - 기초지수와의 괴리 발생 가능..."
```

### 예시 3: MULTI_HOP — "S&P500을 추적하는 ETF의 주요 보유종목은?"

```
① Intent 분류 → MULTI_HOP (confidence: 0.88)
   entities: ["S&P 500"]
② 채널 선택 → [Graph, RDB]
③ Graph 실행:
   (ETF)-[TRACKS]->(S&P 500) → TIGER 미국S&P500, TIGER S&P500 등 식별
④ RDB 실행 (Graph 결과의 ksd_fund_code로 조회):
   SELECT h.holding_name, h.weight_pct
   FROM etf_holdings h WHERE h.ksd_fund_code IN ('KR70000D0009', ...)
   ORDER BY h.weight_pct DESC LIMIT 20
   → Apple 7.12%, NVIDIA 6.89%, Microsoft 6.54% ...
⑤ 응답: "S&P 500 지수를 추적하는 TIGER 미국S&P500 ETF의 주요 보유종목은
         Apple (7.12%), NVIDIA (6.89%), Microsoft (6.54%) ... 입니다."
```

### 예시 4: COMPARISON — "TIGER 미국S&P500과 TIGER 미국나스닥100의 차이는?"

```
① Intent 분류 → COMPARISON (confidence: 0.93)
   entities: ["TIGER 미국S&P500", "TIGER 미국나스닥100"]
② 채널 선택 → [Graph, RDB]
③ Graph 실행: 두 ETF의 관계 구조 비교
   → TIGER 미국S&P500: TRACKS S&P 500, MANAGES 미래에셋, HAS_RISK 환율변동위험
   → TIGER 미국나스닥100: TRACKS NASDAQ-100, MANAGES 미래에셋, HAS_RISK 환율변동위험
④ RDB 실행: 두 상품의 정형 데이터 비교
   → 총보수: 0.07% vs 0.07%, AUM: 5.2조 vs 3.1조
⑤ 응답: 비교 테이블 형태로 응답 생성
```

---

## 5.7 쿼리 분해 (Query Decomposition)

복합 질문은 여러 하위 질문으로 분해하여 각각 최적 채널로 라우팅합니다.

```
입력: "미래에셋자산운용이 운용하는 ETF 중 S&P 500 지수를 추적하는
       상품의 주요 보유종목은?"

분해 결과:
  Sub-Q1: "미래에셋자산운용이 운용하는 ETF 목록"
          → FILTER (Graph: MANAGES 관계 탐색)

  Sub-Q2: "그 중 S&P 500 지수를 추적하는 것"
          → FILTER (Graph: TRACKS 관계 탐색)

  Sub-Q3: "해당 상품의 주요 보유종목"
          → ATTRIBUTE (RDB: etf_holdings 테이블 조회)

실행:
  1. Graph: (미래에셋자산운용)-[MANAGES]->(ETF)-[TRACKS]->(S&P 500)
     → ksd_fund_code: KR70000D0009
  2. RDB: SELECT * FROM etf_holdings
          WHERE ksd_fund_code = 'KR70000D0009'
          ORDER BY weight_pct DESC
  3. 결과 조합 → LLM 응답 생성
```

```python
QUERY_DECOMPOSITION_PROMPT = """
복합 질문을 독립적인 하위 질문으로 분해하세요.

## 규칙
- 각 하위 질문은 단일 Intent로 분류 가능해야 합니다.
- 하위 질문 간의 의존 관계를 명시하세요.
- 최대 4개까지 분해하세요.

## 응답 형식 (JSON)
{
  "sub_questions": [
    {"id": 1, "question": "...", "intent": "FILTER", "depends_on": []},
    {"id": 2, "question": "...", "intent": "FILTER", "depends_on": [1]},
    {"id": 3, "question": "...", "intent": "ATTRIBUTE", "depends_on": [2]}
  ]
}

질문: {question}
"""
```

---

## 5.8 아키텍처 요약

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 질문                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Intent Classifier (Claude 3.7 Sonnet)                              │
│  → Intent 분류 (8종) + 엔티티 추출 + Confidence Score               │
│  → 복합 질문이면 Query Decomposition                                 │
└──────┬─────────────┬─────────────┬──────────────┬───────────────────┘
       │             │             │              │
       ▼             ▼             ▼              ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
  │Channel 1│  │Channel 2 │  │Channel 3 │  │ Multi-Channel│
  │  RDB    │  │ Graph DB │  │ Vector   │  │  (복합 질문)  │
  │Text2SQL │  │Traversal │  │ Search   │  │ Graph → RDB  │
  │         │  │          │  │          │  │              │
  │ Aurora  │  │ Neptune  │  │OpenSearch│  │  순차 실행    │
  │PostgreSQL│  │ DB       │  │Serverless│  │              │
  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘
       │            │             │               │
       └────────────┼─────────────┼───────────────┘
                    ▼
         ┌─────────────────────┐
         │  Context Assembly   │
         │  RDB 수치 우선 적용   │
         │  Graph 관계 보완     │
         │  Vector 서술 보완    │
         └─────────┬───────────┘
                   ▼
         ┌─────────────────────┐
         │  Response Generator │
         │  (Claude 3.7 Sonnet) │
         │  출처 명시 + 수치 검증 │
         └─────────────────────┘
```

### 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **RDB = Source of Truth** | 수치/속성 질문은 반드시 RDB에서 조회 (PDF 추출값이 아님) |
| **Graph = 관계 추론** | 엔티티 간 관계 탐색, Multi-hop 추론에 활용 |
| **Vector = 의미 검색** | 서술형 질문에서 관련 문서 컨텍스트 검색 |
| **Intent 기반 라우팅** | LLM이 질문 의도를 분류하여 최적 채널 선택 |
| **쿼리 분해** | 복합 질문은 하위 질문으로 분해 후 각각 최적 채널에 라우팅 |
| **수치 우선** | 동일 정보가 RDB와 Graph에 모두 있으면 RDB 값을 우선 사용 |
