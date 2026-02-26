[[Home](./)]

## FalkorDB를 Graph Store로 사용하기

### 목차

  - [개요](#overview)
  - [패키지 설치](#install-package)
  - [FalkorDB를 graph store로 등록하기](#registering-falkordb-as-a-graph-store)
  - [FalkorDB graph store 생성하기](#creating-a-falkordb-graph-store)

### 개요

FalkorDB를 graph store로 사용할 수 있습니다.

### 패키지 설치

FalkorDB graph store는 별도의 기여자 패키지에 포함되어 있습니다. 설치하려면:

```
!pip install https://github.com/awslabs/graphrag-toolkit/archive/refs/tags/v3.15.5.zip#subdirectory=lexical-graph-contrib/falkordb
```

### FalkorDB를 graph store로 등록하기

FalkorDB graph store를 생성하기 전에 `FalkorDBGraphStoreFactory`를 `GraphStoreFactory`에 등록해야 합니다:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit_contrib.lexical_graph.storage.graph.falkordb import FalkorDBGraphStoreFactory

GraphStoreFactory.register(FalkorDBGraphStoreFactory)

```

### FalkorDB graph store 생성하기

`GraphStoreFactory.for_graph_store()` 정적 팩토리 메서드를 사용하여 FalkorDB graph store 인스턴스를 생성할 수 있습니다.

FalkorDB graph store는 현재 [semantic-guided search](./semantic-guided-search.md)를 지원합니다. [traversal-based search](./traversal-based-search.md)는 지원하지 않습니다.

[FalkorDB Cloud](https://app.falkordb.cloud/) graph store를 생성하려면 `falkordb://`로 시작하는 연결 문자열 뒤에 FalkorDB 엔드포인트를 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit_contrib.lexical_graph.storage.graph.falkordb import FalkorDBGraphStoreFactory

falkordb_connection_info = 'falkordb://your-falkordb-endpoint'

GraphStoreFactory.register(FalkorDBGraphStoreFactory)

with GraphStoreFactory.for_graph_store(falkordb_connection_info) as graph_store:
  ...

```

사용자 이름과 비밀번호를 전달하고 SSL 사용 여부를 지정해야 할 수도 있습니다:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

falkordb_connection_info = 'falkordb://<your-falkordb-endpoint>'

with GraphStoreFactory.for_graph_store(
      falkordb_connection_info,
      username='<username>',
      password='<password>',
      ssl=True
  ) as graph_store:

    ...
```

로컬 FalkorDB graph store를 생성하려면 `falkordb://`만 포함하는 연결 문자열을 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

falkordb_connection_info = 'falkordb://'

with GraphStoreFactory.for_graph_store(falkordb_connection_info) as graph_store:
  ...
```
