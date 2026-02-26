[[Home](./)]

## Multi-Tenancy

### 목차

- [개요](#overview)
- [Tenant Id](#tenant-id)
- [인덱싱과 multi-tenancy](#indexing-and-multi-tenancy)
- [쿼리와 multi-tenancy](#querying-and-multi-tenancy)
- [구현 세부 사항](#implementation-details)

### 개요

Multi-tenancy를 사용하면 동일한 기본 graph 및 vector store에 여러 개의 별도 lexical graph를 호스팅할 수 있습니다.

### Tenant Id

Multi-tenancy 기능을 사용하려면 `LexicalGraphIndex` 또는 `LexicalGraphQueryEngine`을 생성할 때 tenant id를 제공해야 합니다. tenant id는 1-10개의 소문자와 숫자로 구성된 문자열입니다. tenant id를 제공하지 않으면 인덱스와 쿼리 엔진은 _기본 tenant_(즉, tenant id 값이 `None`)를 사용합니다.

### 인덱싱과 multi-tenancy

다음 예제는 tenant 'user123'에 대한 `LexicalGraphIndex`를 생성합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex

graph_store = ...
vector_store = ...

graph_index = LexicalGraphIndex(
    graph_store,
    vector_store,
    tenant_id='user123'
)
```

`LexicalGraphIndex`는 다른 tenant id를 제공하더라도 항상 [extract 단계](https://github.com/awslabs/graphrag-toolkit/blob/main/docs/indexing.md#extract)에서 _기본 tenant_를 사용합니다. 그러나 [build 단계](https://github.com/awslabs/graphrag-toolkit/blob/main/docs/indexing.md#build)에서는 tenant id를 사용합니다. 이는 한 번 추출한 다음 잠재적으로 다른 tenant에 대해 여러 번 구축할 수 있도록 하기 위함입니다.

### 쿼리와 multi-tenancy

다음 예제는 tenant 'user123'에 대한 `LexicalGraphQueryEngine`을 생성합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine

graph_store = ...
vector_store = ...

query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store,
    vector_store,
    tenant_id='user123'
)
```

지정된 tenant id에 대한 lexical graph가 존재하지 않는 경우, 기본 retriever는 빈 결과 집합을 반환합니다.

### 구현 세부 사항

Multi-tenancy는 그래프의 노드에 tenant별 노드 레이블을 사용하고, vector store에 tenant별 인덱스를 사용하여 작동합니다. 예를 들어, tenant 'user123'에 속하는 그래프의 chunk 노드는 `__Chunk__user123__`으로 레이블이 지정되고, chunk vector 인덱스는 `chunk_user123`으로 명명됩니다.
