[[Home](./)]

## 스토리지 모델

### 주제

- [개요](#overview)
- [Graph store](#graph-store)
  - [그래프 쿼리 로깅](#logging-graph-queries)
- [Vector store](#vector-store)

### 개요

lexical-graph는 두 개의 별도 스토어를 사용합니다: `GraphStore`와 `VectorStore`. `VectorStore`는 `VectorIndex` 컬렉션의 컨테이너 역할을 합니다. 그래프를 구축하거나 쿼리할 때 graph store와 vector store의 인스턴스를 모두 제공해야 합니다.

이 툴킷은 [Amazon Neptune Analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html)와 [Amazon Neptune Database](https://docs.aws.amazon.com/neptune/latest/userguide/intro.html) (엔진 버전 1.4.1.0 이상), 그리고 [FalkorDB](https://docs.falkordb.com/)에 대한 graph store 구현과 Neptune Analytics, [Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html) 및 pgvector 확장이 포함된 Postgres에 대한 vector store 구현을 제공합니다. lexical-graph는 이러한 스토어의 인스턴스를 생성하기 위한 여러 편리한 팩토리 메서드를 제공합니다.

> 이 툴킷의 초기 릴리스는 Amazon Neptune과 Amazon OpenSearch Serverless를 지원하지만, 대안적인 스토어 구현을 환영합니다. 스토어 API와 스토어가 사용되는 방식은 대안적인 구현을 예상하여 설계되었습니다. 그러나 증명은 개발 과정에서 이루어집니다: 대안적인 스토어를 개발하는 과정에서 문제가 발생하면 [알려주세요](https://github.com/awslabs/graphrag-toolkit/issues).

graph store와 vector store는 미리 프로비저닝해야 하는 *기존* 스토리지 인스턴스에 대한 연결을 제공합니다.

### Graph store

graph store는 [openCypher](https://opencypher.org/) 속성 그래프 쿼리 언어를 지원해야 합니다. 그래프 구축 쿼리는 일반적으로 `UNWIND ... MERGE` 관용구를 사용하여 [입력 배치](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/best-practices-content.html#best-practices-content-14)에 대한 그래프를 생성하거나 업데이트합니다. Neptune graph store 구현은 `GraphStore.node_id()` 메서드를 재정의하여 코드의 노드 ID(예: `chunkId`)가 Neptune의 `~id` 예약 속성에 매핑되도록 합니다. 대안적인 graph store 구현은 `node_id()`의 기본 구현을 그대로 둘 수 있습니다. 이렇게 하면 노드 ID가 동일한 이름의 속성에 매핑됩니다(즉, 코드에서 `chunkId`에 대한 참조가 노드의 `chunkId` 속성에 매핑됩니다).

graph store를 생성하려면 `GraphStoreFactory.for_graph_store()` 정적 팩토리 메서드를 사용합니다.

lexical-graph는 다음 그래프 데이터베이스를 지원합니다:

  - [Amazon Neptune](./graph-store-neptune-db.md)
  - [Amazon Neptune Analytics](./graph-store-neptune-analytics.md)
  - [Neo4j](./graph-store-neo4j.md)

#### 그래프 쿼리 로깅

기본적으로 로그의 모든 그래프 쿼리는 수정됩니다. 쿼리와 그 결과를 로깅하도록 툴킷을 구성하려면 graph store를 생성할 때 `NonRedactedGraphQueryLogFormatting`을 사용하세요:

```python
import os
from graphrag_toolkit.lexical_graph import set_logging_config
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage.graph import NonRedactedGraphQueryLogFormatting

set_logging_config('DEBUG', ['graphrag_toolkit.lexical_graph.storage.graph'])

graph_store = GraphStoreFactory.for_graph_store(
	os.environ['GRAPH_STORE'],
	log_formatting=NonRedactedGraphQueryLogFormatting()
)
```

### Vector store

vector store는 vector 인덱스의 컬렉션입니다. lexical-graph는 최대 두 개의 vector 인덱스를 사용합니다: chunk 인덱스와 statement 인덱스. chunk 인덱스는 일반적으로 statement 인덱스보다 훨씬 작습니다. [semantic-guided search](./semantic-guided-search.md)를 사용하려면 statement 인덱스를 활성화해야 합니다. [traversal 기반 검색](./traversal-based-search.md)을 사용하려면 chunk 인덱스를 활성화해야 합니다. 아래에 설명된 `VectorStoreFactory`는 기본적으로 두 인덱스를 모두 활성화합니다.

vector store를 생성하려면 `VectorStoreFactory.for_vector_store()` 정적 팩토리 메서드를 사용합니다.

lexical-graph는 다음 vector store를 지원합니다:

  - [Amazon OpenSearch Serverless](./vector-store-opensearch-serverless.md)
  - [Amazon Neptune Analytics](./vector-store-neptune-analytics.md)
  - [pgvector 확장이 포함된 Postgres](./vector-store-postgres.md)
  - [Amazon S3 Vectors](./vector-store-s3-vectors.md)

기본적으로 `VectorStoreFactory`는 statement 인덱스와 chunk 인덱스를 모두 활성화합니다. 그러나 chunk 인덱스만 필요한 traversal 기반 검색을 사용하는 것을 권장합니다. `index_names` 인수를 사용하여 chunk 인덱스만 활성화하세요:

```python
vector_store = VectorStoreFactory.for_vector_store(opensearch_connection_info, index_names=['chunk'])
```
