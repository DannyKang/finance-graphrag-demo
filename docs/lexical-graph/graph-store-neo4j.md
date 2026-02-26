[[Home](./)]

## Neo4j를 Graph Store로 사용하기

### 목차

  - [개요](#overview)
  - [Neo4j graph store 생성하기](#creating-a-neo4j-graph-store)

### 개요

[Neo4j](https://neo4j.com/docs)를 graph store로 사용할 수 있습니다.

### Neo4j graph store 생성하기

`GraphStoreFactory.for_graph_store()` 정적 팩토리 메서드를 사용하여 Neo4j graph store 인스턴스를 생성하세요.

Neo4j graph store를 생성하려면 다음 형식에 따라 [Neo4j URI 스킴](https://neo4j.com/docs/api/python-driver/5.28/api.html#uri)(예: `neo4j://`) 중 하나로 시작하는 연결 문자열을 제공하세요:

```
[scheme]://[user[:password]@][host][:port][/dbname][?routing_context]
```

예를 들어:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

neo4j_connection_info = 'neo4j://neo4j:!zfg%dGGh@example.com:7687'

with GraphStoreFactory.for_graph_store(neo4j_connection_info) as graph_store:
    ...
```
