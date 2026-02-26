# 프로젝트 구조 분석 (마이그레이션 완료 후)

## 1. 전체 디렉토리 구조

```
aos-neptune/
├── src/tiger_etf/
│   ├── __init__.py
│   ├── cli.py                  # Click CLI 엔트리포인트
│   ├── config.py               # pydantic-settings + YamlSettingsSource
│   ├── db.py                   # SQLAlchemy 엔진/세션 관리
│   ├── models.py               # ORM 모델 (EtfProduct, EtfHolding, etc.)
│   ├── graphrag/
│   │   ├── __init__.py
│   │   ├── indexer.py          # LexicalGraphIndex 빌드 (ETF 도메인 온톨로지 포함)
│   │   ├── loader.py           # PDF/RDB 데이터를 LlamaIndex Document로 변환
│   │   ├── query.py            # LexicalGraphQueryEngine 쿼리 + Neptune 통계 조회
│   │   └── experiment.py       # 실험 프레임워크 (설정 비교, 메트릭 수집)
│   ├── parsers/                # HTML 파서 (list_parser, detail_parser)
│   ├── scrapers/               # 미래에셋 웹사이트 스크레이퍼 6종
│   └── utils/                  # 로깅 설정
├── config.yaml                 # 프로젝트 설정 (graph_store, vector_store, LLM)
├── experiments/
│   ├── configs/                # 실험 설정 YAML
│   └── results/                # 실험 결과 JSON
├── tests/                      # 테스트
├── docker/graphrag/
│   └── docker-compose.yml      # 로컬 개발용 PostgreSQL
├── data/pdfs/                  # ETF 투자설명서 PDF
├── sql/schema.sql
├── alembic/                    # DB 마이그레이션
├── pyproject.toml
└── .env / .env.example
```

## 2. 스토어 연결 구성

### Graph Store — AWS Neptune
- **설정**: `config.yaml` → `graph_store: "neptune-graph://<graph-id>"` 또는 `"neptune-db://<endpoint>"`
- **팩토리**: `graphrag_toolkit`의 `GraphStoreFactory`가 연결 문자열 prefix로 자동 감지
- **인덱싱/쿼리**: `indexer.py`, `query.py`에서 `GraphStoreFactory.for_graph_store()` 호출
- **직접 접근**: `query.py`의 `get_graph_stats()`에서 boto3 Neptune 클라이언트로 OpenCypher 쿼리

### Vector Store — AWS OpenSearch Serverless
- **설정**: `config.yaml` → `vector_store: "aoss://<endpoint>"`
- **팩토리**: `graphrag_toolkit`의 `VectorStoreFactory`가 연결 문자열 prefix로 자동 감지
- **인덱싱/쿼리**: `indexer.py`, `query.py`에서 `VectorStoreFactory.for_vector_store()` 호출

### RDB — Aurora PostgreSQL
- **설정**: `config.yaml` → `database_url` 또는 `.env` → `DATABASE_URL`
- **연결**: `db.py`에서 SQLAlchemy 엔진 생성

## 3. LLM 모델 설정

- **설정 위치**: `config.yaml`의 `graphrag:` 섹션
- **적용 코드**: `indexer.py:_configure()`, `query.py:get_query_engine()`, `experiment.py:_apply_config()`
- **설정 우선순위**: 환경변수 > .env > config.yaml > 코드 기본값

```yaml
graphrag:
  extraction_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  response_llm: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  embedding_model: "cohere.embed-multilingual-v3"
```
