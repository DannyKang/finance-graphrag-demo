# mirae-graphrag 프로젝트 컨텍스트

## 프로젝트 구조
- 언어: Python
- 패키지 관리: pyproject.toml
- 주요 모듈: src/tiger_etf/graphrag/
- 설정: config.yaml + .env (pydantic-settings, 환경변수 > .env > config.yaml > 기본값)

## 현재 스택
- RDB: Aurora PostgreSQL
- Vector DB: AWS OpenSearch Serverless (`aoss://` 연결 문자열)
- Graph DB: AWS Neptune (`neptune-graph://` 또는 `neptune-db://` 연결 문자열)
- Entity Extraction LLM: config.yaml의 `graphrag.extraction_llm`으로 관리
- Embedding: Amazon Titan Embed Text v2 (Amazon Bedrock)
- GraphRAG 프레임워크: AWS graphrag-toolkit-lexical-graph v3.16.1

## 주요 파일
- `config.yaml` — 인프라/LLM 설정 (프로젝트 루트)
- `src/tiger_etf/config.py` — YamlSettingsSource + pydantic-settings
- `src/tiger_etf/graphrag/indexer.py` — LexicalGraphIndex 빌드 + ETF 도메인 온톨로지
- `src/tiger_etf/graphrag/query.py` — 질의 엔진 + Neptune 통계 (boto3)
- `src/tiger_etf/graphrag/experiment.py` — 실험 프레임워크

## 작업 원칙
- 절대 작업 중간에 승인을 구하지 말 것
- 에러 발생 시 스스로 원인 파악 후 수정하고 계속 진행
- 모르는 부분은 기존 코드 패턴을 참고해서 판단
- 테스트 작성 후 통과까지 완료해야 작업 완료
- 작업 완료 후 PROGRESS.md에 결과 기록
