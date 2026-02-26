[[Home](./)]

## Traversal-Based Search 구성

### 목차

  - [개요](#overview)
  - [검색 결과 구성](#search-results-configuration)
    - [max_search_results](#max_search_results)
    - [max_statements_per_topic](#max_statements_per_topic)
    - [max_statements](#max_statements)
    - [statement_pruning_factor](#statement_pruning_factor)
    - [statement_pruning_threshold](#statement_pruning_threshold)
    - [검색 결과 구성을 사용할 때](#when-to-use-search-results-configuration)
  - [Retriever 선택](#retriever-selection)
    - [retrievers](#retrievers)
    - [다른 retriever를 사용할 때](#when-to-use-different-retrievers)
  - [재순위화 전략](#reranking-strategy)
    - [reranker](#reranker)
    - [reranker 전략 선택하기](#choosing-a-reranker-strategy)
    - [재순위화 결과 문제 해결](#troubleshooting-reranking-results)
  - [Graph 및 vector 검색 매개변수](#graph-and-vector-search-parameters)
    - [intermediate_limit](#intermediate_limit)
    - [query_limit](#query_limit)
    - [vss_top_k](#vss_top_k)
    - [vss_diversity_factor](#vss_diversity_factor)
    - [num_workers](#num_workers)
    - [Graph 및 vector 검색 매개변수를 변경할 때](#when-to-change-the-graph-and-vector-search-parameters)
  - [Entity network 컨텍스트 선택](#entity-network-context-selection)
    - [Entity network 생성](#entity-network-generation)
    - [ec_max_depth](#ec_max_depth)
    - [ec_max_contexts](#ec_max_contexts)
    - [ec_max_score_factor](#ec_max_score_factor)
    - [ec_min_score_factor](#ec_min_score_factor)
    - [Entity network 생성을 조정할 때](#when-to-adjust-entity-network-generation)


   

### 개요

Traversal-based search 구성 옵션을 사용하여 특정 애플리케이션, 데이터셋 및 쿼리 유형에 더 적합하도록 traversal-based search 연산을 사용자 정의할 수 있습니다. 검색 성능을 최적화하는 데 도움이 되는 다음 구성 옵션을 사용할 수 있습니다:

  - [**검색 결과 구성**](#search-results-configuration) 반환되는 검색 결과 및 statement 수를 조정하고, 낮은 품질의 statement 및 결과를 필터링하기 위한 점수 임계값을 설정합니다
  - [**Retriever 선택**](#retriever-selection) 정보를 가져올 때 사용할 retriever를 지정합니다
  - [**재순위화 전략**](#reranking-strategy) statement 및 결과의 재순위화 및 정렬 방식을 수정합니다
  - [**Graph 및 vector 검색 매개변수**](#graph-and-vector-search-parameters) 그래프 쿼리 및 vector 검색을 제어하는 매개변수를 사용자 정의합니다
  - [**Entity network 컨텍스트 선택**](#entity-network-context-selection) entity network 컨텍스트를 선택하는 데 사용되는 매개변수를 구성합니다

이러한 옵션을 통해 특정 요구 사항에 따라 검색 동작을 미세 조정하고 반환된 결과의 관련성을 개선할 수 있습니다.
___

### 검색 결과 구성

검색 기능을 구성할 때 다음 매개변수를 사용하여 반환되는 결과의 수와 품질을 제어할 수 있습니다:

#####  `max_search_results`

반환할 최대 검색 결과 수를 정의합니다. 각 검색 결과에는 동일한 토픽(및 소스)에 속하는 하나 이상의 statement가 포함됩니다. `None`으로 설정하면 일치하는 모든 검색 결과가 반환됩니다. 기본값은 `10`입니다.

#####  `max_statements_per_topic`

단일 토픽에 포함될 수 있는 statement 수를 제어하여 각 검색 결과의 크기를 효과적으로 제한합니다. `None`으로 설정하면 검색과 일치하는 토픽에 속하는 모든 statement가 결과에 포함됩니다. 기본값은 `10`입니다.

#####  `max_statements`

전체 결과 집합에 걸친 총 statement 수를 제한합니다. `None`으로 설정하면 모든 결과의 모든 statement가 반환됩니다. 기본값은 `100`입니다.

#####  `statement_pruning_factor`

이 매개변수는 전체 결과 집합에서 가장 높은 statement 점수의 비율을 기반으로 낮은 품질의 statement를 필터링하는 데 도움을 줍니다. `<최대_statement_점수> * statement_pruning_factor`보다 낮은 점수를 가진 statement는 결과에서 제거됩니다. 기본값은 `0.05`(최대 점수의 5%)입니다.

##### `statement_pruning_threshold`

statement에 대한 절대 최소 점수 임계값을 설정합니다. 이 임계값보다 낮은 점수를 가진 statement는 결과에서 제거됩니다. 기본값은 `None`입니다.

#### 예제

```python
query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    statement_pruning_threshold=0.2
)
```

#### 검색 결과 구성을 사용할 때

`max_search_results`, `max_statements_per_topic` 및 `max_statements` 매개변수를 사용하여 결과의 전체 크기를 제어할 수 있습니다.

각 검색 결과는 단일 소스의 단일 토픽에 속하는 하나 이상의 statement로 구성됩니다. 동일한 소스이지만 다른 토픽의 statement는 별도의 검색 결과로 나타납니다. `max_search_results`를 늘리면 결과의 소스 다양성이 증가합니다. `max_statements_per_topic`을 늘리면 각 개별 검색 결과에 더 많은 세부 정보가 추가됩니다.

statement 수를 늘릴 때(전체 또는 토픽별), statement 가지치기 매개변수도 함께 늘리는 것을 고려해야 합니다. 이렇게 하면 더 큰 결과 집합에서도 관련성이 낮은 정보가 아닌 매우 관련성 높은 statement를 얻을 수 있습니다.

___

### Retriever 선택

`retrievers` 매개변수를 사용하여 최대 [세 가지 서로 다른 retriever](./traversal-based-search.md#retrievers)로 traversal-based search를 구성할 수 있습니다.

#####  `retrievers`

retriever 클래스 이름의 배열을 허용합니다. 다음 중에서 선택하세요:

  - **`ChunkBasedSearch`** 이 retriever는 vector 유사도 검색을 사용하여 원래 쿼리와 유사한 정보를 찾습니다. retriever는 먼저 vector 유사도 검색을 사용하여 관련 chunk를 찾습니다. 이러한 chunk에서 retriever는 토픽, statement 및 fact를 순회합니다. Chunk 기반 검색은 원래 쿼리와 일치하는 chunk의 statement 및 fact 이웃을 기반으로 좁은 범위의 결과 집합을 반환하는 경향이 있습니다.
  - **`EntityBasedSearch`** 이 retriever는 entity network 컨텍스트의 entity를 시작점으로 사용합니다. 이러한 entity에서 retriever는 fact, statement 및 토픽을 순회합니다. Entity 기반 검색은 개별 entity의 이웃과 entity를 연결하는 fact를 기반으로 넓은 범위의 결과 집합을 반환하는 경향이 있습니다.
  - **`EntityNetworkSearch`** 이 retriever는 entity network 컨텍스트의 텍스트 전사를 사용하여 원래 쿼리와 유사하지 않지만 정확하고 완전한 응답을 생성하는 데 구조적으로 관련이 있는 정보에 대한 vector 검색을 수행합니다. 이러한 vector 검색은 '질문과 다른 무언가'와 유사한 chunk를 반환합니다. 이러한 chunk에서 retriever는 토픽, statement 및 fact를 순회하여 유사하지 않은 콘텐츠의 구조적으로 관련된 공간을 탐색합니다.
	
#### 예제

```python
from graphrag_toolkit.lexical_graph.retrieval.retrievers import *

query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    retrievers=[ChunkBasedSearch, EntityBasedSearch]
)
```

#### 다른 retriever를 사용할 때

기본적으로 traversal-based search는 `ChunkBasedSearch`와 `EntityNetworkSearch`의 조합을 사용하도록 구성됩니다. 이 조합은 질문과 직접적으로 유사한 콘텐츠와 관련이 있지만 쿼리에서 명시적으로 언급되지 않은 콘텐츠 모두에 대한 접근을 제공합니다.

다음과 같은 경우 `ChunkBasedSearch` retriever만 단독으로 사용하는 것을 고려하세요:

  - 쿼리에 주로 유사도 기반 검색이 필요한 경우
  - 전체 chunk가 아닌 개별 관련 statement에 초점을 맞추고 싶은 경우
  - 기존 vector 검색보다 더 넓은 검색 범위가 필요한 경우

이 retriever는 로컬 연결을 사용하여 동일한 소스의 다른 chunk에서 관련 statement를 찾아 기본 vector 유사도를 넘어 확장합니다.

`EntityBasedSearch`와 `EntityNetworkSearch` retriever는 검색에서 entity network를 활용하는 서로 다른 방법을 제공합니다:

  - `EntityBasedSearch`는 글로벌 연결을 사용하여 동일한 fact로 연결된 서로 다른 소스의 statement를 찾습니다. 종종 다른 retriever보다 더 다양한 결과를 생성합니다.
   - `EntityNetworkSearch` retriever는 entity network(그래프 순회를 통해 검색됨)를 유사도 검색 집합으로 변환합니다. 이 접근 방식은 글로벌 및 로컬 연결의 균형을 맞춥니다.

___

### 재순위화 전략

Traversal-based search는 검색 프로세스 중 두 가지 핵심 지점에서 재순위화를 통합합니다:

  - entity network 컨텍스트를 생성할 때, entity와 entity network 모두 재순위화됩니다
  - 검색 결과를 최종 확정하기 전에, 전체 statement 집합이 재순위화를 거칩니다

재순위화는 단일 매개변수를 통해 관리됩니다:

#####  `reranker`

매개변수 옵션:

  - `model`: LlamaIndex 기반 `SentenceReranker`를 사용하여 결과 집합의 모든 statement를 재순위화합니다
  - `tfidf` (기본값): 용어 빈도-역문서 빈도 측정을 적용하여 statement의 순위를 매깁니다
  - `None`: 재순위화 기능을 완전히 비활성화합니다

tfidf 기반 옵션은 모델 기반 접근 방식보다 훨씬 빠릅니다. 모델 reranker를 사용하려면 먼저 다음 추가 종속성을 설치해야 합니다:

```
pip install torch sentence_transformers
```

#### 예제

```python
query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    reranker='model'
)
```

#### reranker 전략 선택하기

tfidf reranker 옵션은 대부분의 사용 사례에 대해 빠르고 비용 효율적이며 일반적으로 효과적인 솔루션을 제공합니다. 그러나 결과가 요구 사항을 충족하지 못하는 경우 모델 reranker로 전환하는 것을 고려하세요. 모델이 다른 결과를 제공할 수 있지만 tfidf보다 훨씬 느리게 작동하며 개선된 결과를 보장하지 않는다는 점에 유의하세요.

##### 재순위화 결과 문제 해결

효과적인 재순위화 전략은 최종 결과에 매우 관련성 높은 statement만 나타나도록 해야 합니다. 재순위화가 제대로 작동하려면, 재순위화 프로세스가 시작되기 전에 먼저 관련 statement가 retriever에 의해 캡처되어야 합니다.

검색 결과에 기대하는 콘텐츠가 포함되지 않은 경우, 다음과 같이 사전 순위화된 결과에 이 콘텐츠가 있는지 확인하세요:

  1. `reranker=None`으로 설정하여 reranker를 비활성화합니다
  2. [검색 결과 구성](#search-results-configuration)에서 다음 매개변수를 늘립니다:
    - [max_search_results](#max_search_results)
    - [max_statements_per_topic](#max_statements_per_topic)
    - [max_statements](#max_statements)

이러한 조정 후 `retrieve()` 연산에서 반환된 결과를 검토하세요. 기대하는 콘텐츠가 여전히 나타나지 않으면 문제는 재순위화와 관련이 없습니다. 대신 문서의 다른 곳에 설명된 다른 튜닝 접근 방식을 고려하세요:

  - retriever 구성 변경
  - 가지치기 임계값 조정
  - entity network 컨텍스트 구성

___

### Graph 및 vector 검색 매개변수

이러한 설정은 시스템이 graph 및 vector store를 쿼리하는 방법을 제어합니다. 사용자가 쿼리를 제출하면 두 스토어 모두에서 여러 검색이 실행되며, 일부는 병렬로 실행됩니다. vector store는 top K 접근 방식을 기반으로 가장 유사한 항목을 반환합니다. 결과는 서로 다른 소스에 걸쳐 다양화될 수 있습니다. graph store 쿼리는 소스별로 그룹화된 statement 집합을 반환합니다. 그래프 쿼리는 초기 statement 식별 후 연결 탐색이라는 2단계 프로세스를 사용합니다.

##### `intermediate_limit`

연결(로컬 및 글로벌 모두)을 탐색하기 전에 그래프 쿼리의 첫 번째 단계에서 식별되는 statement 수를 제어합니다. 기본값은 `50`입니다.

##### `query_limit`

각 그래프 쿼리가 반환하는 결과 수를 정의합니다. 각 결과는 단일 소스의 statement로 구성됩니다. 기본값은 `10`입니다.

##### `vss_top_k`

유사도 기반 순회를 시작하는 데 사용되는 상위 매칭 결과 수를 지정합니다. 기본값은 `10`입니다.

##### `vss_diversity_factor`

결과가 다양한 소스에서 나오도록 보장합니다. vector store에 대한 쿼리는 (`vss_top_k × vss_diversity_factor`)개의 초기 매칭을 검색한 다음, 이전에 사용되지 않은 소스에서 가장 관련성 높은 결과를 반복적으로 선택합니다. 이 프로세스는 총 `vss_top_k`개의 결과에 도달할 때까지 계속됩니다. `None`으로 설정하면 처음 `vss_top_k`개의 매칭을 단순히 반환합니다. 기본값은 `5`입니다.

##### `num_workers`
 
그래프 쿼리를 병렬로 실행하는 데 사용할 수 있는 스레드 수를 설정합니다. 기본값은 `10`입니다.

#### 예제

```python
query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    intermediate_limit=25,
    num_workers=3
)
```

#### Graph 및 vector 검색 매개변수를 변경할 때

[검색 결과 구성](#search-results-configuration) 매개변수는 검색 결과의 처리를 제어하는 반면, graph 및 vector store 구성 매개변수는 결과를 생성하는 데 사용되는 쿼리 처리를 제어합니다.

쿼리가 여러 소스에 걸쳐 매우 다양한 콘텐츠를 찾아야 하는 경우 `vss_diversity_factor`를 늘리세요. 쿼리가 기본 소스에서 직접 파생된 콘텐츠를 필요로 하는 경우 `vss_diversity_factor`를 줄이거나 `None`으로 설정하세요.

사용자 쿼리를 실행하는 동안 메모리 부족 문제가 발생하면 `intermediate_limit`와 `num_workers`를 줄이세요. 이렇게 하면 각 그래프 쿼리의 작업 집합 크기가 줄어들고 병렬로 실행되는 그래프 쿼리 수가 줄어듭니다.

애플리케이션에 많은 수의 검색 결과가 필요한 경우 `intermediate_limit`, `query_limit` 및/또는 `vss_top_k`를 늘리는 것을 고려해야 합니다. 이러한 매개변수를 늘리면 쿼리 지연 시간이 증가하고 더 많은 메모리가 필요할 수 있다는 점에 유의하세요.

___

### Entity network 컨텍스트 선택

시스템은 사용자의 쿼리 용어를 기반으로 집중된 [entity network 컨텍스트](./traversal-based-search.md#entity-network-contexts)를 생성합니다. 이러한 컨텍스트 네트워크는 검색 및 응답 생성 단계를 모두 안내합니다.

#### Entity network 생성

Entity network 컨텍스트를 생성하는 프로세스는 다음과 같습니다:

  1. **초기 entity 발견** id 조회, 정확한 매칭, 부분 매칭, 전체 텍스트 검색 또는 graph store에서 제공하는 기타 검색 기술 등 다양한 검색 방법을 사용하여 쿼리 용어를 entity에 매칭합니다.
  2. **Entity 우선순위화**	쿼리에 대한 관련성별로 매칭된 entity를 정렬합니다. 상위 entity의 차수 중심성을 계산합니다: 이는 후속 필터링의 기준점으로 사용됩니다.
  3. **네트워크 확장** 각 루트 entity 노드에서 시작하여 entity 간 관계를 따라가며 2-3 수준의 깊이로 확장합니다.
  4. **네트워크 가지치기** 2단계에서 생성된 기준점에서 파생된 차수 중심성 임계값을 기반으로 필터링을 적용합니다. 각 경로를 따라 이러한 임계값 위아래의 entity를 제거합니다.
  5. **경로 선택** 모든 유효한 경로를 재순위화하고 상위 N개의 가장 높은 순위의 경로를 선택합니다. 이것이 최종 entity network 컨텍스트 집합을 형성합니다.

다음 매개변수를 사용하여 entity network 생성을 구성할 수 있습니다:

##### `ec_max_depth`

각 entity network 경로의 최대 entity 수를 결정합니다.

기본값은 `3`입니다.

##### `ec_max_contexts`

제공자가 반환하는 entity 컨텍스트 수를 제한합니다. 참고: 여러 entity 컨텍스트가 동일한 루트 entity에서 시작될 수 있습니다. 기본값은 `3`입니다.

##### `ec_max_score_factor`

상위 entity의 차수 중심성 비율을 기반으로 한 임계값을 초과하는 차수 중심성을 가진 entity를 필터링합니다. 기본값은 `10`(상위 entity 점수의 1000%)입니다.

##### `ec_min_score_factor`

상위 entity의 차수 중심성 비율을 기반으로 한 임계값 아래로 떨어지는 차수 중심성을 가진 entity를 필터링합니다. 기본값은 `0.1`(상위 entity 점수의 10%)입니다.

#### 예제

```python
query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    ec_max_depth=3,
    ec_max_contexts=3
)
```

#### Entity network 생성을 조정할 때

Entity network 컨텍스트 설정은 시스템이 관련 콘텐츠를 얼마나 광범위하게 검색하고 entity 관계를 기반으로 결과를 어떻게 필터링하는지를 제어합니다. 구조적으로 관련이 있지만 유사하지 않은 콘텐츠를 찾으려면 검색 범위를 늘리세요. 쿼리와 유사한 콘텐츠에 집중하려면 검색 범위를 줄이세요.

**넓지만 얕은 검색** – e.g. `ec_max_depth=1` and `ec_max_contexts=5` – 은 쿼리와의 직접적인 매칭에 초점을 맞춘 다양한 컨텍스트를 탐색하는 데 도움이 됩니다. 

**깊지만 좁은 검색** – e.g. `ec_max_depth=3` and `ec_max_contexts=2` – 은 핵심 entity를 통해 먼 관련 콘텐츠를 탐색하는 데 도움이 됩니다.

`ec_max_score_factor` 및 `ec_min_score_factor` 매개변수를 사용하면 상위 entity의 중요도에 비례하여 '대형'과 '소형' entity를 필터링할 수 있습니다. 

`ec_max_score_factor`는 고점수 원거리 entity가 검색 결과에 얼마나 두드러지게 나타나는지를 제어합니다. 높은 값은 멀리 관련되어 있더라도 잘 연결된 entity를 포함합니다. 직접 연결되지 않은 중요한 entity를 보고 싶을 때 `ec_max_score_factor`를 늘리세요.

`ec_min_score_factor`는 덜 중요한 원거리 entity의 포함을 제어합니다. 낮은 값은 멀리 관련되어 있더라도 거의 언급되지 않는 entity를 포함하게 됩니다. 틈새 또는 드문 연결을 찾으려면 `ec_min_score_factor`를 줄이세요.
