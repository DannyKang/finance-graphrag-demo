## Semantic-Guided Search

쿼리 및 검색에 권장되는 방법은 [traversal-based search](./traversal-based-search.md) 연산을 사용하는 것입니다. 그러나 lexical-graph는 현재 semantic-guided search도 지원하지만, 이 접근 방식에는 몇 가지 단점이 있습니다:

  - 각 statement에 대한 embedding이 필요하여 높은 스토리지 비용 발생
  - 대규모 데이터셋에서의 낮은 성능으로, 쿼리가 완료되는 데 수 분이 걸리는 경우가 많음
  - 향후 릴리스에서 제거될 예정

이 페이지에는 semantic-guided search 문서가 포함되어 있습니다.

### 예제

다음 예제는 모든 기본 설정으로 semantic-guided search를 사용하여 그래프를 쿼리합니다:

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

    query_engine = LexicalGraphQueryEngine.for_semantic_guided_search(
        graph_store, 
        vector_store,
        streaming=True
    )

    response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

print(response.print_response_stream())
```

기본적으로 semantic-guided search는 세 가지 하위 retriever를 사용하는 복합 검색 전략을 사용합니다:

  - `StatementCosineSimilaritySearch` - statement embedding과 쿼리 embedding의 코사인 유사도를 사용하여 상위 k개의 statement를 가져옵니다.
  - `KeywordRankingSearch` - 쿼리에서 추출된 지정된 수의 키워드 및 동의어에 대한 매칭 수를 기반으로 상위 k개의 statement를 가져옵니다. 키워드 매칭이 더 많은 statement가 결과에서 더 높은 순위를 차지합니다.
  - `SemanticBeamGraphSearch` - 공유된 entity를 기반으로 statement의 인접 statement를 찾고, 후보 statement의 embedding과 쿼리 embedding의 코사인 유사도를 기반으로 가장 유망한 것을 유지하는 statement 기반 검색입니다. 이 검색은 다른 retriever(예: `StatementCosineSimilaritySearch` 및/또는 `KeywordRankingSearch`)의 statement 또는 statement 인덱스에 대한 초기 vector 유사도 검색의 statement로 시작됩니다.

#### Semantic-guided search 결과

Semantic-guided search는 하나 이상의 검색 결과를 반환하며, 각각은 소스와 statement 집합으로 구성됩니다:

```
<source_1>
<source_1_metadata>
	<url>https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html</url>
</source_1_metadata>
<statement_1.1>Neptune Database is a serverless graph database</statement_1.1>
<statement_1.2>Neptune Analytics is an analytics database engine</statement_1.2>
<statement_1.3>Neptune Analytics is a solution for quickly analyzing existing graph databases</statement_1.3>
<statement_1.4>Neptune Database provides a solution for graph database workloads that need Multi-AZ high availability</statement_1.4>
<statement_1.5>Neptune Analytics is a solution for quickly analyzing graph datasets stored in a data lake (details: Graph datasets LOCATION data lake)</statement_1.5>
<statement_1.6>Neptune Database provides a solution for graph database workloads that need to scale to 100,000 queries per second</statement_1.6>
<statement_1.7>Neptune Database is designed for optimal scalability</statement_1.7>
<statement_1.8>Neptune Database provides a solution for graph database workloads that need multi-Region deployments</statement_1.8>
<statement_1.9>Neptune Analytics removes the overhead of managing complex data-analytics pipelines (details: Overhead CONTEXT managing complex data-analytics pipelines)</statement_1.9>
...
</source_1>

...

<source_4>
<source_4_metadata>
	<url>https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html</url>
</source_4_metadata>
<statement_4.1>Neptune Analytics allows performing business intelligence queries using openCypher language</statement_4.1>
<statement_4.2>The text distinguishes between Neptune Analytics and Neptune Database</statement_4.2>
<statement_4.3>Neptune Analytics allows performing custom analytical queries using openCypher language</statement_4.3>
<statement_4.4>Neptune Analytics allows performing in-database analytics on large graphs</statement_4.4>
<statement_4.5>Neptune Analytics allows focusing on queries and workflows to solve problems</statement_4.5>
<statement_4.6>Neptune Analytics can load data extremely fast into memory</statement_4.6>
<statement_4.7>Neptune Analytics allows running graph analytics queries using pre-built or custom graph queries</statement_4.7>
<statement_4.8>Neptune Analytics manages graphs instead of infrastructure</statement_4.8>
<statement_4.9>Neptune Analytics allows loading graph data from Amazon S3 or a Neptune Database endpoint</statement_4.9>
...
</source_4>
```

#### SemanticGuidedRetriever 구성하기

개별 하위 retriever를 구성하여 semantic-guided search 동작을 구성할 수 있습니다:

| Retriever  | 매개변수  | 설명 | 기본값 |
| ------------- | ------------- | ------------- | ------------- |
| `StatementCosineSimilaritySearch` | `top_k` | 결과에 포함할 statement 수 | `100` |
| `KeywordRankingSearch` | `top_k` | 결과에 포함할 statement 수 | `100` |
|| `max_keywords` | 쿼리에서 추출할 최대 키워드 수 | `10` |
| `SemanticBeamGraphSearch` | `max_depth` | 시작 statement에서 유망한 후보를 따라갈 최대 깊이 | `3` |
|| `beam_width` | 확장된 각 statement에 대해 반환할 가장 유망한 후보 수 | `10` |
| `RerankingBeamGraphSearch` | `max_depth` | 시작 statement에서 유망한 후보를 따라갈 최대 깊이 | `3` |
|| `beam_width` | 확장된 각 statement에 대해 반환할 가장 유망한 후보 수 | `10` |
|| `reranker` | statement를 재순위화하는 데 사용될 Reranker 인스턴스 (아래 참조) | `None`
|| `initial_retrievers` | 시작 statement를 제공하는 데 사용되는 retriever 목록 (아래 참조) | `None` |

#### 재순위화 beam search를 사용한 semantic-guided search

`SemanticGuidedRetriever`에서 `SemanticBeamGraphSearch` 대신 `RerankingBeamGraphSearch`를 사용할 수 있습니다. `RerankingBeamGraphSearch`는 코사인 유사도 대신 reranker를 사용하여 어떤 후보 statement를 추구할지 결정합니다.

`RerankingBeamGraphSearch` 인스턴스를 reranker로 초기화해야 합니다. 툴킷에는 `BGEReranker`와 `SentenceReranker`라는 두 가지 서로 다른 reranker가 포함되어 있습니다. CPU 디바이스에서 실행하는 경우 `SentenceReranker`를 사용하는 것을 권장합니다. GPU 디바이스에서 실행하는 경우 `BGEReranker` 또는 `SentenceReranker` 중 하나를 선택할 수 있습니다.

아래 예제는 beam search를 수행하면서 statement를 재순위화하기 위해 `SentenceReranker`와 `RerankingBeamGraphSearch`를 사용합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.retrieval.retrievers import RerankingBeamGraphSearch, StatementCosineSimilaritySearch, KeywordRankingSearch
from graphrag_toolkit.lexical_graph.retrieval.post_processors import SentenceReranker

with (
    GraphStoreFactory.for_graph_store(
        'neptune-db://my-graph.cluster-abcdefghijkl.us-east-1.neptune.amazonaws.com'
    ) as graph_store,
    VectorStoreFactory.for_vector_store(
        'aoss://https://abcdefghijkl.us-east-1.aoss.amazonaws.com'
    ) as vector_store
):

    cosine_retriever = StatementCosineSimilaritySearch(
        vector_store=vector_store,
        graph_store=graph_store,
        top_k=50
    )

    keyword_retriever = KeywordRankingSearch(
        vector_store=vector_store,
        graph_store=graph_store,
        max_keywords=10
    )

    reranker = SentenceReranker(
        batch_size=128
    )

    beam_retriever = RerankingBeamGraphSearch(
        vector_store=vector_store,
        graph_store=graph_store,
        reranker=reranker,
        initial_retrievers=[cosine_retriever, keyword_retriever],
        max_depth=8,
        beam_width=100
    )

    query_engine = LexicalGraphQueryEngine.for_semantic_guided_search(
        graph_store, 
        vector_store,
        retrievers=[
            cosine_retriever,
            keyword_retriever,
            beam_retriever
        ]
    )

    response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

print(response.response)
```

아래 예제는 beam search를 수행하면서 statement를 재순위화하기 위해 `BGEReranker`와 `RerankingBeamGraphSearch`를 사용합니다.

reranker가 tensor를 다운로드하는 동안 처음 실행 시 지연이 발생합니다.

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.retrieval.retrievers import RerankingBeamGraphSearch, StatementCosineSimilaritySearch, KeywordRankingSearch
from graphrag_toolkit.lexical_graph.retrieval.post_processors import BGEReranker

with (
    GraphStoreFactory.for_graph_store(
        'neptune-db://my-graph.cluster-abcdefghijkl.us-east-1.neptune.amazonaws.com'
    ) as graph_store,
    VectorStoreFactory.for_vector_store(
        'aoss://https://abcdefghijkl.us-east-1.aoss.amazonaws.com'
    ) as vector_store
):

    cosine_retriever = StatementCosineSimilaritySearch(
        vector_store=vector_store,
        graph_store=graph_store,
        top_k=50
    )

    keyword_retriever = KeywordRankingSearch(
        vector_store=vector_store,
        graph_store=graph_store,
        max_keywords=10
    )

    reranker = BGEReranker(
        gpu_id=0, # Remove if running on CPU device,
        batch_size=128
    )

    beam_retriever = RerankingBeamGraphSearch(
        vector_store=vector_store,
        graph_store=graph_store,
        reranker=reranker,
        initial_retrievers=[cosine_retriever, keyword_retriever],
        max_depth=8,
        beam_width=100
    )

    query_engine = LexicalGraphQueryEngine.for_semantic_guided_search(
        graph_store, 
        vector_store,
        retrievers=[
            cosine_retriever,
            keyword_retriever,
            beam_retriever
        ]
    )

    response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

print(response.response)
```

### 후처리기

결과를 더욱 개선하고 포맷하는 데 사용할 수 있는 여러 후처리기가 있습니다:

| 후처리기  | 설명 |
| ------------- | ------------- | ------------- |
| `BGEReranker` | 쿼리 엔진에 반환하기 전에 `BAAI/bge-reranker-v2-minicpm-layerwise` 모델을 사용하여 결과를 재순위화(및 제한)합니다. GPU 디바이스가 있는 경우에만 사용하세요. |
| `SentenceReranker` | 쿼리 엔진에 반환하기 전에 `mixedbread-ai/mxbai-rerank-xsmall-v1` 모델을 사용하여 결과를 재순위화(및 제한)합니다. |
| `StatementDiversityPostProcessor` | TF-IDF 유사도를 사용하여 결과에서 유사한 statement를 제거합니다. `StatementDiversityPostProcessor`를 처음 실행하기 전에 다음 패키지를 로드하세요: `python -m spacy download en_core_web_sm` |
| `StatementEnhancementPostProcessor` | chunk 컨텍스트와 LLM을 사용하여 원본 metadata를 보존하면서 콘텐츠를 개선하여 statement를 향상시킵니다. (statement당 LLM 호출이 필요합니다.) |

아래 예제는 `StatementDiversityPostProcessor`, `SentenceReranker` 및 `StatementEnhancementPostProcessor`를 사용합니다. GPU 디바이스에서 실행하는 경우 `SentenceReranker`를 `BGEReranker`로 대체할 수 있습니다.

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.retrieval.post_processors import SentenceReranker, SentenceReranker, StatementDiversityPostProcessor, StatementEnhancementPostProcessor
import os

with (
    GraphStoreFactory.for_graph_store(
        'neptune-db://my-graph.cluster-abcdefghijkl.us-east-1.neptune.amazonaws.com'
    ) as graph_store,
    VectorStoreFactory.for_vector_store(
        'aoss://https://abcdefghijkl.us-east-1.aoss.amazonaws.com'
    ) as vector_store
):

    query_engine = LexicalGraphQueryEngine.for_semantic_guided_search(
        graph_store, 
        vector_store,
        post_processors=[
            SentenceReranker(), 
            StatementDiversityPostProcessor(), 
            StatementEnhancementPostProcessor()
        ]
    )

    response = query_engine.query("What are the differences between Neptune Database and Neptune Analytics?")

print(response.response)
```