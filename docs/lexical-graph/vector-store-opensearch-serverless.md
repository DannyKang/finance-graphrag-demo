[[Home](./)]

## Amazon OpenSearch Serverless를 Vector Store로 사용하기

### 목차

  - [개요](#overview)
  - [종속성 설치](#install-dependencies)
  - [OpenSearch Serverless vector store 생성하기](#creating-an-opensearch-serverless-vector-store)
  - [Amazon OpenSearch Serverless와 사용자 정의 문서 ID](#amazon-opensearch-serverless-and-custom-document-ids)
    - [Amazon OpenSearch Serverless vector store 확인 및 복구](#verify-and-repair-an-amazon-opensearch-serverless-vector-store)

### 개요

Amazon OpenSearch Serverless 컬렉션을 vector store로 사용할 수 있습니다.

### 종속성 설치

OpenSearch vector store에는 `opensearch-py` 및 `llama-index-vector-stores-opensearch` 패키지가 모두 필요합니다:

```
pip install opensearch-py llama-index-vector-stores-opensearch
```

### OpenSearch Serverless vector store 생성하기

`VectorStoreFactory.for_vector_store()` 정적 팩토리 메서드를 사용하여 Amazon OpenSearch Serverless vector store 인스턴스를 생성하세요.

Amazon OpenSearch Serverless vector store를 생성하려면 `aoss://`로 시작하는 연결 문자열 뒤에 OpenSearch Serverless 컬렉션의 https 엔드포인트를 제공하세요:

```python
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

opensearch_connection_info = 'aoss://https://123456789012.us-east-1.aoss.amazonaws.com'

with VectorStoreFactory.for_vector_store(opensearch_connection_info) as vector_store:
    ...
```

### Amazon OpenSearch Serverless와 사용자 정의 문서 ID

Amazon OpenSearch Serverless vector 검색 컬렉션은 사용자 정의 문서 ID로 문서를 인덱싱하거나 upsert 요청으로 업데이트하는 것을 허용하지 않습니다. 내부적으로 Amazon OpenSearch Serverless는 각 인덱스 작업에 대해 고유한 문서 ID를 생성합니다. 이는 동일한 문서가 두 번 인덱싱되면 컬렉션에 두 개의 별도 항목이 생긴다는 것을 의미합니다.

툴킷 버전 3.10.3은 대량 인덱싱 프로세스에 문서가 이미 인덱싱되었는지 확인하는 단계를 도입합니다. 이미 인덱싱된 경우 해당 특정 문서를 (재)인덱싱하라는 요청을 무시합니다. 또한 확인 과정에서 문서가 vector store에 여러 번 인덱싱된 것으로 판단되면 스토어에서 중복 복사본을 삭제합니다.

#### Amazon OpenSearch Serverless vector store 확인 및 복구

3.10.3은 Amazon OpenSearch Serverless vector store를 확인하고 복구하는 데 사용할 수 있는 [명령줄 도구](https://github.com/awslabs/graphrag-toolkit/blob/main/examples/lexical-graph/scripts/repair_opensearch_vector_store.py)를 도입합니다. [repair_opensearch_vector_store.py](https://github.com/awslabs/graphrag-toolkit/blob/main/examples/lexical-graph/scripts/repair_opensearch_vector_store.py)를 다운로드하고 다음 명령을 실행하세요:

```
$ python repair_opensearch_vector_store.py --graph-store <graph store info> --vector-store <vector store info> --dry-run
```

위의 `--dry-run` 플래그를 사용하면 실제로 인덱스를 수정하지 않고 도구를 실행하여 필요한 복구를 확인할 수 있습니다. vector store를 복구(중복 문서 삭제)하려면 `--dry-run` 플래그를 제거하세요.

이 도구에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 필수 | 기본값 |
| ------------- | ------------- | ------------- | ------------- |
| `--graph-store` | Graph store 연결 정보 (예: `neptune-db://mydbcluster.cluster-123456789012.us-east-1.neptune.amazonaws.com:8182`) | 예 | – |
| `--vector-store` | Vector store 연결 정보 (예: `aoss://https://123456789012.us-east-1.aoss.amazonaws.com`) | 예 | – |
| `--tenant-ids` | 확인할 tenant id의 공백으로 구분된 목록 | 아니오 | 모든 tenant |
| `--batch-size` | OpenSearch에 대한 각 요청으로 확인할 OpenSearch 문서 수 | 아니오 | 1000 |
| `--dry-run` | 스토어를 확인하되, 스토어를 복구(중복 삭제)하지 않음 | 아니오 | 도구가 vector store에서 중복 문서를 삭제함 |

도구는 다음 형식으로 결과를 반환합니다:

```
{
  "duration_seconds": 16,
  "dry_run": false,
  "totals": {
    "total_node_ids": 15354,
    "total_doc_ids": 15354,
    "total_deleted_doc_ids": 0,
    "total_unindexed": 0
  },
  "results": [
    {
      "tenant_id": "default_",
      "index": "chunk",
      "num_nodes": 17,
      "num_docs": 17,
      "num_deleted": 0,
      "num_unindexed": 0
    },
    {
      "tenant_id": "default_",
      "index": "statement",
      "num_nodes": 211,
      "num_docs": 211,
      "num_deleted": 0,
      "num_unindexed": 0
    },
    {
      "tenant_id": "local",
      "index": "chunk",
      "num_nodes": 1,
      "num_docs": 1,
      "num_deleted": 0,
      "num_unindexed": 0
    },
    {
      "tenant_id": "local",
      "index": "statement",
      "num_nodes": 26,
      "num_docs": 26,
      "num_deleted": 0,
      "num_unindexed": 0
    }
  ]
}
```

필드 설명:

| 필드  | 설명 |
| ------------- | ------------- |
| `dry_run` | `true` - 중복 문서가 실제로 vector store에서 삭제되지 않음 (결과의 삭제된 문서 수는 삭제되었을 수를 나타냄); `false` - 중복 문서가 vector store에서 삭제됨. |
| `total_node_ids` | 그래프의 인덱싱 가능한 총 노드 수 |
| `total_doc_ids` | vector store의 총 문서 수 |
| `total_deleted_doc_ids` | vector store에서 삭제된 총 문서 수 (`dry_run`이 `true`인 경우 표시 수만) |
| `total_unindexed` | 인덱싱되지 않은 총 노드 수 |
| `tenant_id` | Tenant id (기본 tenant는 `default_`) |
| `index` | 인덱스 이름 |
| `num_nodes` | 특정 tenant 그래프의 인덱싱 가능한 노드 수 |
| `num_docs` | 특정 tenant vector 인덱스의 문서 수 |
| `num_deleted` | 특정 tenant vector 인덱스에서 삭제된 문서 수 (`dry_run`이 `true`인 경우 표시 수만) |
| `num_unindexed` | 특정 tenant vector 인덱스에서 인덱싱되지 않은 노드 수 |