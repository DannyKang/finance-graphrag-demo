[[Home](./)]

## Traversal-Based Search

### 목차

  - [개요](#overview)
  - [예제](#example)
  - [기본 개념](#basic-concepts)
    - [연결 유형](#connectivity-types)
    - [Entity network 컨텍스트](#entity-network-contexts)
  - [Retriever](#retrievers)
  - [검색 결과](#search-results)

### 개요

쿼리 및 검색에 권장되는 방법은 traversal-based search 연산을 사용하는 것입니다. lexical-graph가 semantic-guided search를 지원하기는 하지만, 이 대안적 접근 방식에는 몇 가지 중요한 단점이 있습니다:

  - 각 statement에 대한 embedding이 필요하여 높은 스토리지 비용 발생
  - 대규모 데이터셋에서의 낮은 성능으로, 쿼리가 완료되는 데 수 분이 걸리는 경우가 많음
  - 향후 릴리스에서 제거될 예정

최적의 결과를 위해 사용자는 애플리케이션에서 traversal-based search를 사용해야 합니다.

Traversal-based search는 검색(retrieval)과 쿼리(querying)의 두 가지 방식으로 사용할 수 있습니다. 검색 연산을 수행하면 시스템이 graph 및 vector store를 검색하여 쿼리와 가장 관련성 높은 정보를 찾습니다. 그런 다음 이러한 원시 검색 결과를 직접 반환합니다. 쿼리 연산에서는 시스템이 추가 단계를 거칩니다. 관련 정보를 찾은 후 이 결과를 Large Language Model(LLM)에 전달합니다. LLM은 이 정보를 처리하고 쿼리에 답변하는 자연어 응답을 생성합니다.

### 예제

다음 예제는 기본 설정을 사용하여 traversal-based search를 수행합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

with (
    GraphStoreFactory.for_graph_store(
        'neptune-db://my-graph.cluster-abcdefghijkl.us-east-1.neptune.amazonaws.com'
    ) as graph_store,
    VectorStoreFactory.for_vector_store(
        'aoss://https://abcdefghijkl.us-east-1.aoss.amazonaws.com'
    ) as vector_store
):

    query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, 
        vector_store,
        streaming=True
    )

    response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

print(response.print_response_stream())
```

traversal-based search를 구성하는 데 사용되는 매개변수는 [Traversal-Based Search 구성](./traversal-based-search-configuration.md)에 설명되어 있습니다.

### 기본 개념

Traversal-based search는 lexical graph 내에서 정보를 찾기 위해 하나 이상의 retriever를 사용하는 방법입니다. 이 접근 방식은 lexical graph 구조의 두 가지 핵심 기능인 연결성(로컬 및 글로벌 모두)과 entity network 컨텍스트를 활용합니다.

#### 연결 유형

lexical graph는 로컬 및 글로벌 연결을 모두 제공합니다:

  - *로컬 연결* 로컬 연결은 일반적으로 단일 소스 내의 지역화된 네트워크 내에서 순회를 가능하게 합니다. 이는 주로 동일한 소스 자료 내의 관련 정보 chunk를 연결하는 토픽에 의해 촉진됩니다.
  - *글로벌 연결* 글로벌 연결은 그래프 구조에서 더 먼 관련 구성 요소로의 탐색을 허용합니다. 이는 서로 다른 소스 간에 연결을 생성하는 fact를 통해 달성됩니다.

서로 다른 retriever는 이러한 연결 유형을 다양한 방식으로 강조합니다:

  - `ChunkBasedSearch` retriever는 주로 로컬 연결을 활용합니다
  - `EntityBasedSearch` retriever는 글로벌 연결에 더 초점을 맞춥니다
	- The `EntityNetworkSearch` retriever balances local and global connectivity

#### Entity network 컨텍스트

Entity network 컨텍스트는 사용자 쿼리에서 발견된 검색어와 관련된 필터링되고 순위가 매겨진 entity 네트워크로 구성됩니다. 이러한 컨텍스트는 여러 중요한 기능을 수행합니다:

  - *검색 초기화* `EntityBasedSearch` retriever에서 entity 기반 검색의 시작점을 제공합니다
  - *유사도 검색* Entity network transcriptions – textual representations of the entity network contexts – help find content that differs from but relates to the original query in the `EntityNetworkSearch` retriever
  - *재순위화* 검색 결과에서 statement를 재순위화할 때 entity network 전사를 사용하여 원래 검색어를 향상시킬 수 있습니다
  - *LLM 통합* 쿼리 연산 중에 entity network 전사를 Large Language Model(LLM)에 제공하여 가장 관련성 높은 검색 결과에 응답을 집중시키는 데 도움을 줄 수 있습니다

### Retriever

Traversal-based search는 세 가지 서로 다른 retriever를 제공합니다:

  - `ChunkBasedSearch` retriever는 vector 유사도 검색을 사용하여 원래 쿼리와 유사한 정보를 찾습니다. retriever는 먼저 vector 유사도 검색을 사용하여 관련 chunk를 찾습니다. 이러한 chunk에서 retriever는 토픽, statement 및 fact를 순회합니다. Chunk 기반 검색은 원래 쿼리와 일치하는 chunk의 statement 및 fact 이웃을 기반으로 좁은 범위의 결과 집합을 반환하는 경향이 있습니다.
	- `EntityBasedSearch` retriever는 entity network 컨텍스트의 entity를 시작점으로 사용합니다. 이러한 entity에서 retriever는 fact, statement 및 토픽을 순회합니다. Entity 기반 검색은 개별 entity의 이웃과 entity를 연결하는 fact를 기반으로 넓은 범위의 결과 집합을 반환하는 경향이 있습니다.
	- `EntityNetworkSearch` retriever는 entity network 컨텍스트의 텍스트 전사를 사용하여 원래 쿼리와 유사하지 않지만 정확하고 완전한 응답을 생성하는 데 구조적으로 관련이 있는 정보에 대한 vector 검색을 수행합니다. 이러한 vector 검색은 '질문과 다른 무언가'와 유사한 chunk를 반환합니다. 이러한 chunk에서 retriever는 토픽, statement 및 fact를 순회하여 유사하지 않은 콘텐츠의 구조적으로 관련된 공간을 탐색합니다.
	
기본적으로 traversal-based search는 `ChunkBasedSearch`와 `EntityNetworkSearch`의 조합을 사용하도록 구성됩니다. 이 두 retriever는 함께 질문과 유사한 콘텐츠와 '질문과 다른 무언가'와 유사한 콘텐츠에 대한 접근을 제공합니다.

### 검색 결과

Traversal-based search와 함께 사용할 때, `LexicalGraphQueryEngine`의 `retrieve()` 연산은 LlamaIndex 점수화된 노드(`NodeWithScore`)의 컬렉션을 반환합니다. 각 노드는 소스, 토픽 및 statement 집합으로 구성된 단일 검색 결과를 포함합니다. 예를 들어,

```python
response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

for n in response.source_nodes:
    print(n.text)
```

 – 다음 출력을 반환합니다:

```
{
  "source": "https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html",
  "topic": "Neptune Analytics Features",
  "statements": [
    "Neptune Analytics allows loading graph data from a Neptune Database endpoint.",
    "Neptune Analytics enables running graph analytics queries.",
    "Neptune Analytics allows loading graph data from Amazon S3.",
    "Neptune Analytics supports custom graph queries.",
    "Neptune Analytics supports pre-built graph queries."
  ]
}
{
  ...
}
```

각 노드의 `metadata` 속성에는 검색 결과의 훨씬 더 자세한 분석이 포함된 딕셔너리가 있습니다. 여기에는 각 statement의 점수, 각 statement를 뒷받침하는 fact, 각 statement를 가져오는 데 사용된 retriever, 그리고 쿼리에 사용된 entity network 컨텍스트가 포함됩니다. 예를 들어,

```python
import json
for n in response.source_nodes:
    print(json.dumps(n.metadata, indent=2))
```

 – 다음 출력을 반환합니다:

```
{
  "result": {
    "source": {
      "sourceId": "aws::4510583f:e412",
      "metadata": {
        "url": "https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html"
      }
    },
    "topics": [
      {
        "topic": "Neptune Analytics Features",
        "topicId": "fbbde2f69acd195da90e578d0f9eeefe",
        "statements": [
          {
            "statementId": "810a8ac6943708e1584662b32431eb67",
            "statement": "Neptune Analytics allows loading graph data from a Neptune Database endpoint.",
            "facts": [
              "Neptune Analytics FEATURE loading graph data",
              "Neptune Analytics SUPPORTS LOADING FROM Neptune Database"
            ],
            "details": "",
            "chunkId": "aws::4510583f:e412:9f69cb6f",
            "score": 0.3187,
            "statement_str": "Neptune Analytics allows loading graph data from a Neptune Database endpoint. (details: Neptune Analytics FEATURE loading graph data, Neptune Analytics SUPPORTS LOADING FROM Neptune Database)",
            "retrievers": [
              "ChunkBasedSearch (3.12.0)"
            ]
          },
          {
            "statementId": "797021c7c33db8674fa0be42a1cdd9a6",
            "statement": "Neptune Analytics enables running graph analytics queries.",
            "facts": [
              "Neptune Analytics FEATURE running graph analytics queries"
            ],
            "details": "",
            "chunkId": "aws::4510583f:e412:9f69cb6f",
            "score": 0.2233,
            "statement_str": "Neptune Analytics enables running graph analytics queries. (details: Neptune Analytics FEATURE running graph analytics queries)",
            "retrievers": [
              "ChunkBasedSearch (3.12.0)"
            ]
          },
          {
            "statementId": "23deac383344021ed50e1c78448408a8",
            "statement": "Neptune Analytics allows loading graph data from Amazon S3.",
            "facts": [
              "Neptune Analytics FEATURE loading graph data",
              "Neptune Analytics SUPPORTS LOADING FROM Amazon S3"
            ],
            "details": "",
            "chunkId": "aws::4510583f:e412:9f69cb6f",
            "score": 0.2197,
            "statement_str": "Neptune Analytics allows loading graph data from Amazon S3. (details: Neptune Analytics FEATURE loading graph data, Neptune Analytics SUPPORTS LOADING FROM Amazon S3)",
            "retrievers": [
              "ChunkBasedSearch (3.12.0)"
            ]
          },
          {
            "statementId": "85a4ea712a9a83fb4ac7f441be72e694",
            "statement": "Neptune Analytics supports custom graph queries.",
            "facts": [
              "Neptune Analytics FEATURE custom graph queries"
            ],
            "details": "",
            "chunkId": "aws::4510583f:e412:9f69cb6f",
            "score": 0.199,
            "statement_str": "Neptune Analytics supports custom graph queries. (details: Neptune Analytics FEATURE custom graph queries)",
            "retrievers": [
              "ChunkBasedSearch (3.12.0)"
            ]
          },
          {
            "statementId": "3a480d6a686748a628009de3cd8238ed",
            "statement": "Neptune Analytics supports pre-built graph queries.",
            "facts": [
              "Neptune Analytics FEATURE pre-built graph queries"
            ],
            "details": "",
            "chunkId": "aws::4510583f:e412:9f69cb6f",
            "score": 0.1857,
            "statement_str": "Neptune Analytics supports pre-built graph queries. (details: Neptune Analytics FEATURE pre-built graph queries)",
            "retrievers": [
              "ChunkBasedSearch (3.12.0)"
            ]
          }
        ]
      }
    ]
  },
  "entity_contexts": {
    "contexts": [
      {
        "entities": [
          {
            "entity": {
              "entityId": "19ad98dc563a3a3c935d93723d3c9029",
              "value": "Neptune Analytics",
              "classification": "Software"
            },
            "score": 37.0,
            "reranking_score": 0.5025
          },
          {
            "entity": {
              "entityId": "ecc28e0aba278f8803bfbc5ae162831a",
              "value": "Neptune",
              "classification": "Software"
            },
            "score": 10.0,
            "reranking_score": 0.0
          }
        ]
      },
      {
        "entities": [
          {
            "entity": {
              "entityId": "51874c430e9cb1f5b09d790049d5380d",
              "value": "Neptune Database",
              "classification": "Software"
            },
            "score": 5.0,
            "reranking_score": 0.5025
          }
        ]
      }
    ]
  }
}
{
  ...
}
```