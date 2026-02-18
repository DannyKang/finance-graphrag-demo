// =============================================================
// NeoDash Dashboard Queries - TIGER ETF GraphRAG Lexical Graph
// =============================================================
// NeoDash (http://localhost:5005) 접속 후 위젯 추가 시 사용
// 접속 정보: bolt://localhost:7689, neo4j/password
// =============================================================

// ----- 1. 그래프 전체 통계 (Table) -----
MATCH (n)
RETURN labels(n)[0] AS Label, count(n) AS Count
ORDER BY Count DESC;

// ----- 2. 엔티티 클래스 분포 (Bar Chart) -----
MATCH (e:__Entity__)
RETURN e.class AS Class, count(*) AS Count
ORDER BY Count DESC
LIMIT 15;

// ----- 3. 상위 관계 유형 (Pie Chart) -----
MATCH (:__Entity__)-[r:__RELATION__]->(:__Entity__)
RETURN r.value AS Relation, count(*) AS Count
ORDER BY Count DESC
LIMIT 12;

// ----- 4. 가장 많이 언급된 엔티티 Top 20 (Bar Chart) -----
MATCH (e:__Entity__)-[:__SUBJECT__|__OBJECT__]-(f:__Fact__)
RETURN e.value AS Entity, e.class AS Class, count(f) AS Mentions
ORDER BY Mentions DESC
LIMIT 20;

// ----- 5. 토픽별 Statement 수 (Bar Chart) -----
MATCH (t:__Topic__)<-[:__BELONGS_TO__]-(s:__Statement__)
RETURN t.value AS Topic, count(s) AS Statements
ORDER BY Statements DESC
LIMIT 15;

// ----- 6. ETF 엔티티 네트워크 (Graph) -----
MATCH path = (e1:__Entity__)-[r:__RELATION__]->(e2:__Entity__)
WHERE e1.class = 'Financial Instrument' OR e2.class = 'Financial Instrument'
RETURN path
LIMIT 80;

// ----- 7. 특정 ETF 중심 관계 탐색 (Graph) -----
MATCH path = (e:__Entity__)-[:__RELATION__*1..2]-(n:__Entity__)
WHERE e.value CONTAINS 'TIGER'
RETURN path
LIMIT 100;

// ----- 8. 회사-ETF 관계 (Graph) -----
MATCH path = (c:__Entity__)-[r:__RELATION__]->(f:__Entity__)
WHERE c.class = 'Company' AND f.class = 'Financial Instrument'
RETURN path
LIMIT 80;

// ----- 9. 관계 유형별 Subject -> Object 샘플 (Table) -----
MATCH (e1:__Entity__)-[r:__RELATION__]->(e2:__Entity__)
RETURN e1.value AS Subject, r.value AS Relation, e2.value AS Object,
       e1.class AS SubjectClass, e2.class AS ObjectClass
ORDER BY r.value
LIMIT 50;

// ----- 10. PDF 소스별 추출 규모 (Bar Chart) -----
MATCH (s:__Source__)<-[:__EXTRACTED_FROM__]-(c:__Chunk__)<-[:__MENTIONED_IN__]-(st:__Statement__)
RETURN s.file_name AS Source,
       count(DISTINCT st) AS Statements,
       count(DISTINCT c) AS Chunks
ORDER BY Statements DESC;

// ----- 11. 투자 관계 네트워크 (Graph) -----
MATCH path = (e1:__Entity__)-[r:__RELATION__]->(e2:__Entity__)
WHERE r.value IN ['INVESTS IN', 'TRACKS', 'MANAGES', 'ISSUES']
RETURN path
LIMIT 100;

// ----- 12. Fact에서 추출한 지식 트리플 (Table) -----
MATCH (subj:__Entity__)<-[:__SUBJECT__]-(f:__Fact__)-[:__OBJECT__]->(obj:__Entity__)
RETURN subj.value AS Subject, f.value AS Predicate, obj.value AS Object, subj.class AS SubjClass
ORDER BY subj.value
LIMIT 50;
