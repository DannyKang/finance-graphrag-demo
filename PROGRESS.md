# 마이그레이션 진행 기록

## 2026-02-25: 코드베이스 정리 — neo4j/pgvector 잔여 코드 완전 제거

### 완료된 작업

#### 코드 변경
- `cli.py` — "Neo4j" 문자열 → "Neptune" 으로 변경, experiment docstring 정리
- `pyproject.toml` — `neo4j>=5.0` 의존성 제거, `opensearch-py>=2.4` 추가
- `docker-compose.yml` — Neo4j/pgvector/NeoDash 컨테이너 전체 제거, 로컬 개발용 PostgreSQL만 유지
- `neodash-queries.cypher` — 삭제 (NeoDash 사용 중단)
- `.gitignore` — neo4j_data/graphrag_pg_data 볼륨 경로 제거

#### 문서 재작성
- `README.md` — 아키텍처 다이어그램, Quick Start, Storage Architecture, Tech Stack 모두 Neptune/OpenSearch 기준으로 전면 재작성
- `CLAUDE.md` — "현재 스택 (변경 전)"/"목표 스택" 구분 제거, 현재 스택(Neptune/OpenSearch)으로 통합
- `ANALYSIS.md` — 마이그레이션 완료 후 구조 분석으로 재작성

---

## 2026-02-22: pgvector/neo4j → OpenSearch/Neptune 마이그레이션

### 완료된 작업

#### 1. config.yaml 기반 설정 체계 구축
- `config.yaml` 생성 (프로젝트 루트)
- `config.py` — pydantic-settings custom source 패턴으로 재작성
- 설정 우선순위: 환경변수 > .env > config.yaml > 코드 기본값

#### 2. Vector DB: pgvector → OpenSearch Serverless
- 연결 문자열 변경: `postgresql://...` → `aoss://...`
- `graphrag_toolkit`의 `OpenSearchVectorIndexFactory`가 자동 감지

#### 3. Graph DB: neo4j → Neptune
- 연결 문자열 변경: `bolt://...` → `neptune-graph://...`
- `get_graph_stats()` — boto3 Neptune 클라이언트(OpenCypher)로 재작성

#### 4. LLM 모델명 관리
- `config.yaml`의 `graphrag:` 섹션에서 관리하도록 변경

#### 5. experiment.py 정리
- Docker 컨테이너 관리 코드 전체 제거

### 테스트 결과
```
12 passed in 0.19s
```

### 다음 단계
- Neptune 그래프 인스턴스 ID를 `.env` / `config.yaml`에 실제 값으로 설정
- OpenSearch Serverless 컬렉션 엔드포인트를 실제 값으로 설정
- 실제 인프라 연결 후 통합 테스트 실행
