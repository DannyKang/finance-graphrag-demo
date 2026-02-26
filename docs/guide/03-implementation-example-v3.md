# 4. 실제 구현 예제: TIGER ETF GraphRAG

TIGER ETF 221종의 상품 데이터를 **AWS GraphRAG Toolkit + Neptune DB + OpenSearch Serverless + Aurora PostgreSQL**로 구축한 실제 사례입니다.

> 소스코드: `/home/ec2-user/mirae-graphrag/aos-neptune`

## 4.1 시스템 구성

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

  entities:
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

### 질문: "TIGER 미국S&P500의 주요 투자위험은?"

```
① 질문 임베딩 생성 (Titan Embed v2, 1024차원)
      │
      ▼
② OpenSearch에서 유사 Chunk/Statement 검색 (topK)
   → "TIGER 미국S&P500 ETF는 환율변동위험이 있다" (score: 0.89)
   → "이 투자신탁은 해외 자산에 투자하므로..." (score: 0.85)
      │
      ▼
③ Neptune DB에서 그래프 탐색 (Traversal)
   ├── ChunkBasedSearch: 유사 chunk → Topic/Statement/Fact 순회
   │   → Topic "TIGER 미국S&P500 투자위험" 하위 Statement 모두 수집
   │
   └── EntityNetworkSearch: Entity Network 전사 → "다른 관련 정보" 검색
       → TIGER 미국S&P500 → HAS_RISK → 환율변동위험, 시장위험, 추적오차위험
       → TIGER 미국S&P500 → INVESTS_IN → 미국 주식 → LOCATED_IN → 미국 (환율 노출)
      │
      ▼
④ 컨텍스트 조합 → Claude 3.7 Sonnet 응답 생성
```

### 검색 결과 구조 예시

```json
{
  "source": "KR70000D0009_prospectus_0506c0d9.pdf",
  "topic": "TIGER 미국S&P500 투자위험",
  "statements": [
    "TIGER 미국S&P500 ETF는 환율변동위험이 있다",
    "이 투자신탁은 해외 자산에 투자하므로 환율 변동에 따른 손실이 발생할 수 있다",
    "환헤지를 실시하지 않는다",
    "주식시장의 변동에 따라 투자원본의 손실이 발생할 수 있다"
  ]
}
```

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
