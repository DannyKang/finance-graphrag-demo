# 4. 실제 구현 예제: TIGER ETF GraphRAG

TIGER ETF 221종의 상품 데이터를 **AWS GraphRAG Toolkit + Neptune DB + OpenSearch Serverless + Aurora PostgreSQL**로 구축한 실제 사례입니다.


## 4.1 시스템 구성

![](images/mirae-asset-architecture.png)


```
┌──────────────────────────────────────────────────────────────────────┐
│                        데이터 소스                                    │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  웹 스크래핑      │  │ PDF 투자설명서    │  │ Aurora PostgreSQL   │  │
│  │  (ETF 상품 정보)  │  │ (887건)          │  │ (RDB: 상품/보유종목) │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           └─────────────────────┼──────────────────────┘             │
│                                 ▼                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  AWS GraphRAG Toolkit (Extraction Pipeline)                   │  │
│  │  - 추출 LLM: Claude 3.7 Sonnet (Amazon Bedrock)              │  │
│  │  - Embedding: Amazon Titan Embed v2 (1024차원)                │  │
│  │  - 커스텀 ETF 도메인 온톨로지 (17 엔티티 분류 / 17 관계 유형)   │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               ▼                                      │
│  ┌──────────────────────┐  ┌──────────────────────────────┐        │
│  │  Amazon Neptune DB    │  │  Amazon OpenSearch Serverless │        │
│  │  (Graph Store)        │  │  (Vector Store)               │        │
│  │  OpenCypher 쿼리      │  │  Chunk + Statement 임베딩     │        │
│  └──────────────────────┘  └──────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

### 인프라 구성 요약

| 구성 요소 | AWS 서비스 | 역할 |
|----------|-----------|------|
| **RDB** | Aurora PostgreSQL | ETF 상품 정보, 보유종목, 분배금 저장 |
| **Graph Store** | Amazon Neptune Database | 3-Tier Lexical Graph 저장, OpenCypher 쿼리 |
| **Vector Store** | OpenSearch Serverless | Chunk/Statement 임베딩 인덱스, 유사도 검색 |
| **추출/응답 LLM** | Amazon Bedrock (Claude 3.7 Sonnet) | 명제 추출, 엔티티/관계 추출, 응답 생성 |
| **Embedding** | Amazon Bedrock (Titan Embed v2) | 1024차원 벡터 임베딩 생성 |

---

## 4.2 도메인 온톨로지 설계

ETF 도메인에 특화된 **17개 엔티티 분류**와 **17개 관계 유형**을 정의했습니다.

![](./images/ontology_1.png)

### 엔티티 분류 (Entity Classifications)

> 소스: `aos-neptune/src/tiger_etf/graphrag/indexer.py`

```python
ETF_ENTITY_CLASSIFICATIONS = [
    "ETF",                       # ETF 상품 (TIGER 미국S&P500 등)
    "Asset Management Company",  # 자산운용사 (미래에셋자산운용)
    "Index",                     # 추적 지수 (S&P500, KOSPI200)
    "Stock",                     # 개별 종목 (NVIDIA, Apple)
    "Bond",                      # 채권 (US Treasury, 국고채)
    "Exchange",                  # 거래소 (한국거래소, NYSE)
    "Regulatory Body",           # 규제기관 (금융위원회)
    "Regulation",                # 법률/규정 (자본시장법)
    "Trustee",                   # 수탁회사 (한국씨티은행)
    "Distributor",               # 판매회사 (증권사, 은행)
    "Sector",                    # 업종/섹터 (반도체, IT)
    "Country",                   # 투자 국가 (미국, 한국)
    "Risk Factor",               # 위험 요소 (환율위험)
    "Fee",                       # 수수료/비용 (총보수)
    "Benchmark",                 # 비교지수
    "Person",                    # 펀드매니저 등
    "Derivative",                # 파생상품 (swap, option)
]
```

### 관계 유형 (Relationship Types)

| 관계 | 의미 | 예시 |
|------|------|------|
| `MANAGES` | 운용사 → ETF 운용 | 미래에셋자산운용 → TIGER 미국S&P500 |
| `TRACKS` | ETF → 지수 추적 | TIGER 미국S&P500 → S&P 500 |
| `INVESTS_IN` | ETF → 종목/자산 투자 | TIGER 미국S&P500 → Apple |
| `LISTED_ON` | ETF → 거래소 상장 | TIGER 미국S&P500 → 한국거래소 |
| `REGULATED_BY` | 규제기관에 의한 규제 | |
| `DISTRIBUTED_BY` | 판매회사에 의한 판매 | |
| `TRUSTEED_BY` | 수탁회사에 의한 수탁 | TIGER 미국S&P500 → 한국씨티은행 |
| `BENCHMARKED_AGAINST` | 비교지수 대비 | |
| `BELONGS_TO_SECTOR` | 섹터 소속 | Apple → IT |
| `HAS_FEE` | 수수료/보수 보유 | TIGER 미국S&P500 → 0.07% |
| `HAS_RISK` | 위험요소 보유 | TIGER 미국S&P500 → 환율변동위험 |
| `ISSUED_BY` | 발행주체 | |
| `LOCATED_IN` | 국가/지역 위치 | Apple → 미국 |
| `HOLDS` | 보유종목/자산 | |
| `COMPONENT_OF` | 지수 구성종목 | Apple → S&P 500 |
| `GOVERNED_BY` | 법률/규정 규율 | TIGER 미국S&P500 → 자본시장법 |
| `SUBSIDIARY_OF` | 자회사 관계 | |

### 커스텀 추출 프롬프트 (핵심 규칙)

도메인 온톨로지를 강제하기 위해 커스텀 프롬프트에 다음 규칙을 포함합니다:



```
Entity Classification Rules:
  - 분류는 반드시 위 목록에서 선택 (새 분류 생성 금지)
  - ETF 상품 → "ETF", 자산운용사 → "Asset Management Company" 등

Relationship Type Rules:
  - 허용된 17개 관계 유형만 사용

Entity Name Normalization Rules:
  - 한국 엔티티는 공식 한글명 사용 (미래에셋자산운용)
  - 지수는 표준 이름 사용 (S&P 500, KOSPI 200)
  - 문서 구조 엔티티 추출 금지 (제1조, 제2호)
  - 중복 엔티티 병합 (한영 중복 시 한글명 사용)
```

---

## 4.3 데이터 흐름: PDF/RDB에서 Entity Extraction까지

Entity Extraction의 **주요 원본은 PDF 투자설명서**이며, RDB 데이터는 PDF에 없는 정형 정보를 보완하기 위해 자연어 변환 후 동일한 파이프라인에 투입됩니다.

```
경로 A (주요): PDF 투자설명서 → PyMuPDFReader → LlamaIndex Document
경로 B (보조): RDB 정형 데이터 → 자연어 변환 → LlamaIndex Document
                                    ↓
                        동일한 Extraction Pipeline으로 통합
                                    ↓
                    Chunking → Proposition → Entity/Relation
                                    ↓
                     Neptune DB (Graph) + OpenSearch (Vector)
```

### Step 1A: PDF 투자설명서 로딩 (주요 소스)

> 소스: `aos-neptune/src/tiger_etf/graphrag/loader.py` — `load_pdfs()`

```python
def load_pdfs(limit: Optional[int] = None) -> list[Document]:
    pdf_dir = settings.pdfs_dir
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    reader = PyMuPDFReader()
    documents: list[Document] = []

    # RDB에서 ksd_fund_code -> ticker 매핑 구축
    ticker_map = _build_ticker_map()

    for pdf_path in pdf_files:
        meta = _parse_pdf_filename(pdf_path, ticker_map)
        docs = reader.load_data(file_path=pdf_path)
        for doc in docs:
            doc.metadata.update(meta)   # 메타데이터 부착
        documents.extend(docs)

    return documents
```

**PDF 파일명 규칙**: `{ksd_fund_code}_{doc_type}_{hash}.pdf`

```python
def _parse_pdf_filename(pdf_path, ticker_map):
    # 예: KR70000D0009_prospectus_0506c0d9.pdf
    # → ksd_fund_code: KR70000D0009
    # → doc_type: prospectus
    # → ticker: 360750 (RDB에서 조회)
```

| doc_type | 설명 | 포함 내용 |
|----------|------|----------|
| `prospectus` | 투자설명서 | 상품 상세, 위험요소, 수수료 구조, 운용전략 |
| `simple_prospectus` | 간이투자설명서 | 요약된 상품 정보 |
| `rules` | 집합투자규약 | 법적 규정, 운용 규칙 |
| `monthly_report` | 월간 보고서 | 운용 실적, 자산 현황 |
| `factsheet` | 팩트시트 | 핵심 지표 요약 |

**PDF에서 추출되는 원본 텍스트 예시** (투자설명서 일부):

```text
제1부 집합투자기구의 개요

1. 집합투자기구의 명칭: TIGER 미국S&P500 증권 상장지수 투자신탁(주식-파생형)
2. 집합투자업자: 미래에셋자산운용(주)
3. 수탁회사: 한국씨티은행(주)
4. 판매회사: 미래에셋증권(주), NH투자증권(주) 외

이 투자신탁은 S&P 500 Price Return Index를 기초지수로 하여,
기초지수의 수익률을 추적하는 것을 목적으로 합니다.

[투자위험]
- 환율변동위험: 이 투자신탁은 해외 자산에 투자하므로 환율 변동에 따른
  손실이 발생할 수 있습니다. 환헤지를 실시하지 않습니다.
- 시장위험: 주식시장의 변동에 따라 투자원본의 손실이 발생할 수 있습니다.

총보수: 연 0.07% (운용보수 0.045%, 판매보수 0.01%, 수탁보수 0.01%)
```

### Step 1B: RDB 정형 데이터 로딩 (보조 소스)

> 소스: `aos-neptune/src/tiger_etf/graphrag/loader.py` — `load_rdb()`

PDF에 없는 정형 데이터(보유종목 비중, AUM, 분배금 이력 등)를 RDB에서 조회하여 **자연어 텍스트로 변환** 후 동일한 파이프라인에 투입합니다.

```python
def _product_to_document(session, product):
    lines = [
        f"ETF 상품명: {product.name_ko}",
        f"티커: {product.ticker}",
        f"KSD 펀드코드: {product.ksd_fund_code}",
    ]
    if product.benchmark_index:
        lines.append(f"벤치마크 지수: {product.benchmark_index}")
    if product.total_expense_ratio is not None:
        lines.append(f"총보수: {product.total_expense_ratio}%")
    if product.aum is not None:
        lines.append(f"순자산총액(AUM): {product.aum:,.0f} 원")
    if product.currency_hedge is not None:
        lines.append(f"환헤지: {'예' if product.currency_hedge else '아니오'}")

    # 상위 20개 보유종목
    holdings = session.query(EtfHolding).filter(...).order_by(
        EtfHolding.weight_pct.desc()
    ).limit(20).all()
    if holdings:
        lines.append("\n주요 보유종목:")
        for h in holdings:
            lines.append(f"  - {h.holding_name} ({h.weight_pct}%)")

    # 최근 5건 분배금
    dists = session.query(EtfDistribution).filter(...).order_by(
        EtfDistribution.record_date.desc()
    ).limit(5).all()
    if dists:
        lines.append("\n최근 분배금:")
        for d in dists:
            lines.append(f"  - {d.record_date}: {d.amount_per_share:,.0f}원")

    return Document(
        text="\n".join(lines),
        metadata={"source": "rdb", "ticker": product.ticker, ...},
    )
```

**변환된 자연어 텍스트 예시**:

```text
ETF 상품명: TIGER 미국S&P500
티커: 360750
KSD 펀드코드: KR70000D0009
벤치마크 지수: S&P 500 Index (Price Return)
대분류: 해외주식
총보수: 0.07%
순자산총액(AUM): 5,230,000,000,000 원
환헤지: 아니오

주요 보유종목:
  - Apple Inc (7.12%)
  - NVIDIA Corp (6.89%)
  - Microsoft Corp (6.54%)
  - Amazon.com Inc (3.82%)
  - Meta Platforms Inc (2.65%)

최근 분배금:
  - 2025-01-15: 100원
  - 2024-10-15: 95원
```

### 두 경로의 통합

> 소스: `aos-neptune/src/tiger_etf/graphrag/indexer.py` — `build_all()`

```python
def build_all(pdf_limit=None, rdb_limit=None):
    docs: list[Document] = []
    docs.extend(load_pdfs(limit=pdf_limit))   # 경로 A: PDF
    docs.extend(load_rdb(limit=rdb_limit))     # 경로 B: RDB
    build_index(docs)  # 동일한 LexicalGraphIndex로 처리
```

| 구분 | 경로 A: PDF | 경로 B: RDB |
|------|------------|-------------|
| **소스** | 투자설명서, 간이설명서, 규약 등 | Aurora PostgreSQL 테이블 |
| **문서 수** | 887건 | 221건 (ETF 상품 수) |
| **내용** | 위험요소, 수수료, 운용전략, 법적 조항 | 보유종목 비중, AUM, NAV, 분배금 |
| **특징** | 비정형 텍스트 (Lexical Graph의 본래 대상) | 정형 → 자연어 변환 후 투입 |

### Step 2: Chunking + Proposition Extraction

> 소스: `aos-neptune/src/tiger_etf/graphrag/indexer.py` — `build_index()`

```python
def build_index(documents: list[Document]) -> None:
    _configure()  # Bedrock LLM/Embedding 설정
    graph_store, vector_store = _make_stores()  # Neptune + OpenSearch
    extraction_config = _make_extraction_config()  # ETF 온톨로지

    graph_index = LexicalGraphIndex(
        graph_store, vector_store,
        indexing_config=extraction_config,  # 커스텀 온톨로지 적용
    )
    graph_index.extract_and_build(documents, show_progress=True)
```

내부적으로 `extract_and_build()` 가 실행하는 과정:

**Chunking** (256자 단위, 20자 오버랩):

```text
PDF 원본: "이 투자신탁은 S&P 500 Price Return Index를 기초지수로 하여,
          기초지수의 수익률을 추적하는 것을 목적으로 합니다.
          환율변동위험: 이 투자신탁은 해외 자산에 투자하므로..."

    ↓ SentenceSplitter (chunk_size=256, overlap=20)

Chunk 1: "이 투자신탁은 S&P 500 Price Return Index를 기초지수로 하여,
          기초지수의 수익률을 추적하는 것을 목적으로 합니다..."
Chunk 2: "...목적으로 합니다. 환율변동위험: 이 투자신탁은 해외 자산에
          투자하므로 환율 변동에 따른 손실이 발생할 수 있습니다..."
```

**Proposition Extraction** (LLM 호출 1 — Claude 3.7 Sonnet):

```text
Chunk 입력: "이 투자신탁은 S&P 500 Price Return Index를 기초지수로 하여,
            기초지수의 수익률을 추적하는 것을 목적으로 합니다.
            집합투자업자: 미래에셋자산운용(주). 수탁회사: 한국씨티은행(주)"

    ↓ LLM이 원자적 명제로 분해 (복합문 분리, 대명사 해소)

→ "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적한다"
→ "미래에셋자산운용은 TIGER 미국S&P500 ETF를 운용한다"
→ "한국씨티은행은 TIGER 미국S&P500 ETF의 수탁회사이다"
→ "TIGER 미국S&P500 ETF는 환헤지를 하지 않는다"
→ "TIGER 미국S&P500 ETF는 환율변동위험이 있다"
→ "TIGER 미국S&P500 ETF의 총보수는 0.07%이다"
```

### Step 3: Entity/Relation Extraction

**Topic + Entity + Relation Extraction** (LLM 호출 2 — Claude 3.7 Sonnet + 커스텀 ETF 프롬프트):

커스텀 프롬프트에 정의된 **17개 엔티티 분류 + 17개 관계 유형**이 강제 적용됩니다.

```text
topic: TIGER 미국S&P500 투자 구조

  entities(|class):
    TIGER 미국S&P500|ETF
    미래에셋자산운용|Asset Management Company
    S&P 500|Index
    한국씨티은행|Trustee
    환율변동위험|Risk Factor
    Apple Inc|Stock

  proposition: "미래에셋자산운용은 TIGER 미국S&P500 ETF를 운용한다"
    entity-entity relationships:
      미래에셋자산운용|MANAGES|TIGER 미국S&P500

  proposition: "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적한다"
    entity-entity relationships:
      TIGER 미국S&P500|TRACKS|S&P 500

  proposition: "한국씨티은행은 TIGER 미국S&P500 ETF의 수탁회사이다"
    entity-entity relationships:
      TIGER 미국S&P500|TRUSTEED_BY|한국씨티은행

  proposition: "TIGER 미국S&P500 ETF는 환율변동위험이 있다"
    entity-entity relationships:
      TIGER 미국S&P500|HAS_RISK|환율변동위험

  proposition: "TIGER 미국S&P500 ETF는 Apple Inc에 7.12% 비중으로 투자한다"
    entity-entity relationships:
      TIGER 미국S&P500|INVESTS_IN|Apple Inc
    entity-attributes:
      Apple Inc|HAS_WEIGHT|7.12%

  proposition: "TIGER 미국S&P500 ETF의 총보수는 0.07%이다"
    entity-attributes:
      TIGER 미국S&P500|HAS_FEE|0.07%
```

---

## 4.4 3-Tier 그래프 저장 예시

추출 결과가 Neptune DB(Graph Store)와 OpenSearch Serverless(Vector Store)에 어떻게 저장되는지, "TIGER 미국S&P500" ETF를 예시로 각 Tier별로 살펴봅니다.

### Tier 1 — Lineage (계보)

원본 문서와 텍스트 조각의 출처가 추적됩니다.

```
(__Source__: "KR70000D0009_prospectus_0506c0d9.pdf")
  │  metadata: {ksd_fund_code: "KR70000D0009", doc_type: "prospectus", ticker: "360750"}
  │
  │  __HAS_CHUNK__
  ├──▶ (__Chunk__: "이 투자신탁은 S&P 500 Price Return Index를 기초지수로...")
  │        │ __NEXT__
  ├──▶ (__Chunk__: "환율변동위험: 이 투자신탁은 해외 자산에 투자하므로...")
  │        │ __NEXT__
  └──▶ (__Chunk__: "총보수: 연 0.07% (운용보수 0.045%, 판매보수 0.01%...")


(__Source__: "rdb::360750")        ← RDB 소스는 별도로 구분
  │
  └──▶ (__Chunk__: "ETF 상품명: TIGER 미국S&P500\n티커: 360750\n...")
```

- PDF 소스와 RDB 소스가 각각의 `__Source__` 노드로 구분
- Chunk 간 `__NEXT__` 관계로 순서 보존

### Tier 2 — Entity-Relation (엔티티-관계)

추출된 엔티티 간의 관계가 명시적으로 표현됩니다.

```
                    (한국씨티은행)
                     [Trustee]
                         ▲
                    TRUSTEED_BY
                         │
(미래에셋자산운용)──MANAGES──▶(TIGER 미국S&P500)──TRACKS──▶(S&P 500)
 [Asset Mgmt Co.]               [ETF]                   [Index]
                                  │
                     ┌────────────┼────────────┐
                     │            │            │
                INVESTS_IN    HAS_RISK     HAS_FEE
                     │            │            │
              ┌──────┼──────┐     ▼            ▼
              ▼      ▼      ▼  (환율변동위험) (0.07%)
           (Apple)(NVIDIA)(MSFT) [Risk Factor] [Fee]
           [Stock] [Stock][Stock]
              │
         LOCATED_IN
              ▼
           (미국)
          [Country]
```

- 엔티티는 `__SUBJECT__` 또는 `__OBJECT__`로 Fact에 연결
- **Multi-hop 질의 가능**: "S&P 500을 추적하는 ETF가 투자하는 종목은?" → TRACKS 역추적 → INVESTS_IN 순회

### Tier 3 — Summary (요약)

Topic → Statement → Fact 계층으로 요약된 지식이 저장됩니다.

```
(__Topic__: "TIGER 미국S&P500 투자 구조")
  │
  │  __HAS_STATEMENT__
  ├──▶ (__Statement__: "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적한다")
  │       │  __SUPPORTS__
  │       ├──▶ (__Fact__: "TIGER 미국S&P500|TRACKS|S&P 500")
  │       └──▶ (__Fact__: "TIGER 미국S&P500|INVESTS_IN|미국 대형주")
  │
  │  __PREVIOUS__ (연결 목록)
  │
  ├──▶ (__Statement__: "미래에셋자산운용은 TIGER 미국S&P500 ETF를 운용한다")
  │       │  __SUPPORTS__
  │       └──▶ (__Fact__: "미래에셋자산운용|MANAGES|TIGER 미국S&P500")
  │
  └──▶ (__Statement__: "TIGER 미국S&P500 ETF는 환율변동위험이 있다")
          │  __SUPPORTS__
          └──▶ (__Fact__: "TIGER 미국S&P500|HAS_RISK|환율변동위험")
```

- **Statement**: 컨텍스트 창에서 LLM에 반환되는 기본 단위 → OpenSearch에 벡터 임베딩 저장
- **Fact**: 서로 다른 소스 간의 연결 제공 (동일한 사실이 여러 문서에서 언급되면 단일 노드)
- **Topic**: 동일 소스 내 관련 Statement 간의 로컬 연결 제공

### Tier 간 연결 전체 구조

```
Tier 1 (Lineage)          Tier 3 (Summary)           Tier 2 (Entity-Relation)
─────────────────          ─────────────────           ───────────────────────

__Source__                  __Topic__                   __Entity__
  │                           │                         (미래에셋자산운용)
  │ __HAS_CHUNK__             │ __HAS_STATEMENT__            │
  ▼                           ▼                         __SUBJECT__
__Chunk__ ◀──__MENTIONS_IN──▶ __Statement__                  │
  (텍스트+임베딩)               │                           ▼
                               │ __SUPPORTS__           __Fact__
                               ▼                      (MANAGES)
                            __Fact__ ──__OBJECT__──▶ __Entity__
                         (벡터 임베딩)                (TIGER 미국S&P500)
```

---

## 4.5 질의 예시 (Traversal-Based Search)

`LexicalGraphQueryEngine.for_traversal_based_search()`는 **벡터 검색으로 출발 노드를 찾고, 그래프 엣지를 따라 관련 Statement를 수집한 뒤, LLM이 최종 답변을 생성**하는 하이브리드 파이프라인입니다.

> 소스: `aos-neptune/src/tiger_etf/graphrag/query.py`

```python
def get_query_engine():
    GraphRAGConfig.aws_region = settings.graphrag_aws_region
    GraphRAGConfig.extraction_llm = settings.graphrag_extraction_llm
    GraphRAGConfig.response_llm = settings.graphrag_response_llm
    GraphRAGConfig.embed_model = settings.graphrag_embedding_model

    # Reader endpoint 사용 (쓰기/읽기 분리)
    graph_store = GraphStoreFactory.for_graph_store(settings.graph_store_reader)
    vector_store = VectorStoreFactory.for_vector_store(settings.vector_store)

    return LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, vector_store
    )

def query(question: str) -> str:
    engine = get_query_engine()
    response = engine.query(question)
    return str(response)
```

### 전체 파이프라인 흐름

```
사용자 질의
  │
  ▼
Phase 1. 질의 분석 & 엔티티 컨텍스트 추출
  │  KeywordProvider → 키워드 추출
  │  EntityContextProvider → 그래프에서 관련 엔티티 컨텍스트 수집
  │  QueryModeRetriever → 질의 복잡도 판단 (SIMPLE / COMPLEX)
  │
  ▼
Phase 2. 두 Retriever가 병렬로 시작 노드 탐색 (ThreadPoolExecutor)
  │  ├── ChunkBasedSearch (weight=1.0)  : 벡터 유사도 → Chunk 출발
  │  └── EntityNetworkSearch (weight=1.0): 엔티티 컨텍스트 → Entity/Topic 출발
  │
  ▼
Phase 3. 그래프 순회 (Neptune OpenCypher)
  │  시작 노드에서 엣지를 따라 Statement → Topic → Source 수집
  │
  ▼
Phase 4. 후처리 파이프라인
  │  Dedup → Rerank → Prune → Rescore → Truncate
  │
  ▼
Phase 5. LLM 응답 생성 (Claude 3.7 Sonnet)
  │  수집된 Statement + Entity Context → 근거 기반 답변
  │
  ▼
최종 응답
```

### 구체적 예시: "TIGER 미국S&P500 ETF의 주요 보유종목과 비중은?"

#### Phase 1 — 질의 분석 & 엔티티 컨텍스트 추출

```
사용자 질의 → KeywordProvider → 키워드 추출
                                  │
                          ["TIGER 미국S&P500", "보유종목", "비중"]
                                  │
                          EntityContextProvider
                          → 그래프에서 관련 엔티티 컨텍스트 수집
                                  │
                          Entity Contexts:
                            - "TIGER 미국S&P500" (label: ETF)
                            - "S&P 500" (label: Index)
```

`QueryModeRetriever`가 질의 복잡도를 판단합니다. 이 질의는 단일 ETF에 대한 직접적 질문이므로 **SIMPLE** 모드로 처리됩니다. COMPLEX일 경우 키워드 기반 서브쿼리로 분해 후 병렬 실행합니다.

#### Phase 2 — 두 Retriever가 병렬로 시작 노드 탐색

`CompositeTraversalBasedRetriever`는 기본적으로 2개의 하위 검색기를 `ThreadPoolExecutor`로 **병렬 실행**합니다.

**(A) ChunkBasedSearch** — 벡터 유사도 기반 Chunk 출발

```
1. 질의를 Amazon Titan Embed Text v2로 임베딩
   "TIGER 미국S&P500 ETF의 주요 보유종목과 비중은?" → [0.023, -0.156, 0.891, ...]

2. OpenSearch Serverless에서 벡터 유사도 검색 (topK)
   → 유사한 Chunk 노드들을 반환:
     - chunk_001: "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적하며..." (score: 0.92)
     - chunk_002: "주요 보유종목: Apple (7.2%), Microsoft (6.8%)..." (score: 0.89)
     - chunk_003: "NVIDIA (5.1%), Amazon (4.3%), ..." (score: 0.85)
```

**(B) EntityNetworkSearch** — 엔티티 네트워크 기반 출발

```
1. 추출된 엔티티 컨텍스트로 벡터 검색
   "TIGER 미국S&P500" → OpenSearch에서 Entity/Topic 노드 검색

2. 엔티티 네트워크에서 관련 노드 탐색
   → "TIGER 미국S&P500" 엔티티 → 연결된 Topic/Chunk 노드 식별
```

#### Phase 3 — 그래프 순회 (Neptune OpenCypher)

각 Retriever가 찾은 시작 노드에서 Neptune DB의 엣지를 따라 순회하며 관련 Statement를 수집합니다.

**(A) ChunkBasedSearch의 그래프 순회:**

```cypher
-- Chunk에서 출발하여 Statement → Topic → Source로 순회
MATCH (c:Chunk)-[:HAS_STATEMENT]->(s:Statement)-[:SUPPORTS]->(t:Topic)
WHERE c.chunkId IN ['chunk_001', 'chunk_002', 'chunk_003']
RETURN s, t, source metadata
```

```
chunk_001 ──HAS_STATEMENT──▶ Statement: "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적한다"
                                │
                             SUPPORTS
                                │
                                ▼
                          Topic: "TIGER 미국S&P500 투자 구조"
                                │
                         HAS_STATEMENT (같은 Topic의 다른 Statement도 수집)
                                │
                                ▼
                          Statement: "미래에셋자산운용은 TIGER 미국S&P500 ETF를 운용한다"

chunk_002 ──HAS_STATEMENT──▶ Statement: "Apple이 7.2%의 비중으로 편입되어 있다"
chunk_003 ──HAS_STATEMENT──▶ Statement: "NVIDIA가 5.1%의 비중을 차지한다"
```

**(B) EntityNetworkSearch의 그래프 순회:**

```
Entity: "TIGER 미국S&P500"
  │
  ├── INVESTS_IN ──▶ Apple (Stock)      ← 보유종목 관계
  ├── INVESTS_IN ──▶ NVIDIA (Stock)
  ├── INVESTS_IN ──▶ Microsoft (Stock)
  ├── TRACKS ──────▶ S&P 500 (Index)
  └── HAS_FEE ────▶ 0.07% (Fee)
        │
        ▼
  관련 Statement 노드들로 확장:
  MATCH (e)-[:MENTIONED_IN]->(s:Statement)-[:SUPPORTS]->(t:Topic)
  → Statement: "Apple Inc에 7.12% 비중으로 투자한다"
  → Statement: "NVIDIA Corp에 6.89% 비중으로 투자한다"
  → Statement: "Microsoft Corp에 6.54% 비중으로 투자한다"
```

**순회 결과를 그래프 구조로 시각화하면:**

```
                        ┌──────────────────────┐
                        │   Source: 투자설명서    │
                        │   (PDF 문서 메타데이터)  │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐   ┌──────────┐
             │ Topic:    │  │ Topic:    │   │ Topic:    │
             │ ETF 상품  │  │ 보유종목  │   │ 투자전략  │
             │ 개요      │  │ 구성      │   │          │
             └────┬─────┘  └────┬─────┘   └────┬─────┘
                  │             │              │
            ┌─────┴────┐  ┌────┴─────┐   ┌───┴──────┐
            ▼          ▼  ▼          ▼   ▼          ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
      │Statement │ │Statement │ │Statement │ │Statement │
      │"TIGER    │ │"Apple이  │ │"NVIDIA가 │ │"S&P 500  │
      │ 미국S&P  │ │ 7.2%의   │ │ 5.1%의   │ │ 지수를   │
      │ 500 ETF  │ │ 비중으로 │ │ 비중으로 │ │ 추적하는 │
      │ 는..."   │ │ 편입"    │ │ 편입"    │ │ 전략"    │
      └──────────┘ └──────────┘ └──────────┘ └──────────┘
            │            │           │
            ▼            ▼           ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ Chunk    │ │ Chunk    │ │ Chunk    │
      │ (벡터    │ │ (벡터    │ │ (벡터    │
      │  인덱스) │ │  인덱스) │ │  인덱스) │
      └──────────┘ └──────────┘ └──────────┘
```

#### Phase 4 — 후처리 파이프라인

두 Retriever가 수집한 결과를 순차적으로 정제합니다.

```
수집된 Statements (ChunkBasedSearch + EntityNetworkSearch 결과 합산)
  │
  ├── DedupResults          : 두 Retriever가 중복 발견한 Statement 제거
  ├── DisaggregateResults   : 복합 결과를 개별 단위로 분리
  ├── PopulateStatementStrs : Statement 노드에서 텍스트 문자열 추출
  ├── RerankStatements      : 원래 질의와의 관련성으로 재순위화
  ├── PruneStatements       : 낮은 점수의 Statement 제거
  ├── RescoreResults        : Topic/Source 단위로 점수 재계산
  ├── SortResults           : 점수 순으로 정렬
  ├── TruncateStatements    : Statement 수 제한
  ├── StatementsToStrings   : Statement를 텍스트 문자열로 변환
  ├── FormatSources         : 출처 정보 포맷팅
  └── TruncateResults       : 컨텍스트 윈도우에 맞게 최종 자르기
```

#### Phase 5 — LLM 응답 생성

최종 정제된 컨텍스트가 Claude 3.7 Sonnet에 전달됩니다.

```
[Entity Contexts]
- TIGER 미국S&P500 (ETF): S&P 500 지수를 추적하는 ETF 상품
- S&P 500 (Index): 미국 대형주 500개 기업으로 구성된 지수

[Search Results — Topic: 보유종목 구성]
Source: KR70000D0009_prospectus_0506c0d9.pdf
- "Apple이 7.2%의 비중으로 편입되어 있다"
- "Microsoft가 6.8%의 비중으로 편입되어 있다"
- "NVIDIA가 5.1%의 비중을 차지한다"
- "Amazon이 4.3%의 비중으로 편입되어 있다"

[Search Results — Topic: TIGER 미국S&P500 투자 구조]
Source: rdb::360750
- "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적한다"
- "총보수는 연 0.07%이다"

[Question]
TIGER 미국S&P500 ETF의 주요 보유종목과 비중은?
```

→ LLM이 **그래프에서 순회하여 수집된 증거만을 기반으로** 답변을 생성합니다.

### 단순 벡터 RAG와의 차이점

| 구분 | 단순 벡터 RAG | Traversal-Based Search |
|------|-------------|----------------------|
| **검색 방식** | 질의 임베딩 → 유사 Chunk 반환 | 벡터 검색은 **출발점**일 뿐, 그래프 엣지를 따라 순회 |
| **정보 범위** | 단일 Chunk 내 정보만 반환 | Chunk → Statement → Topic → 같은 Topic의 다른 Statement까지 확장 |
| **Multi-hop** | 불가능 | 가능 (TRACKS 역추적 → INVESTS_IN 순회 등) |
| **중복 제거** | Chunk 단위 중복만 제거 | Fact 노드로 동일 사실의 다중 소스 자동 통합 |
| **컨텍스트 품질** | 관련 없는 텍스트 포함 가능 | Statement 단위로 정제된 증거만 전달 |

### 검색 결과 구조 예시 (SearchResult)

```json
{
  "score": 0.92,
  "source": {
    "sourceId": "KR70000D0009_prospectus_0506c0d9.pdf",
    "metadata": {"ksd_fund_code": "KR70000D0009", "doc_type": "prospectus"}
  },
  "topics": [
    {
      "topic": "TIGER 미국S&P500 보유종목 구성",
      "statements": [
        {
          "statement": "Apple이 7.2%의 비중으로 편입되어 있다",
          "facts": ["TIGER 미국S&P500|INVESTS_IN|Apple Inc"],
          "score": 0.92,
          "retrievers": ["ChunkBasedSearch", "EntityNetworkSearch"]
        },
        {
          "statement": "NVIDIA가 5.1%의 비중을 차지한다",
          "facts": ["TIGER 미국S&P500|INVESTS_IN|NVIDIA Corp"],
          "score": 0.88,
          "retrievers": ["ChunkBasedSearch"]
        }
      ]
    }
  ]
}
```

### 파이프라인 단계별 사용 기술 요약

| 단계 | 역할 | 사용 기술 |
|------|------|-----------|
| **Phase 1** 질의 분석 | 키워드·엔티티 추출, 질의 복잡도 판단 | KeywordProvider, EntityContextProvider |
| **Phase 2** 시작 노드 탐색 | 벡터 유사도로 Chunk/Entity 식별 | OpenSearch + Titan Embed v2 |
| **Phase 3** 그래프 순회 | 엣지를 따라 Statement/Topic/Source 수집 | Neptune DB OpenCypher |
| **Phase 4** 후처리 | 중복 제거, 재순위화, 가지치기 | 내장 Processor 체인 |
| **Phase 5** 응답 생성 | 수집된 증거 기반 자연어 답변 | Claude 3.7 Sonnet (Bedrock) |

### 그래프 통계 확인 (Neptune OpenCypher)

> 소스: `aos-neptune/src/tiger_etf/graphrag/query.py` — `get_graph_stats()`

```python
def get_graph_stats() -> dict:
    store_type, identifier = _parse_graph_store_uri(settings.graph_store_reader)

    # Neptune Database의 경우
    client = session.client("neptunedata", endpoint_url=f"https://{endpoint}:8182")

    # 노드 카운트 by label
    node_results = client.execute_open_cypher_query(
        openCypherQuery="MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt"
    )
    # 엣지 카운트 by type
    edge_results = client.execute_open_cypher_query(
        openCypherQuery="MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt"
    )
    return {"nodes": ..., "edges": ...}
```

---

## 4.6 핵심 코드 구조

```
aos-neptune/
├── config.yaml                          # LLM/Embedding 모델, 워커 수 설정
├── .env.example                         # Neptune/OpenSearch/Aurora 접속 정보
├── docker/graphrag/
│   └── docker-compose.yml               # 로컬 PostgreSQL (개발용)
├── alembic/                             # DB 마이그레이션
├── src/tiger_etf/
│   ├── config.py                        # Pydantic Settings (YAML + env)
│   ├── db.py                            # SQLAlchemy 세션 관리
│   ├── models.py                        # 7개 ORM 테이블 (EtfProduct, EtfHolding 등)
│   ├── cli.py                           # CLI 진입점 (tiger-etf 명령어)
│   ├── scrapers/                        # 6종 웹 스크래퍼
│   └── graphrag/
│       ├── loader.py                    # PDF/RDB → LlamaIndex Document
│       ├── indexer.py                   # 온톨로지 + 그래프 인덱스 빌드
│       ├── query.py                     # Traversal-based Search 질의
│       └── config.py                    # GraphRAG LLM 설정 로더
└── experiments/
    ├── configs/                         # 실험 설정 (LLM/임베딩 조합)
    └── results/                         # 실험 결과 (JSON)
```

### 설정 파일 (config.yaml)

```yaml
graphrag:
  extraction_llm: "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  response_llm: "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  embedding_model: "amazon.titan-embed-text-v2:0"
  aws_region: "ap-northeast-2"
  extraction_num_workers: 2
  extraction_num_threads_per_worker: 8
  build_num_workers: 2
  batch_writes_enabled: true
  enable_cache: true
```

### 환경 변수 (.env)

```bash
# Aurora PostgreSQL (RDB)
DATABASE_URL=postgresql+psycopg://user:pass@cluster.ap-northeast-2.rds.amazonaws.com:5432/tiger_etf
DATABASE_URL_READER=postgresql+psycopg://user:pass@cluster-ro.ap-northeast-2.rds.amazonaws.com:5432/tiger_etf

# Neptune Database (Graph Store)
GRAPH_STORE=neptune-db://cluster.ap-northeast-2.neptune.amazonaws.com
GRAPH_STORE_READER=neptune-db://cluster-ro.ap-northeast-2.neptune.amazonaws.com

# OpenSearch Serverless (Vector Store)
VECTOR_STORE=aoss://https://xxxxxxxxx.ap-northeast-2.aoss.amazonaws.com
```

### CLI 사용법

```bash
# 그래프 빌드 (PDF 5건으로 테스트)
tiger-etf graphrag build-pdf --limit 5

# 전체 빌드 (PDF + RDB)
tiger-etf graphrag build

# 그래프 통계 확인
tiger-etf graphrag status

# 질의
tiger-etf graphrag query "TIGER 미국S&P500의 주요 투자위험은?"
```

---

## 4.7 구축 결과 요약

| 항목 | 수치 |
|------|------|
| 입력 ETF 상품 | 221개 |
| 입력 PDF 문서 | 887건 (테스트: 50건) |
| 생성된 그래프 노드 | ~127,000개 |
| Source 노드 | ~998개 |
| Chunk 노드 | ~13,850개 |
| Statement 노드 (명제) | ~59,015개 |
| Entity 노드 | ~5,001개 |
| Fact 노드 | ~34,433개 |
| Topic 노드 | ~13,869개 |
| 그래프 엣지 | ~748,158개 |
| 커스텀 엔티티 분류 | 17종 |
| 커스텀 관계 유형 | 17종 |
| 벡터 차원 | 1,024 (Titan Embed v2) |
| 추출 LLM | Claude 3.7 Sonnet |
| 응답 LLM | Claude 3.7 Sonnet |

### 주요 엣지 유형 분포

| 엣지 유형 | 수 | 역할 |
|----------|-----|------|
| `__NEXT__` | ~386,000 | Chunk/Fact 간 순서 연결 |
| `__SUPPORTS__` | ~107,000 | Fact → Statement 뒷받침 |
| `__MENTIONS_IN__` | ~73,000 | Entity ↔ Chunk 출현 |
| 도메인 관계 (MANAGES, TRACKS 등) | ~34,000 | Entity 간 비즈니스 관계 |
