# Finance GraphRAG — TIGER ETF Knowledge Graph

TIGER ETF 데이터 파이프라인 + AWS GraphRAG Toolkit을 활용한 금융 Knowledge Graph 구축

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
│  - Aurora PostgreSQL 저장                                │
└─────────────────────┬───────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2: GraphRAG (Knowledge Graph + Vector Index)      │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │ Bedrock LLM │    │ AWS Neptune  │    │ OpenSearch  │  │
│  │ Claude      │───▶│ Graph Store  │    │ Serverless  │  │
│  │ Sonnet      │    │ (Entity,Fact │    │ (Embedding  │  │
│  │             │    │  Relation)   │    │  Vector)    │  │
│  │ Titan Embed │───▶│              │    │             │  │
│  │ Text v2     │    └──────────────┘    └────────────┘  │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
```

## AWS Infrastructure

| 서비스 | 용도 | Writer/Reader 분리 |
|--------|------|--------------------|
| **Aurora PostgreSQL** | ETF 메타데이터 RDB | Writer + Reader 엔드포인트 |
| **Neptune Database** | Knowledge Graph (OpenCypher) | Writer + Reader 엔드포인트 |
| **OpenSearch Serverless** | Vector Embedding 저장/검색 | 단일 엔드포인트 |
| **Amazon Bedrock** | LLM (Claude Sonnet) + Embedding (Titan) | -- |
| **Secrets Manager** | Aurora PG 비밀번호 관리 | -- |

**엔드포인트 사용 규칙:**
- **Indexer / Scraper** → Writer 엔드포인트 (데이터 쓰기)
- **Query / Report** → Reader 엔드포인트 (조회 전용)
- Reader 미설정 시 자동으로 Writer로 fallback

## Project Structure

```
aos-neptune/
├── README.md
├── pyproject.toml              # 패키지 설정 + 의존성
├── config.yaml                 # GraphRAG/LLM/인프라 설정
├── .env.example                # 환경변수 템플릿
├── certs/
│   └── global-bundle.pem       # RDS SSL 인증서 (gitignore)
├── alembic/                    # DB 마이그레이션
├── docker/
│   └── graphrag/
│       └── docker-compose.yml  # 로컬 개발용 PostgreSQL
├── sql/
│   └── schema.sql              # ETF RDB 스키마
├── data/
│   ├── pdfs/                   # ETF PDF 문서 (gitignore)
│   └── excel/                  # 엑셀 데이터 (gitignore)
├── experiments/
│   ├── configs/                # 실험 설정 YAML
│   └── results/                # 실험 결과 JSON
├── tests/
└── src/tiger_etf/
    ├── cli.py                  # Click CLI
    ├── config.py               # Pydantic Settings + config.yaml
    ├── db.py                   # SQLAlchemy 엔진 (writer + reader)
    ├── models.py               # ORM 모델
    ├── graphrag/
    │   ├── indexer.py          # LexicalGraphIndex 빌드 + ETF 온톨로지
    │   ├── loader.py           # PDF/RDB → LlamaIndex Documents
    │   ├── query.py            # GraphRAG 질의 + Neptune 통계
    │   └── experiment.py       # 실험 프레임워크
    ├── parsers/                # HTML 파서
    └── scrapers/               # 웹 스크래퍼
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- AWS 계정 및 아래 서비스 접근 권한:
  - Amazon Bedrock (Claude Sonnet, Titan Embed Text v2)
  - Aurora PostgreSQL 클러스터
  - Neptune Database 클러스터
  - OpenSearch Serverless 컬렉션
  - Secrets Manager (RDS 비밀번호)

### 2. AWS 리소스 생성

#### 2-1. Aurora PostgreSQL 클러스터

1. **RDS → Create database** → Engine: Amazon Aurora → PostgreSQL-Compatible
2. **Templates**: Dev/Test (비용 절감)
3. **Settings**:
   - DB cluster identifier: `<your-cluster-name>`
   - Master username: `postgres`
   - Credentials management: **Managed in AWS Secrets Manager** (자동 비밀번호 생성)
4. **Instance configuration**: `db.t3.medium` 이상
5. **Connectivity**:
   - VPC: EC2와 동일한 VPC 선택
   - VPC security group: EC2 → RDS 간 포트 **5432** 인바운드 허용
6. **생성 후 확인**:
   - Writer endpoint: `<cluster>.cluster-xxx.<region>.rds.amazonaws.com`
   - Reader endpoint: `<cluster>.cluster-ro-xxx.<region>.rds.amazonaws.com`
   - Secrets Manager ARN (비밀번호 조회용)

> **유의사항**
> - SSL 연결 필수: `sslmode=verify-full`, `sslrootcert=certs/global-bundle.pem`
> - 비밀번호에 특수문자가 포함되므로 `.env`에 설정할 때 **URL-encode** 필요
> - EC2 보안그룹에서 RDS 보안그룹으로의 **아웃바운드 5432** 규칙도 확인

#### 2-2. Neptune Database 클러스터

1. **Neptune → Create database**
2. **Engine**: Neptune Database (Neptune Analytics 아님)
3. **DB cluster identifier**: `<your-cluster-name>`
4. **Instance class**: `db.t3.medium` (개발/테스트용)
5. **Connectivity**:
   - VPC: EC2와 동일한 VPC 선택
   - VPC security group: EC2 → Neptune 간 포트 **8182** 인바운드 허용
6. **생성 후 확인**:
   - Writer endpoint: `<cluster>.cluster-xxx.<region>.neptune.amazonaws.com`
   - Reader endpoint: `<cluster>.cluster-ro-xxx.<region>.neptune.amazonaws.com`

> **유의사항**
> - Neptune 보안그룹 **인바운드**: EC2 보안그룹에서 TCP **8182** 허용
> - EC2 보안그룹 **아웃바운드**: Neptune 보안그룹으로 TCP **8182** 허용 (아웃바운드가 제한적인 경우 누락하기 쉬움)
> - `db.t3.medium`에서는 동시 쓰기 트랜잭션 충돌(`ConcurrentModificationException`)이 발생할 수 있음 → `batch_writes_enabled=False` 권장
> - IAM 인증 사용 시 EC2 IAM 역할에 `neptune-db:*` 권한 필요

#### 2-3. OpenSearch Serverless 컬렉션

1. **OpenSearch → Serverless → Collections → Create collection**
2. **Collection type**: Vector search
3. **Collection name**: `<your-collection-name>`
4. **Network access**:
   - **VPC endpoint 생성**: EC2와 동일한 VPC/서브넷 선택
   - 또는 Public access (테스트용)
5. **Encryption**: AWS owned key (기본값)
6. **생성 후 확인**:
   - Endpoint: `https://<collection-id>.<region>.aoss.amazonaws.com`

> **유의사항 (중요)**
> - **Data access policy 필수**: 컬렉션 생성만으로는 데이터 접근 불가. 아래처럼 별도 정책 생성 필요:
>   ```bash
>   aws opensearchserverless create-access-policy \
>     --name <policy-name> --type data \
>     --policy '[{"Rules":[
>       {"ResourceType":"collection","Resource":["collection/<name>"],"Permission":["aoss:*"]},
>       {"ResourceType":"index","Resource":["index/<name>/*"],"Permission":["aoss:*"]}
>     ],"Principal":["arn:aws:iam::<account-id>:user/<username>"]}]'
>   ```
> - **VPC endpoint 보안그룹**: EC2 보안그룹에서 TCP **443** 인바운드 허용
> - **포트 주의**: AOSS는 **443** 포트만 지원. `aoss://` 프리픽스 사용 시 opensearch-py가 기본 포트 9200으로 접속을 시도하여 타임아웃 발생 → `.env`에서 `VECTOR_STORE=https://<endpoint>` 형식으로 설정

#### 보안그룹 체크리스트

| Source | Destination | Port | 용도 |
|--------|------------|------|------|
| EC2 SG (outbound) | RDS SG | 5432 | Aurora PG 접속 |
| EC2 SG (outbound) | Neptune SG | 8182 | Neptune 접속 |
| EC2 SG (outbound) | AOSS VPC Endpoint SG | 443 | OpenSearch Serverless 접속 |
| RDS SG (inbound) | EC2 SG | 5432 | Aurora PG 허용 |
| Neptune SG (inbound) | EC2 SG | 8182 | Neptune 허용 |
| AOSS VPC Endpoint SG (inbound) | EC2 SG | 443 | OpenSearch Serverless 허용 |

### 3. 프로젝트 설정

```bash
# 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# pip 업그레이드 + 의존성 설치
pip install --upgrade pip setuptools wheel
pip install -e .

# RDS SSL 인증서 다운로드
mkdir -p certs
curl -o certs/global-bundle.pem \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

# 환경변수 설정
cp .env.example .env
```

### 4. .env 설정

```bash
# Aurora PG 비밀번호 가져오기
aws secretsmanager get-secret-value \
  --secret-id '<your-secret-arn>' \
  --query SecretString --output text | jq -r '.password'

# 비밀번호를 URL-encode (특수문자 포함 시)
python3 -c "from urllib.parse import quote; print(quote('<password>', safe=''))"
```

`.env` 파일에 실제 엔드포인트를 설정:

```ini
# Aurora PostgreSQL (writer / reader)
DATABASE_URL=postgresql://postgres:<encoded-pw>@<writer-endpoint>:5432/mirae_etf?sslmode=verify-full&sslrootcert=certs/global-bundle.pem
DATABASE_URL_READER=postgresql://postgres:<encoded-pw>@<reader-endpoint>:5432/mirae_etf?sslmode=verify-full&sslrootcert=certs/global-bundle.pem

# Neptune Database (writer / reader)
GRAPH_STORE=neptune-db://<writer-endpoint>
GRAPH_STORE_READER=neptune-db://<reader-endpoint>

# OpenSearch Serverless
VECTOR_STORE=aoss://<collection-endpoint>

# AWS Region
GRAPHRAG_AWS_REGION=<your-region>
```

### 5. Configuration

설정 우선순위: **환경변수 > .env > config.yaml > 코드 기본값**

`config.yaml`에서 LLM 모델과 런타임 설정을 관리:

```yaml
graphrag:
  extraction_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  response_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  embedding_model: "amazon.titan-embed-text-v2:0"
  aws_region: "ap-northeast-2"
  extraction_num_workers: 1
  extraction_num_threads_per_worker: 8
  build_num_workers: 1            # Neptune 그래프 빌드 병렬 워커 수
  batch_writes_enabled: false     # Neptune batch write (t3.medium은 false 권장)
  enable_cache: true
```

> **Neptune 인스턴스 크기별 권장 설정**
> | 인스턴스 | `build_num_workers` | `batch_writes_enabled` | 비고 |
> |---------|--------------------|-----------------------|------|
> | db.t3.medium | 1 | false | ConcurrentModificationException 방지 |
> | db.r5.large 이상 | 2 | true | 기본 batch_write_size=25 |

### 6. ETF Data Scraping (Phase 1)

```bash
# DB 스키마 초기화
tiger-etf db init

# 전체 ETF 상품 목록 수집
tiger-etf scrape list

# 보유종목, 수익률, 분배금, PDF 다운로드
tiger-etf scrape holdings
tiger-etf scrape perf
tiger-etf scrape dist
tiger-etf scrape docs

# RDB 현황 확인
tiger-etf report summary
```

### 7. GraphRAG Indexing (Phase 2)

```bash
# PDF 5개로 테스트
tiger-etf graphrag build-pdf --limit 5

# 전체 소스(PDF + RDB)로 빌드
tiger-etf graphrag build

# 그래프 상태 확인
tiger-etf graphrag status

# GraphRAG 질의
tiger-etf graphrag query "TIGER 미국S&P500 ETF의 주요 투자위험은?"
```

### 8. Experiments

```bash
# 실험 설정 목록
tiger-etf experiment list

# 실험 실행 (설정 적용 → 인덱싱 → 메트릭 → 평가)
tiger-etf experiment run baseline_claude37_titan

# 실험 비교
tiger-etf experiment compare
```

## GraphRAG Pipeline Details

### Extraction Flow

```
PDF → PyMuPDF → LlamaIndex Documents
  → SentenceSplitter (256 chars, 25 overlap)
    → Step 1: Proposition Extraction (Bedrock LLM)
      → 원문을 atomic 명제로 분해
    → Step 2: Topic + Entity + Relation Extraction (Bedrock LLM)
      → ETF 도메인 온톨로지 기반 구조화된 추출
    → Step 3: Build (Neptune 그래프 + OpenSearch 임베딩 저장)
```

### ETF Domain Ontology

Entity extraction 품질을 높이기 위해 ETF 도메인 전용 온톨로지를 정의하여 LLM 프롬프트에 주입.

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
| Benchmark | 비교지수 | -- |
| Person | 인물 | 펀드매니저 |
| Derivative | 파생상품 | swap, option |

**Relationship Types (17종):**

`MANAGES`, `TRACKS`, `INVESTS_IN`, `LISTED_ON`, `REGULATED_BY`, `DISTRIBUTED_BY`, `TRUSTEED_BY`, `BENCHMARKED_AGAINST`, `BELONGS_TO_SECTOR`, `HAS_FEE`, `HAS_RISK`, `ISSUED_BY`, `LOCATED_IN`, `HOLDS`, `COMPONENT_OF`, `GOVERNED_BY`, `SUBSIDIARY_OF`

### Storage Architecture

| Store | Technology | Content |
|---|---|---|
| ETF RDB | Aurora PostgreSQL (writer/reader 분리) | ETF 상품, 보유종목, 분배금, 문서 메타데이터 |
| Graph Store | Neptune Database (OpenCypher, writer/reader 분리) | Entity, Fact, Statement, Topic 노드 + 관계 |
| Vector Store | OpenSearch Serverless | chunk/statement 텍스트 + 1024d Titan 임베딩 |

### Query Flow

```
질의 → Titan 임베딩 → OpenSearch 유사도 검색 (진입점)
  → Neptune Reader 그래프 순회 (관련 엔티티/팩트 확장)
    → Bedrock LLM (컨텍스트 기반 답변 생성)
```

## Tech Stack

- **Language**: Python 3.11
- **LLM**: Amazon Bedrock (Claude Sonnet — extraction + response)
- **Embedding**: Amazon Bedrock (Amazon Titan Embed Text v2, 1024d)
- **GraphRAG**: [AWS GraphRAG Toolkit](https://github.com/awslabs/graphrag-toolkit) v3.16.1 (Lexical Graph)
- **Graph DB**: AWS Neptune Database (OpenCypher, writer/reader 분리)
- **Vector DB**: AWS OpenSearch Serverless
- **RDB**: Aurora PostgreSQL + SQLAlchemy 2.0 (writer/reader 분리, SSL verify-full)
- **Secret Management**: AWS Secrets Manager
- **Configuration**: config.yaml + pydantic-settings (env var override)
- **CLI**: Click + Rich
