[[Home](./)]

## Neptune Analytics를 Graph Store로 사용하기

### 목차

  - [개요](#overview)
  - [Neptune Analytics graph store 생성하기](#creating-a-neptune-analytics-graph-store)

### 개요

Amazon Neptune Analytics를 graph store로 사용할 수 있습니다.

### Neptune Analytics graph store 생성하기

`GraphStoreFactory.for_graph_store()` 정적 팩토리 메서드를 사용하여 Neptune Analytics graph store 인스턴스를 생성하세요.

Neptune Analytics graph store를 생성하려면 `neptune-graph://`로 시작하는 연결 문자열 뒤에 그래프 식별자를 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

neptune_connection_info = 'neptune-graph://g-jbzzaqb209'

with GraphStoreFactory.for_graph_store(neptune_connection_info) as graph_store:
    ...
```
