# AWS GraphRAG Toolkit 가이드

## 정보
- 대상: AWS GraphRAG Toolkit을 활용한 지식 그래프 구축에 관심 있는 고객

## 목차

### [1. GraphRAG 개요](01-graphrag-overview-v2.md)
- 1.1 GraphRAG란? (기존 RAG 대비 장점)
- 1.2 GraphRAG의 여러 구현 방법
- 2.1 Graph Pattern — RDF vs Property Graph
- 2.2 Lexical Graph란? (graphrag.com 기반 설명 + 이미지)

### [2. AWS GraphRAG Toolkit](02-aws-graphrag-toolkit-v2.md)
- 3.1 개요 및 아키텍처
- 3.2 3-Tier Lexical Graph 구조 (이미지 포함)
- 3.3 Extraction & Build Pipeline (상세 설명)
- 3.4 Retrieval & Query Pipeline (Traversal-based Search)
- 3.5 지원 스토어 및 설정

### [3. 실제 구현 예제: TIGER ETF GraphRAG](03-implementation-example-v3.md)
- 4.1 시스템 구성 (Neptune DB + OpenSearch Serverless + Aurora PG)
- 4.2 도메인 온톨로지 설계 (17 엔티티 / 17 관계)
- 4.3 데이터 흐름: PDF/RDB에서 Entity Extraction까지 (소스 코드 포함)
- 4.4 3-Tier 그래프 저장 예시 (Lineage / Entity-Relation / Summary)
- 4.5 질의 예시 (Traversal-based Search)
- 4.6 핵심 코드 구조 및 소스 코드 예시
- 4.7 구축 결과 요약

### [4. Query Routing: Intent 기반 검색 채널 선택](04-query-routing-v2.md)
- 5.1 문제: 단일 검색 경로의 한계
- 5.2 Query Routing 아키텍처
- 5.3 Intent 분류 체계 (8종)
- 5.4 3-Channel Hybrid Retrieval (RDB Text2SQL / Graph Traversal / Vector Search)
- 5.5 Query Router Agent 구현
- 5.6 질문별 라우팅 경로 예시
- 5.7 쿼리 분해 (Query Decomposition)
- 5.8 아키텍처 요약

