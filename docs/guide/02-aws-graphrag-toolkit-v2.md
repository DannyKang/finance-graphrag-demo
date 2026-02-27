# 3. AWS GraphRAG Toolkit

## 3.1 개요

graphrag-toolkit의 **lexical-graph** 라이브러리는 비정형 데이터로부터 **계층적 lexical graph**(소스 문서에서 추출된 여러 수준의 세분화된 텍스트 요소를 나타내는 그래프)의 구축을 자동화하고, 사용자 질문에 답변할 때 이 그래프를 쿼리하는 질의응답 전략을 구성하기 위한 프레임워크를 제공합니다.

- GitHub: `awslabs/graphrag-toolkit`
- LlamaIndex 기반, Apache 2.0 라이선스
- Amazon Bedrock LLM + Embedding 활용

### 아키텍처

lexical-graph 라이브러리는 세 가지 백엔드 시스템에 의존합니다.

| 백엔드 | 역할 | 지원 옵션 |
|--------|------|-----------|
| **Graph Store** | Lexical Graph 저장 및 쿼리 | Neptune Analytics, Neptune Database, Neo4j, FalkorDB |
| **Vector Store** | 그래프 요소의 임베딩 인덱스 (검색 진입점) | OpenSearch Serverless, pgvector (Aurora/Postgres), Neptune Analytics, S3 Vectors |
| **Foundation Model** | 정보 추출 + 임베딩 생성 + 응답 생성 | Amazon Bedrock (Claude, Titan Embedding, Cohere 등) |

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWS GraphRAG Toolkit                        │
│                                                                 │
│   ┌────────────────────┐         ┌──────────────────────┐      │
│   │  Indexing Pipeline  │         │  Query Pipeline       │      │
│   │  (Extract + Build)  │         │  (Retrieve + Generate)│      │
│   └────────┬───────────┘         └──────────┬───────────┘      │
│            │                                │                   │
│            ▼                                ▼                   │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│   │ Amazon Bedrock  │  │  Graph Store   │  │  Vector Store  │  │
│   │ (LLM+Embedding) │  │  (Neptune DB)  │  │  (OpenSearch)  │  │
│   └────────────────┘  └────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3.2 3-Tier Lexical Graph 구조

AWS GraphRAG Toolkit의 핵심은 **3계층 lexical graph**입니다.

> 이 그래프의 역할은 질의응답 시스템이 **질문과 의미적으로 유사하지 않지만, 그럼에도 답변에 관련된 정보**를 검색하는 것을 돕는 것입니다.

![3-Tier Lexical Graph](./images/lexical-graph.png)

### 3개 계층 개요

| 계층 | 구성 요소 | 역할 |
|------|----------|------|
| **계보 (Lineage)** | `__Source__`, `__Chunk__` | 원본 문서와 텍스트 조각의 출처 추적 |
| **엔티티-관계 (Entity-Relation)** | `__Entity__`, `__RELATION__` | 추출된 개체와 관계 — 키워드 기반 검색 진입점 |
| **요약 (Summary)** | `__Topic__`, `__Statement__`, `__Fact__` | 계층적 요약, 벡터 검색 진입점, 컨텍스트 단위 |

### Tier 1: 계보 계층 (Lineage)

`__Source__` 노드와 `__Chunk__` 노드로 구성됩니다.

- **Source**: 소스 문서의 메타데이터 (파일명, URL, 작성자 등)
- **Chunk**: 실제 chunk된 텍스트와 임베딩. 이전/다음/상위/하위 chunk에 연결
- **역할**: 데이터의 출처를 추적 (provenance tracking)

### Tier 2: 엔티티-관계 계층 (Entity-Relation)

`__Entity__` 노드와 `__RELATION__` 관계로 구성됩니다.

- **Entity**: 값(예: 'TIGER 미국S&P500')과 분류(예: 'ETF')를 가짐
- **Relation**: 값(예: 'TRACKS')을 가짐
- 모든 엔티티는 `__SUBJECT__` 또는 `__OBJECT__`로서 최소 하나의 `__Fact__`와 연관
- **역할**: 상향식 키워드 기반(정확 일치) 검색의 그래프 진입점


### Tier 3: 요약 계층 (Summary)

`__Topic__`, `__Statement__`, `__Fact__` 노드로 구성됩니다.

#### Fact (사실)

단일 트리플릿(주어-술어-목적어) 형태의 의미 단위입니다.

```
예: TIGER 미국S&P500 TRACKS S&P 500
    미래에셋자산운용 MANAGES TIGER 미국S&P500
```

- **SPO 사실**: 주어와 목적어 엔티티에 모두 연결 (예: ETF → TRACKS → Index)
- **SPC 사실**: 주어 엔티티에만 연결 (예: ETF → HAS_FEE → 0.07%)
- **서로 다른 소스 간의 연결**을 제공: 동일한 사실이 여러 문서에서 언급되면 단일 노드로 통합
- 선택적 임베딩 → 그래프로의 저수준 벡터 기반 진입점

#### Statement (진술)

기본 소스에서 추출된 독립적 주장입니다. **컨텍스트 창에서 LLM에 반환되는 기본 컨텍스트 단위**입니다.

```
Statement: "TIGER 미국S&P500 ETF는 S&P 500 지수를 추적하며 미국 대형주에 투자한다"

  Facts:
    TIGER 미국S&P500 TRACKS S&P 500
    TIGER 미국S&P500 INVESTS_IN 미국 대형주
```

- 토픽 아래 그룹화되며, `__PREVIOUS__` 관계로 연결 목록 구성
- 사실과 토픽을 통해 다른 진술과 전이적으로 연결
- 선택적 임베딩 → 벡터 검색 기반 상위 수준 그래프 진입점

#### Topic (토픽)

특정 소스 문서 내의 주제 또는 관심 영역입니다.

```
예: "TIGER 미국S&P500 투자 구조"
    "ETF 위험요소 및 수수료"
```

- 개별 소스 문서로 범위 지정 → **단일 소스 내 관련 chunk 간의 연결** 증가
- 간단한 문서 수준 요약 메커니즘 제공
- 선택적 임베딩 가능

### 연결 구조의 핵심 설계

그래프 토폴로지와 연결 정도는 관련 정보를 찾는 데 중요한 역할을 합니다.

| 연결 유형 | 제공자 | 범위 |
|-----------|--------|------|
| **로컬 연결** | Topic | 동일한 소스 내의 관련 chunk 연결 |
| **글로벌 연결** | Fact | 서로 다른 소스 간의 연결 |

---

## 3.3 Extraction & Build Pipeline (인덱싱)

인덱싱은 **Extract**와 **Build** 두 단계로 구성됩니다. 마이크로 배칭을 사용하여 연속 수집(continuous ingest) 기능을 제공하며, 추출이 시작된 직후 그래프가 채워지기 시작합니다.

![Extract & Build Pipeline](./images/extract-and-build.png)

![Extract & Build Pipeline](./images/graph-toolkit.png)

### Extract 단계 (3단계 프로세스)

```
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────────┐
│  Stage 1         │     │  Stage 2              │     │  Stage 3                  │
│  Chunking        │────▶│  Proposition          │────▶│  Topic/Entity/Statement/  │
│                  │     │  Extraction           │     │  Fact Extraction          │
│  문서 → Chunk 분할│     │  (LLM 호출 1)          │     │  (LLM 호출 2)              │
└──────────────────┘     └──────────────────────┘     └──────────────────────────┘
     SentenceSplitter          복합문 → 원자적 명제          명제 → 토픽, 엔티티,
     (256자, overlap 20)       대명사 → 구체적 이름          관계, 진술, 사실
                               약어 → 전체 표현
```

**Stage 1: Chunking**
- 소스 문서를 chunk로 분할 (기본값: `SentenceSplitter`, chunk_size=256, overlap=20)
- 이미 chunk된 데이터라면 생략 가능

**Stage 2: Proposition Extraction** (LLM 호출 1)
- 비정형 콘텐츠에서 명제(proposition) 세트를 추출
- 복잡한 문장 → 단순한 문장으로 분리
- 대명사 → 구체적 이름, 약어 → 전체 표현으로 치환
- **선택 사항**: 생략 시 LLM 호출 감소, 대신 추출 품질 저하

**Stage 3: Topic/Entity/Statement/Fact Extraction** (LLM 호출 2)
- 추출된 명제에서 토픽, 진술, 사실, 엔티티 및 관계를 추출
- 선호하는 엔티티 분류 목록으로 시드 (가볍게 안내되는 전략)
- **커스텀 프롬프트**로 도메인 특화 가능 (예: ETF 온톨로지 적용)

### Build 단계

Extract에서 내보낸 chunk 노드를 개별 Source, Chunk, Topic, Statement, Fact 노드의 스트림으로 분해합니다.

- **Graph 구축 핸들러**: 그래프 스토어에 노드/엣지 생성
- **Vector 인덱싱 핸들러**: chunk와 statement 노드에 대한 임베딩 생성 및 인덱싱

### 커스텀 온톨로지 적용 (ExtractionConfig)

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex, IndexingConfig, ExtractionConfig

graph_index = LexicalGraphIndex(
    graph_store, vector_store,
    indexing_config=IndexingConfig(
        extraction=ExtractionConfig(
            # 도메인 특화 엔티티 분류 목록
            preferred_entity_classifications=["ETF", "Index", "Stock", ...],
            # 커스텀 추출 프롬프트
            extract_topics_prompt_template=CUSTOM_ETF_PROMPT,
        )
    )
)
graph_index.extract_and_build(documents)
```

| ExtractionConfig 파라미터 | 설명 | 기본값 |
|--------------------------|------|--------|
| `enable_proposition_extraction` | 명제 추출 수행 여부 | `True` |
| `preferred_entity_classifications` | 엔티티 분류 시드 목록 | 기본 분류 목록 |
| `extract_propositions_prompt_template` | 명제 추출 프롬프트 | 기본 템플릿 |
| `extract_topics_prompt_template` | 토픽/엔티티/관계 추출 프롬프트 | 기본 템플릿 |

---

## 3.4 Retrieval & Query Pipeline (질의)

쿼리는 **검색(Retrieval)** 과 **생성(Generation)** 의 2단계 프로세스입니다.

![Query Pipeline](./images/question-answering.png)

### 쿼리 단계

```
① 사용자 질문 제출
      │
      ▼
② 질문 임베딩 생성
      │
      ▼
③ Vector Store에서 topK 유사도 검색 (Chunk/Statement 임베딩 기반)
      │
      ▼
④ 검색 결과로 Graph Store에서 관련 콘텐츠 탐색 (그래프 순회)
      │    ├── Topic → 관련 Statement 그룹
      │    ├── Fact → 다른 소스의 관련 Statement
      │    └── Entity → 연결된 Fact/Statement
      ▼
⑤ 검색된 컨텍스트 + 사용자 질문 → LLM 응답 생성
      │
      ▼
⑥ 응답 반환
```

### Traversal-Based Search (권장 검색 전략)

lexical-graph의 구조적 특성(로컬/글로벌 연결 + Entity Network)을 활용하는 검색 방식입니다.

#### 3가지 Retriever

| Retriever | 동작 방식 | 연결 유형 | 결과 특성 |
|-----------|----------|----------|----------|
| **ChunkBasedSearch** | 벡터 유사도로 관련 chunk 찾기 → Topic/Statement/Fact 순회 | 로컬 중심 | 좁은 범위, 정확한 결과 |
| **EntityBasedSearch** | Entity Network 컨텍스트의 엔티티에서 출발 → Fact/Statement/Topic 순회 | 글로벌 중심 | 넓은 범위, 다양한 소스 |
| **EntityNetworkSearch** | Entity Network 전사(transcription)를 사용한 벡터 검색 → 질문과 **다르지만 관련된** 정보 탐색 | 로컬+글로벌 균형 | 유사하지 않은 관련 정보 발견 |

> **기본 설정**: `ChunkBasedSearch` + `EntityNetworkSearch` 조합
> → 질문과 유사한 콘텐츠 + "질문과 다른 무언가"에 대한 접근을 동시에 제공

#### 코드 예시

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory, VectorStoreFactory

graph_store  = GraphStoreFactory.for_graph_store('neptune-db://my-graph...')
vector_store = VectorStoreFactory.for_vector_store('aoss://https://my-aoss...')

# Traversal-based search 엔진 생성
query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, vector_store, streaming=True
)

# 쿼리 실행
response = query_engine.query("TIGER 미국S&P500의 주요 투자위험은?")
```

#### 검색 결과 구조

```json
{
  "source": "KR70000D0009_prospectus_0506c0d9.pdf",
  "topic": "TIGER 미국S&P500 투자위험",
  "statements": [
    "TIGER 미국S&P500 ETF는 환율변동위험이 있다",
    "이 투자신탁은 해외 자산에 투자하므로 환율 변동에 따른 손실이 발생할 수 있다",
    "환헤지를 실시하지 않는다"
  ]
}
```

각 Statement에는 점수, 뒷받침 Fact, 사용된 Retriever 정보가 메타데이터로 포함됩니다.

---

## 3.5 지원 스토어 및 설정

### Graph Store 옵션

| 스토어 | 연결 문자열 형식 | 특징 |
|--------|----------------|------|
| Neptune Database | `neptune-db://endpoint` | 관리형, OpenCypher, 안정적 |
| Neptune Analytics | `neptune-graph://graph-id` | 서버리스, 분석 최적화 |
| Neo4j | `bolt://host:port` | 자체 관리, Cypher |
| FalkorDB | `falkordb://host:port` | 경량, Redis 기반 |

### Vector Store 옵션

| 스토어 | 연결 문자열 형식 | 특징 |
|--------|----------------|------|
| OpenSearch Serverless | `aoss://https://endpoint` | 서버리스, 관리 불필요 |
| PostgreSQL pgvector | `postgresql://user:pass@host/db` | 기존 PG 활용 가능 |
| Neptune Analytics | 그래프 스토어와 동일 | 통합 스토어 |
| S3 Vectors | `s3vectors://bucket-name` | 대규모 임베딩 저장 |

### 기본 설정 예시

```python
from graphrag_toolkit.lexical_graph import GraphRAGConfig

# LLM 설정 (Amazon Bedrock)
GraphRAGConfig.extraction_llm = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
GraphRAGConfig.response_llm   = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
GraphRAGConfig.embedding_model = "amazon.titan-embed-text-v2:0"

# 리전 설정
GraphRAGConfig.aws_region = "ap-northeast-2"

# 성능 설정
GraphRAGConfig.extraction_num_workers = 2
GraphRAGConfig.extraction_num_threads_per_worker = 8
GraphRAGConfig.enable_cache = True
```
