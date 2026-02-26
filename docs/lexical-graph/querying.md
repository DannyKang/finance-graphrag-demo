[[Home](./)]

## 쿼리

lexical-graph가 LLM에 제시하는 컨텍스트의 기본 단위는 독립적인 주장 또는 명제인 *진술*입니다. 소스 문서는 chunk로 나뉘고, 이 chunk에서 진술이 추출됩니다. graphrag-toolkit의 [그래프 모델](./graph-model.md)에서 진술은 토픽별로 주제적으로 그룹화되며 사실에 의해 뒷받침됩니다. 질의응답 시 lexical-graph는 진술 그룹을 검색하여 LLM에 컨텍스트 창으로 제시합니다.

lexical-graph는 토픽과 소스별로 그룹화된 진술 세트에 대해 하이브리드 하향식 및 상향식 유사도 및 그래프 기반 검색을 수행하기 위해 [traversal 기반 검색](./traversal-based-search.md) 전략을 사용합니다. (lexical-graph에는 향후 버전에서 폐기될 가능성이 있는 [semantic-guided search](./semantic-guided-search.md) 접근 방식도 포함되어 있습니다.)

쿼리는 [메타데이터 필터링](./metadata-filtering.md)과 [멀티 테넌시](multi-tenancy.md)를 지원합니다. 메타데이터 필터링을 사용하면 lexical graph를 쿼리할 때 메타데이터 필터 및 관련 값을 기반으로 제한된 소스, 토픽 및 진술 세트를 검색할 수 있습니다. 멀티 테넌시를 사용하면 동일한 백엔드 graph 및 vector 스토어에 호스팅된 서로 다른 lexical graph를 쿼리할 수 있습니다.

참고:

  - [Traversal 기반 검색](./traversal-based-search.md)
  - [Traversal 기반 검색 구성 및 튜닝](./traversal-based-search-configuration.md)
  - [메타데이터 필터링](./metadata-filtering.md)
  - [멀티 테넌시](./multi-tenancy.md)
