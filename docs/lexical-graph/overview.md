[[Home](./)]

## 개요

graphrag-toolkit [lexical-graph](../../lexical-graph/) 라이브러리는 비정형 데이터로부터 [계층적 lexical graph](graph-model.md)(소스 문서에서 추출된 여러 수준의 세분화된 텍스트 요소를 나타내는 그래프)의 구축을 자동화하고, 사용자 질문에 답변할 때 이 그래프를 쿼리하는 질의응답 전략을 구성하기 위한 프레임워크를 제공합니다.

  - [스토어 및 모델 제공자](#stores-and-model-providers)
  - [인덱싱 및 쿼리](#indexing-and-querying)
    - [인덱싱](#indexing)
    - [쿼리](#querying)
  - [멀티 테넌시](#multi-tenancy)
  - [메타데이터 필터링](#metadata-filtering)
  - [버전 관리 업데이트](#versioned-updates)
  - [Model Context Protocol 서버](#model-context-protocol-server)
  - [보안](#security)
  - [하이브리드 배포](#hybrid-deployment)
  - [시작하기](#getting-started)

### 스토어 및 모델 제공자

lexical-graph 라이브러리는 세 가지 백엔드 시스템에 의존합니다: [_graph store_](./storage-model.md#graph-store), [_vector store_](./storage-model.md#vector-store), 그리고 _파운데이션 모델 제공자_입니다. graph store는 애플리케이션이 비정형 텍스트 기반 소스에서 추출된 lexical graph를 저장하고 쿼리할 수 있게 합니다. vector store는 lexical graph의 일부 요소에 대한 embedding이 포함된 하나 이상의 인덱스를 포함합니다. 이러한 embedding은 주로 라이브러리가 그래프 쿼리를 실행할 때 그래프의 시작점을 찾는 데 사용됩니다. 파운데이션 모델 제공자는 정보를 추출하고 embedding하는 데 사용되는 Large Language Models (LLMs)과 embedding 모델을 호스팅합니다.

이 라이브러리는 [Amazon Neptune Analytics](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html), [Amazon Neptune Database](https://docs.aws.amazon.com/neptune/latest/userguide/intro.html), [Neo4j](https://neo4j.com/docs/)에 대한 내장 graph store 지원과 Neptune Analytics, [Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html), [Amazon S3 Vectors](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html), pgvector 확장이 포함된 Postgres에 대한 내장 vector store 지원을 제공합니다. 파운데이션 모델 제공자로는 Amazon Bedrock을 사용하도록 구성되어 있습니다. 이러한 기본값 외에도, 라이브러리는 다른 서드파티 백엔드를 지원하도록 확장할 수 있습니다.

### 인덱싱 및 쿼리

lexical-graph 라이브러리는 두 가지 상위 수준 프로세스를 구현합니다: [_인덱싱_](./indexing.md)과 [_쿼리_](./querying.md). 인덱싱 프로세스는 비정형 텍스트 기반 소스 문서에서 정보를 수집하고 추출한 다음 그래프와 함께 vector 인덱스를 구축합니다. 쿼리 프로세스는 그래프와 vector 인덱스에서 콘텐츠를 검색한 다음, 이 콘텐츠를 LLM에 컨텍스트로 제공하여 사용자 질문에 답변합니다.

#### 인덱싱

인덱싱 프로세스는 두 개의 파이프라인 단계로 더 세분화됩니다: [_extract_](./indexing.md#extract)와 [_build_](./indexing.md#build). extract 단계는 비정형 소스에서 데이터를 수집하고, 콘텐츠를 chunk로 나누고, LLM을 사용하여 이러한 chunk에서 토픽, 진술, 사실 및 엔티티 세트를 추출합니다. build 단계는 extract 단계의 결과를 사용하여 그래프를 채우고 일부 콘텐츠에 대한 embedding을 생성하고 인덱싱합니다.

추출은 chunk당 두 번의 LLM 호출을 사용합니다. 첫 번째 호출은 chunk된 텍스트에서 잘 구성되고 자립적인 명제 세트를 추출하여 콘텐츠를 '정리'합니다. 두 번째 호출은 이러한 명제에서 토픽, 진술, 사실, 엔티티 및 그 관계를 추출합니다. 명제 추출은 선택 사항입니다: 두 번째 LLM 호출은 원시 콘텐츠에 대해 수행할 수 있지만, 명제 추출을 먼저 수행하면 추출 품질이 향상되는 경향이 있습니다.

전체 인덱싱 프로세스는 마이크로 배칭 방식을 사용하여 extract 및 build 파이프라인을 통해 데이터를 진행합니다. 이를 통해 호스트 애플리케이션은 extract 파이프라인에서 내보낸 추출된 정보를 파일 시스템이나 Amazon S3에 저장하거나 콘텐츠를 검사하고, 필요한 경우 build 파이프라인에서 사용하기 전에 추출된 요소를 필터링하고 변환할 수 있습니다. 인덱싱은 연속 수집 방식으로 실행하거나 별도의 extract 및 build 단계로 실행할 수 있습니다. 두 모드 모두 Amazon Bedrock의 배치 추론 기능을 활용하여 문서 컬렉션에 대해 [배치 추출](./batch-extraction.md)을 수행할 수 있습니다.

다음 다이어그램은 인덱싱 프로세스의 상위 수준 보기를 보여줍니다:

![인덱싱](../../images/extract-and-build.png)
#### 쿼리

[쿼리](./querying.md)는 _검색_과 _생성_으로 구성된 2단계 프로세스입니다. 검색은 사용자 질문에 답변하는 데 관련된 콘텐츠를 가져오기 위해 그래프 및 vector 스토어를 쿼리합니다. 생성은 이 콘텐츠를 LLM에 컨텍스트로 제공하여 응답을 생성합니다. lexical-graph 쿼리 엔진은 애플리케이션이 검색 작업만 단독으로 적용하여 그래프에서 가져온 검색 결과를 단순히 반환하거나, 검색 결과를 검색한 후 응답을 생성하는 엔드투엔드 쿼리를 실행할 수 있게 합니다.

lexical-graph는 여러 문서에 분산된 주제적으로 관련된 정보를 검색하기 위해 [traversal 기반 검색](./traversal-based-search.md) 전략을 사용합니다.

다음 다이어그램은 엔드투엔드 쿼리 프로세스의 상위 수준 보기를 보여줍니다:

![쿼리](../../images/question-answering.png)

쿼리 단계:

  1. 애플리케이션이 lexical graph 쿼리 엔진에 사용자 질문을 제출합니다.
  2. 엔진이 사용자 질문에 대한 embedding을 생성합니다.
  3. 이 embedding은 vector store에서 embedding된 콘텐츠에 대해 topK vector 유사도 검색을 수행하는 데 사용됩니다.
  4. 유사도 검색 결과는 그래프에서 관련 콘텐츠를 검색하는 하나 이상의 그래프 쿼리를 앵커링하는 데 사용됩니다.
  5. 엔진은 이 검색된 콘텐츠를 사용자 질문과 함께 LLM에 제공하고, LLM이 응답을 생성합니다.
  6. 쿼리 엔진은 이 응답을 애플리케이션에 반환합니다.

### 멀티 테넌시

lexical-graph 라이브러리의 [멀티 테넌시](./multi-tenancy.md) 기능은 애플리케이션이 동일한 기본 graph 및 vector 스토어에서 여러 개의 별도 lexical graph를 호스팅할 수 있게 합니다. 테넌트 그래프는 서로 다른 도메인, 문서 컬렉션 또는 개별 사용자에 해당할 수 있습니다.

### 메타데이터 필터링

lexical-graph는 [메타데이터 필터링](./metadata-filtering.md)을 지원합니다. 메타데이터 필터링은 메타데이터 필터와 관련 값에 기반하여 그래프를 쿼리할 때 검색되는 소스, 토픽 및 진술의 세트를 제한합니다.

메타데이터 필터링에는 두 가지 부분이 있습니다:

  - **인덱싱** 인덱싱 프로세스에 전달되는 소스 문서에 메타데이터를 추가합니다
  - **쿼리** lexical graph를 쿼리할 때 메타데이터 필터를 제공합니다

메타데이터 필터링은 인덱싱 프로세스의 [extract 및 build 단계에서 문서와 chunk를 필터링](./metadata-filtering.md#using-metadata-to-filter-documents-in-the-extract-and-build-stages)하는 데에도 사용할 수 있습니다.

#### 버전 관리 업데이트

lexical graph는 [버전 관리 업데이트](./versioned-updates.mds)를 지원합니다. 버전 관리 업데이트를 사용하면, 마지막으로 추출된 이후 내용 및/또는 메타데이터가 변경된 문서를 다시 수집할 경우, 이전 문서는 아카이브되고 새로 수집된 문서가 소스 문서의 현재 버전으로 처리됩니다. 그런 다음 graph 및 vector 스토어의 현재 상태를 쿼리하거나, 특정 시점에 현재였던 문서를 검색하도록 쿼리를 구성할 수 있습니다.

### Model Context Protocol 서버

[Model Context Protocol](https://modelcontextprotocol.io/introduction) (MCP)은 애플리케이션이 LLM에 컨텍스트를 제공하는 방법을 표준화하는 오픈 프로토콜입니다.

lexical-graph는 멀티 테넌트 그래프에서 테넌트당 하나의 도구로 구성된 '카탈로그'를 생성할 수 있습니다. 각 도구는 해당 테넌트 그래프의 데이터를 기반으로 도메인별 질문에 답변할 수 있습니다. 이 카탈로그는 MCP 서버를 통해 클라이언트에 공개됩니다. 클라이언트(일반적으로 에이전트 및 LLM)는 카탈로그를 탐색하고 정보 목표에 적합한 도구를 선택할 수 있습니다.

카탈로그의 각 도구에는 클라이언트가 도구의 도메인, 범위, 잠재적 용도 및 다루는 질문 유형을 이해하는 데 도움이 되는 자동 생성된 설명이 함께 제공됩니다. 카탈로그에는 엔티티 또는 개념의 이름이 주어지면 해당 검색어에 대한 지식이 있는 하나 이상의 도메인 도구를 추천하는 '검색' 도구도 포함되어 있습니다.

### 보안

lexical-graph 라이브러리를 사용하는 구현자는 인덱싱하려는 데이터 소스에 대한 접근을 보호하고, Neptune 및 OpenSearch와 같은 라이브러리에서 사용하는 기본 AWS 리소스를 프로비저닝하고 보호할 책임이 있습니다. 문서에는 Amazon Neptune, Amazon OpenSearch Serverless 및 Amazon Bedrock에 대한 접근을 제어하기 위해 AWS Identity and Access Management (IAM) 정책을 사용하는 [가이드](./security.md)가 포함되어 있습니다.

lexical-graph 애플리케이션이 실행되는 ID에 적용된 정책과 관계없이, 라이브러리는 항상 AWS 리소스에 대한 요청에 Sigv4 서명을 합니다. 연결은 항상 TLS 버전 1.3을 사용합니다.

### 하이브리드 배포

위의 개요는 모든 작업, 인덱싱 및 쿼리가 클라우드 환경에서 수행된다고 가정합니다. 그러나 인덱싱 프로세스의 extract 및 build 단계 간의 분리는 하이브리드 배포 옵션을 가능하게 하며, 이를 통해 컨테이너화된 graph 및 vector 스토어를 사용한 비용 효율적인 로컬 개발과 SageMaker 및 Bedrock을 통한 높은 처리량의 LLM 추론을 수행할 수 있습니다. 자세한 내용은 [하이브리드 배포](./hybrid-deployment.md) 문서를 참조하세요.

### 시작하기

리포지토리와 함께 제공되는 [빠른 시작 AWS CloudFormation 템플릿](../../examples/lexical-graph/cloudformation-templates/) 중 하나를 사용하여 새로운 AWS 환경에서 빠르게 시작할 수 있습니다. 각 빠른 시작 템플릿은 라이브러리를 사용하여 콘텐츠를 인덱싱하고 쿼리하는 방법을 보여주는 여러 [예제 노트북](../../examples/lexical-graph/notebooks/)이 포함된 Amazon SageMaker 호스팅 Jupyter 노트북을 생성합니다.

CloudFormation 템플릿에 의해 배포된 리소스는 계정에 비용을 발생시킵니다. 불필요한 요금이 발생하지 않도록 사용을 마친 후 스택을 삭제하는 것을 잊지 마세요.

다음 템플릿 중에서 선택하세요:

  - [`graphrag-toolkit-neptune-analytics.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-analytics.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - Amazon Neptune Analytics 그래프
     - Amazon SageMaker 노트북
  - [`graphrag-toolkit-neptune-analytics-opensearch-serverless.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-analytics-opensearch-serverless.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - Amazon Amazon Neptune Analytics 그래프
     - 퍼블릭 엔드포인트가 있는 Amazon OpenSearch Serverless 컬렉션
     - Amazon SageMaker 노트북
  - [`graphrag-toolkit-neptune-analytics-aurora-postgres.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-analytics-aurora-postgres.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - 3개의 프라이빗 서브넷, 1개의 퍼블릭 서브넷 및 인터넷 게이트웨이가 있는 Amazon VPC
     - Amazon Neptune Analytics 그래프
     - 단일 서버리스 인스턴스가 있는 Amazon Aurora Postgres 데이터베이스 클러스터
     - Amazon SageMaker 노트북
  - [`graphrag-toolkit-neptune-analytics-s3-vectors.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-analytics-s3-vectors.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - Amazon Neptune Analytics 그래프
     - Amazon SageMaker 노트북
     - Amazon S3 Vectors 버킷
  - [`graphrag-toolkit-neptune-db-opensearch-serverless.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-db-opensearch-serverless.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - 3개의 프라이빗 서브넷, 1개의 퍼블릭 서브넷 및 인터넷 게이트웨이가 있는 Amazon VPC
     - 단일 Neptune 서버리스 인스턴스가 있는 Amazon Neptune Database 클러스터
     - 퍼블릭 엔드포인트가 있는 Amazon OpenSearch Serverless 컬렉션
     - Amazon SageMaker 노트북
  - [`graphrag-toolkit-neptune-db-aurora-postgres.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-db-aurora-postgres.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - 3개의 프라이빗 서브넷, 1개의 퍼블릭 서브넷 및 인터넷 게이트웨이가 있는 Amazon VPC
     - 단일 Neptune 서버리스 인스턴스가 있는 Amazon Neptune Database 클러스터
     - 단일 서버리스 인스턴스가 있는 Amazon Aurora Postgres 데이터베이스 클러스터
     - Amazon SageMaker 노트북
  - [`graphrag-toolkit-neptune-db-s3-vectors.json`](../../examples/lexical-graph/cloudformation-templates/graphrag-toolkit-neptune-db-s3-vectors.json)은 다음과 같은 lexical-graph 환경을 생성합니다:
     - 3개의 프라이빗 서브넷, 1개의 퍼블릭 서브넷 및 인터넷 게이트웨이가 있는 Amazon VPC
     - 단일 Neptune 서버리스 인스턴스가 있는 Amazon Neptune Database 클러스터
     - Amazon SageMaker 노트북
     - Amazon S3 Vectors 버킷
