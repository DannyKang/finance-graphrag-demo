
[[Home](./)]

## 하이브리드 배포

### 목차

  - [개요](#overview)
  - [스토어 및 모델 제공자](#stores-and-model-providers)
  - [인덱싱과 쿼리](#indexing-and-querying)
    - [인덱싱](#indexing)

### 개요

하이브리드 배포는 유연한 배포를 가능하게 합니다: SageMaker 및 Bedrock을 통한 고처리량 LLM inference, 그리고 컨테이너화된 graph/vector store를 사용한 비용 효율적인 로컬 개발.

### 스토어 및 모델 제공자

`lexical-graph` 라이브러리는 세 가지 백엔드 시스템에 의존합니다: [*graph store*](./storage-model.md#graph-store), [*vector store*](./storage-model.md#vector-store), 그리고 *기초 모델 제공자*. graph store는 비정형 텍스트 기반 소스로부터 구축된 lexical graph의 저장 및 쿼리를 가능하게 합니다. vector store는 그래프 요소에 대한 embedding이 포함된 하나 이상의 인덱스를 포함하며, 그래프 쿼리의 시작점을 식별하는 데 도움을 줍니다. 기초 모델 제공자는 extraction 및 embedding에 사용되는 Large Language Model(LLM)을 호스팅합니다.

이 라이브러리는 다음에 대한 기본 지원을 제공합니다:

* Graph store: [Amazon Neptune Database](https://docs.aws.amazon.com/neptune/latest/userguide/intro.html), [Amazon Neptune Analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html), 그리고 로컬 [FalkorDB](https://falkordb.com/) (Docker를 통해)
* Vector store: [Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html), [`pgvector`가 포함된 PostgreSQL](https://github.com/pgvector/pgvector), Neptune Analytics, 그리고 로컬 [`pgvector`가 포함된 PostgreSQL](https://github.com/pgvector/pgvector)
* 기초 모델 제공자: [Amazon Bedrock](https://aws.amazon.com/bedrock/)

이 하이브리드 구성은 유연한 배포를 가능하게 합니다: SageMaker 및 Bedrock을 통한 고처리량 LLM inference, 그리고 컨테이너화된 graph/vector store를 사용한 비용 효율적인 로컬 개발.

### 인덱싱과 쿼리

lexical-graph 라이브러리는 두 가지 상위 수준 프로세스를 구현합니다: [_인덱싱_](./indexing.md) 및 [_쿼리_](./querying.md). 인덱싱 프로세스는 비정형 텍스트 기반 소스 문서에서 정보를 수집하고 추출한 다음 그래프와 함께 제공되는 vector 인덱스를 구축합니다. 쿼리 프로세스는 그래프와 vector 인덱스에서 콘텐츠를 검색한 다음 이 콘텐츠를 LLM에 컨텍스트로 제공하여 사용자 질문에 답변합니다.

#### 인덱싱

인덱싱은 두 가지 파이프라인 단계로 나뉩니다: **Extract**와 **Build**.

**Extract** 단계는 **Docker를 사용하여 로컬에서 실행됩니다**:

* 문서를 로드하고 chunk로 분할합니다
* 두 가지 LLM 기반 extraction 단계를 수행합니다:

  * *Proposition extraction*: chunk로 분할된 텍스트를 잘 구성된 문장으로 변환합니다
  * *Topic/entity/fact extraction*: 관계와 개념을 식별합니다
* 추출된 결과를 단계 간 전송 매체 역할을 하는 **AWS S3 버킷**에 저장합니다

**Build** 단계는 변경 없이 그대로 유지됩니다.

![Indexing](../../images/hybrid-extract-and-build.png)