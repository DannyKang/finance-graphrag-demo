# Finance GraphRAG Demo

TIGER ETF 데이터 파이프라인 + AWS GraphRAG Toolkit을 활용한 금융 Knowledge Graph 구축 데모

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 미래에셋 ETF  │  │  PDF 문서     │  │  RDB 데이터   │  │
│  │ 웹사이트      │  │ (투자설명서)  │  │ (상품/보유종목)│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼─────────────────┼─────────────────┼──────────┘
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1: ETF Data Pipeline (Scraper + RDB)             │
│  - 221개 TIGER ETF 상품 정보 수집                        │
│  - 보유종목, 수익률, 분배금, PDF 문서 다운로드             │
│  - PostgreSQL RDB 저장                                   │
└─────────────────────┬───────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2: GraphRAG (Knowledge Graph + Vector Index)      │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │ Bedrock LLM │    │   Neo4j      │    │ PostgreSQL │  │
│  │ Claude 3.7  │───▶│ Graph Store  │    │ pgvector   │  │
│  │ Sonnet      │    │ (Entity,Fact │    │ (Embedding │  │
│  │             │    │  Relation)   │    │  Vector)   │  │
│  │ Cohere Embed│───▶│              │    │            │  │
│  │ Multilingual│    └──────────────┘    └────────────┘  │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
mirae-claude/
├── README.md
├── pyproject.toml              # 패키지 설정 + 의존성
├── .env.example                # 환경변수 템플릿
├── .gitignore
├── alembic.ini                 # DB 마이그레이션 설정
├── alembic/
│   ├── env.py
│   └── script.py.mako
├── docker/
│   └── graphrag/
│       ├── docker-compose.yml  # Neo4j + pgvector + NeoDash
│       └── neodash-queries.cypher
├── sql/
│   └── schema.sql              # ETF RDB 스키마
├── data/
│   ├── pdfs/                   # 887개 ETF PDF 문서 (gitignore)
│   └── excel/                  # 엑셀 데이터 (gitignore)
└── src/tiger_etf/
    ├── cli.py                  # Click CLI (scrape, report, graphrag)
    ├── config.py               # Pydantic Settings
    ├── db.py                   # SQLAlchemy 엔진
    ├── models.py               # ORM 모델 (EtfProduct, EtfHolding 등)
    ├── graphrag/
    │   ├── indexer.py          # LexicalGraphIndex 빌드 + ETF 온톨로지
    │   ├── loader.py           # PDF/RDB → LlamaIndex Documents
    │   └── query.py            # GraphRAG 질의 엔진
    ├── parsers/                # HTML 파서
    └── scrapers/               # 웹 스크래퍼
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Docker Compose v2+
- AWS credentials (Bedrock access: Claude 3.7 Sonnet, Cohere Embed)
- PostgreSQL (ETF RDB용, port 5432)

### 2. Setup

```bash
# 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -e .

# 환경변수 설정
cp .env.example .env
# .env 파일에서 DATABASE_URL, AWS credentials 등 수정

# Docker 컨테이너 시작 (Neo4j + pgvector + NeoDash)
docker compose -f docker/graphrag/docker-compose.yml up -d

# PostgreSQL에 vector extension + schema 생성
PGPASSWORD=graphragpass psql -h localhost -p 5433 -U graphrag -d graphrag_db \
  -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE SCHEMA IF NOT EXISTS graphrag;"
```

### 3. ETF Data Scraping (Phase 1)

```bash
# 전체 ETF 상품 목록 수집
tiger-etf scrape products

# 보유종목, 수익률, 분배금, PDF 다운로드
tiger-etf scrape holdings
tiger-etf scrape performance
tiger-etf scrape distributions
tiger-etf scrape documents

# RDB 현황 확인
tiger-etf report summary
```

### 4. GraphRAG Indexing (Phase 2)

```bash
# PDF 5개로 테스트
tiger-etf graphrag build-pdf --limit 5

# PDF 50개로 테스트
tiger-etf graphrag build-pdf --limit 50

# 그래프 상태 확인
tiger-etf graphrag status

# GraphRAG 질의
tiger-etf graphrag query "TIGER NVDA-UST ETF의 주요 투자위험은?"
```

### 5. Visualization

- **Neo4j Browser**: http://\<host\>:7476 (bolt://localhost:7689, neo4j/password)
- **NeoDash**: http://\<host\>:5005

## GraphRAG Pipeline Details

### Extraction Flow

```
PDF → PyMuPDF → LlamaIndex Documents
  → SentenceSplitter (256 chars, 25 overlap)
    → Step 1: Proposition Extraction (Claude 3.7 Sonnet)
      → 원문을 atomic 명제로 분해
    → Step 2: Topic + Entity + Relation Extraction (Claude 3.7 Sonnet)
      → ETF 도메인 온톨로지 기반 구조화된 추출
    → Step 3: Build (Neo4j 그래프 + pgvector 임베딩 저장)
```

### ETF Domain Ontology

Entity extraction 품질을 높이기 위해 ETF 도메인 전용 온톨로지를 정의하여 LLM 프롬프트에 강제합니다.

**Entity Classifications (17종):**

| Classification | 설명 | 예시 |
|---|---|---|
| ETF | ETF 상품 | TIGER NVDA-UST 커버드콜 |
| Asset Management Company | 자산운용사 | 미래에셋자산운용 |
| Index | 추적 지수 | S&P 500, KEDI |
| Stock | 개별 종목 | NVIDIA, Apple |
| Bond | 채권 | US Treasury |
| Exchange | 거래소 | 한국거래소 |
| Regulatory Body | 규제기관 | 금융위원회 |
| Regulation | 법률/규정 | 자본시장법 |
| Trustee | 수탁회사 | 한국씨티은행 |
| Distributor | 판매회사 | 증권사, 은행 |
| Sector | 업종/섹터 | 반도체, IT |
| Country | 투자 국가 | 미국, 한국 |
| Risk Factor | 위험 요소 | 환율위험 |
| Fee | 수수료/비용 | 총보수 |
| Benchmark | 비교지수 | — |
| Person | 인물 | 펀드매니저 |
| Derivative | 파생상품 | swap, option |

**Relationship Types (17종):**

`MANAGES`, `TRACKS`, `INVESTS_IN`, `LISTED_ON`, `REGULATED_BY`, `DISTRIBUTED_BY`, `TRUSTEED_BY`, `BENCHMARKED_AGAINST`, `BELONGS_TO_SECTOR`, `HAS_FEE`, `HAS_RISK`, `ISSUED_BY`, `LOCATED_IN`, `HOLDS`, `COMPONENT_OF`, `GOVERNED_BY`, `SUBSIDIARY_OF`

### Storage Architecture

| Store | Technology | Port | Content |
|---|---|---|---|
| ETF RDB | PostgreSQL | 5432 | 221 상품, 14,697 보유종목, 887 문서 |
| Graph Store | Neo4j 5 Community | 7689 (bolt), 7476 (http) | Entity, Fact, Statement, Topic 노드 + 관계 |
| Vector Store | PostgreSQL + pgvector | 5433 | chunk/statement 텍스트 + 1024d Cohere 임베딩 |

### Query Flow

```
질의 → Cohere 임베딩 → pgvector 유사도 검색 (진입점)
  → Neo4j 그래프 순회 (관련 엔티티/팩트 확장)
    → Claude 3.7 Sonnet (컨텍스트 기반 답변 생성)
```

## Experiment Log

### v0.1.0 — 기본 GraphRAG 파이프라인 구축

- ETF 웹 스크래핑 파이프라인 (Phase 1)
- AWS GraphRAG Toolkit (Lexical Graph) v3.16.1 통합
- Docker 기반 Neo4j + pgvector + NeoDash 환경
- ETF 도메인 온톨로지 (17 entity classes, 17 relation types)
- 커스텀 Topic Extraction 프롬프트 (한국어 ETF 도메인 특화)
- 50개 PDF 인덱싱 테스트: ~127K 노드, ~998 sources

## Tech Stack

- **Language**: Python 3.11
- **LLM**: Amazon Bedrock — Claude 3.7 Sonnet (extraction + response)
- **Embedding**: Amazon Bedrock — Cohere Embed Multilingual v3 (1024d)
- **GraphRAG**: [AWS GraphRAG Toolkit](https://github.com/awslabs/graphrag-toolkit) v3.16.1 (Lexical Graph)
- **Graph DB**: Neo4j 5 Community + APOC
- **Vector DB**: PostgreSQL 16 + pgvector
- **RDB**: PostgreSQL 15 + SQLAlchemy 2.0
- **Visualization**: NeoDash, Neo4j Browser
- **CLI**: Click + Rich
