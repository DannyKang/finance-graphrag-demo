[[Home](./)]

## Neptune Database를 Graph Store로 사용하기

### 목차

  - [개요](#overview)
  - [Neptune Database graph store 생성하기](#creating-a-neptune-database-graph-store)
    - [프록시를 통해 Neptune에 연결하기](#connecting-to-neptune-via-a-proxy)

### 개요

Amazon Neptune Database를 graph store로 사용할 수 있습니다. lexical-graph는 [Neptune 엔진 버전](https://docs.aws.amazon.com/neptune/latest/userguide/engine-releases.html) 1.4.1.0 이상이 필요합니다.

### Neptune Database graph store 생성하기

`GraphStoreFactory.for_graph_store()` 정적 팩토리 메서드를 사용하여 Neptune Database graph store 인스턴스를 생성하세요.

Neptune Database graph store(엔진 버전 1.4.1.0 이상)를 생성하려면 `neptune-db://`로 시작하는 연결 문자열 뒤에 [엔드포인트](https://docs.aws.amazon.com/neptune/latest/userguide/feature-overview-endpoints.html)를 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

neptune_connection_info = 'neptune-db://mydbcluster.cluster-123456789012.us-east-1.neptune.amazonaws.com:8182'

with GraphStoreFactory.for_graph_store(neptune_connection_info) as graph_store:
    ...
```

#### 프록시를 통해 Neptune에 연결하기

프록시(예: 로드 밸런서)를 통해 Neptune에 연결하려면, `GraphStoreFactory.for_graph_store()` 팩토리 메서드에 프로토콜 또는 엔드포인트별 프록시 서버의 `proxies` 딕셔너리가 포함된 config 딕셔너리를 제공해야 합니다:

```python
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory

neptune_connection_info = 'neptune-db://mydbcluster.cluster-123456789012.us-east-1.neptune.amazonaws.com:8182'

config = {
    'proxies': {
        'http': 'http://proxy-hostname:80'
    }
}

with GraphStoreFactory.for_graph_store(
        neptune_connection_info,
        config=config
    ) as graph_store:
    ...
```
