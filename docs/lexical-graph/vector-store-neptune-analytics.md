[[Home](./)]

## Neptune Analytics를 Vector Store로 사용하기

### 목차

  - [개요](#overview)
  - [Neptune Analytics vector store 생성하기](#creating-a-neptune-analytics-vector-store)

### 개요

Amazon Neptune Analytics를 vector store로 사용할 수 있습니다.

### Neptune Analytics vector store 생성하기

`VectorStoreFactory.for_vector_store()` 정적 팩토리 메서드를 사용하여 Amazon Neptune Analytics vector store 인스턴스를 생성하세요.

Neptune Analytics vector store를 생성하려면 `neptune-graph://`로 시작하는 연결 문자열 뒤에 그래프 식별자를 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

neptune_connection_info = 'neptune-graph://g-jbzzaqb209'

with VectorStoreFactory.for_vector_store(neptune_connection_info) as vector_store:
    ...
```
