# 마이그레이션 구현 계획

## 핵심 발견

`graphrag_toolkit` (v3.16.1)이 이미 Neptune과 OpenSearch Serverless를 네이티브 지원한다.
- Neptune: `neptune-graph://<graph-id>` 또는 `neptune-db://<endpoint>` 연결 문자열만 전달하면 자동 감지
- OpenSearch Serverless: `aoss://<endpoint>` 연결 문자열만 전달하면 자동 감지
- Neo4jGraphStoreFactory 수동 등록이 불필요해짐 (Neptune은 기본 등록됨)

따라서 **커스텀 클라이언트 래퍼를 만들 필요 없이**, 설정값만 변경하면 된다.

---

## 1. 변경할 파일 목록

| 파일 | 변경 이유 |
|------|-----------|
| `src/tiger_etf/config.py` | pydantic-settings → config.yaml 로딩으로 전환. graph_store/vector_store 기본값을 Neptune/OpenSearch로 변경 |
| `src/tiger_etf/graphrag/indexer.py` | Neo4jGraphStoreFactory 등록 제거. settings에서 값 읽는 방식 유지 |
| `src/tiger_etf/graphrag/query.py` | Neo4jGraphStoreFactory 등록 제거. `get_graph_stats()` Neptune용으로 재작성 |
| `src/tiger_etf/graphrag/experiment.py` | Docker 컨테이너 관리 로직 제거 (managed service). 스토어 생성 코드에서 Neo4j 제거 |
| `.env.example` | Neptune/OpenSearch 연결 문자열 예시로 업데이트 |

## 2. 새로 생성할 파일 목록

| 파일 | 용도 |
|------|------|
| `config.yaml` | 프로젝트 루트 설정 파일 (graph_store, vector_store, LLM 모델명 등) |
| `tests/test_config.py` | config.yaml 로딩 테스트 |
| `tests/test_graphrag_stores.py` | Neptune/OpenSearch 연결 문자열 팩토리 테스트 |

## 3. config.yaml 스키마 설계

```yaml
# 인프라 설정
graph_store: "neptune-graph://<graph-id>"     # Neptune Analytics
# graph_store: "neptune-db://<endpoint>"       # Neptune Database (대안)
vector_store: "aoss://<endpoint>"              # OpenSearch Serverless

# LLM 모델 설정 (AWS Bedrock 모델 ID)
graphrag:
  extraction_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  response_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  embedding_model: "cohere.embed-multilingual-v3"
  aws_region: "us-east-1"
  extraction_num_workers: 1
  extraction_num_threads_per_worker: 8
  enable_cache: true

# RDB 설정 (ETF 메타데이터용, 변경 없음)
database_url: "postgresql://user:password@localhost:5432/mirae_etf"

# 스크레이퍼 설정
scraper:
  base_url: "https://investments.miraeasset.com/tigeretf"
  request_delay: 1.0
  max_retries: 3

# 일반
log_level: "INFO"
data_dir: "./data"
```

## 4. OpenSearch 클라이언트 인터페이스 설계

**커스텀 클라이언트 불필요.** graphrag_toolkit의 `OpenSearchVectorIndexFactory`가 처리.
- 연결 문자열: `aoss://<endpoint>` → 팩토리가 자동 감지
- AWS SigV4 인증: boto3 세션에서 자동 처리
- 인덱스 생성/검색: 라이브러리 내부에서 처리

## 5. Neptune 클라이언트 인터페이스 설계

**커스텀 클라이언트 불필요 (인덱싱/쿼리용).** graphrag_toolkit의 `NeptuneAnalyticsGraphStoreFactory` 또는 `NeptuneDatabaseGraphStoreFactory`가 처리.

**예외: `get_graph_stats()`** — 직접 Neptune 쿼리 필요:
- Neptune Analytics: boto3 `neptune-graph` 클라이언트로 OpenCypher 쿼리
- Neptune Database: boto3 `neptunedata` 클라이언트로 OpenCypher 쿼리
- graph_store 연결 문자열에서 타입(analytics/database) 자동 판별

## 6. 기존 pgvector/neo4j 코드 처리

**제거한다.** 추상화 레이어로 남기지 않는다.
- Neo4jGraphStoreFactory 수동 등록 코드 삭제
- `neo4j` Python 패키지 직접 import 코드 삭제 (`get_graph_stats()`)
- Docker 컨테이너 관리 코드 삭제 (experiment.py) — Neptune/OpenSearch는 managed service
- pgvector 연결 문자열 기본값 제거

## 7. 작업 순서

```
Step 1: config.yaml 생성 + config.py 수정
         (모든 모듈이 의존하는 설정 레이어)
         ↓
Step 2: indexer.py 수정
         (Neo4j 등록 제거, config에서 설정 로딩)
         ↓
Step 3: query.py 수정
         (Neo4j 등록 제거, get_graph_stats() Neptune용 재작성)
         ↓
Step 4: experiment.py 수정
         (Docker 관리 제거, 스토어 코드 정리)
         ↓
Step 5: .env.example 업데이트
         ↓
Step 6: 테스트 작성 + 실행
         ↓
Step 7: PROGRESS.md 기록
```
