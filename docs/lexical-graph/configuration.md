[[Home](./)]

## 구성

### 주제

  - [개요](#overview)
  - [GraphRAGConfig](#graphragconfig)
    - [LLM 구성](#llm-configuration)
    - [Embedding 모델 구성](#embedding-model-configuration)
    - [배치 쓰기](#batch-writes)
    - [Amazon Bedrock LLM 응답 캐싱](#caching-amazon-bedrock-llm-responses)
  - [로깅 구성](#logging-configuration)
  - [AWS 프로필 구성](#aws-profile-configuration)

### 개요

lexical-graph는 인덱싱 및 검색 프로세스에서 사용하는 LLM과 embedding 모델, 그리고 인덱싱 파이프라인의 병렬 및 배치 처리 동작을 구성할 수 있는 `GraphRAGConfig` 객체를 제공합니다. (lexical-graph는 LlamaIndex `Settings` 객체를 사용하지 않습니다: `Settings`에서 구성된 속성은 graphrag-toolkit에 영향을 미치지 않습니다.)

lexical-graph는 또한 애플리케이션 내에서 로깅 수준을 설정하고 로깅 필터를 적용할 수 있게 합니다.

### GraphRAGConfig

`GraphRAGConfig`를 사용하면 LLM, embedding 모델, extract 및 build 프로세스를 구성할 수 있습니다.

**중요**: 이러한 값을 변경하려면, graph store 또는 vector store를 생성하기 전에 코드 초반에 설정하세요.

구성에는 다음 매개변수가 포함됩니다:

| 매개변수  | 설명 | 기본값 | 환경 변수 |
| ------------- | ------------- | ------------- | ------------- |
| `extraction_llm` | 그래프 추출에 사용되는 LLM ([LLM 구성](#llm-configuration) 참조) | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | `EXTRACTION_MODEL` |
| `response_llm` | 응답 생성에 사용되는 LLM ([LLM 구성](#llm-configuration) 참조) | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | `RESPONSE_MODEL` |
| `embed_model` | 인덱싱된 데이터와 쿼리에 대한 embedding을 생성하는 데 사용되는 Embedding 모델 ([Embedding 모델 구성](#embedding-model-configuration) 참조) | `cohere.embed-english-v3` | `EMBEDDINGS_MODEL` |
| `embed_dimensions` | 각 vector의 차원 수 | `1024` | `EMBEDDINGS_DIMENSIONS` |
| `extraction_num_workers` | extract 단계를 실행할 때 사용할 병렬 프로세스 수 | `2` | `EXTRACTION_NUM_WORKERS` |
| `extraction_num_threads_per_worker` | extract 단계에서 각 프로세스가 사용하는 스레드 수 | `4` | `EXTRACTION_NUM_THREADS_PER_WORKER` |
| `extraction_batch_size` | extract 단계에서 모든 워커에 걸쳐 병렬로 처리할 입력 노드 수 | `4` | `EXTRACTION_BATCH_SIZE` |
| `build_num_workers` | build 단계를 실행할 때 사용할 병렬 프로세스 수 | `2` | `BUILD_NUM_WORKERS` |
| `build_batch_size` | build 단계에서 모든 워커에 걸쳐 병렬로 처리할 입력 노드 수 | `4` | `BUILD_BATCH_SIZE` |
| `build_batch_write_size` | graph 및 vector 스토어에 대량 작업으로 기록할 요소 수 ([배치 쓰기](#batch-writes) 참조) | `25` | `BUILD_BATCH_WRITE_SIZE` |
| `batch_writes_enabled` | 워커 단위로, 입력 노드 배치에서 내보낸 모든 요소(노드 및 엣지, 또는 vector)를 대량 작업으로 기록할지 개별적으로 기록할지 결정합니다 ([배치 쓰기](#batch-writes) 참조) | `True` | `BATCH_WRITES_ENABLED` |
| `include_domain_labels` | 엔티티가 [그래프 모델의](./graph-model.md#entity-relationship-tier) `__Entity__` 레이블 외에 도메인 특정 레이블(예: `Company`)을 가질지 결정합니다 | `False` | `DEFAULT_INCLUDE_DOMAIN_LABELS` |
| `enable_cache` | Amazon Bedrock 모델에 대한 LLM 호출 결과가 로컬 파일 시스템에 캐시될지 결정합니다 ([Amazon Bedrock LLM 응답 캐싱](#caching-amazon-bedrock-llm-responses) 참조) | `False` | `ENABLE_CACHE` |
| `aws_profile` | Bedrock 및 기타 서비스에 대한 요청을 인증하는 데 사용되는 AWS CLI 명명된 프로필 | *None* | `AWS_PROFILE` |
| `aws_region` | Bedrock 서비스 호출 범위를 지정하는 데 사용되는 AWS 리전 | `us-east-1` | `AWS_REGION` |

애플리케이션 코드에서 구성 매개변수를 설정하려면:

```python
from graphrag_toolkit.lexical_graph import GraphRAGConfig

GraphRAGConfig.response_llm = 'anthropic.claude-3-haiku-20240307-v1:0'
GraphRAGConfig.extraction_num_workers = 4
```

위 표의 변수 이름에 따라 환경 변수를 통해서도 구성 매개변수를 설정할 수 있습니다.

#### LLM 구성

`extraction_llm` 및 `response_llm` 구성 매개변수는 세 가지 유형의 값을 허용합니다:

  - LlamaIndex `LLM` 객체의 인스턴스를 전달할 수 있습니다. 이를 통해 Amazon Bedrock 이외의 LLM 백엔드에 대해 lexical-graph를 구성할 수 있습니다.
  - Amazon Bedrock 모델 또는 [추론 프로필](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles.html)의 모델 ID를 전달할 수 있습니다. 예: `anthropic.claude-3-7-sonnet-20250219-v1:0` (모델 ID) 또는 `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (추론 프로필).
  - LlamaIndex `BedrockConverse` 인스턴스의 JSON 문자열 표현을 전달할 수 있습니다. 예:

  ```
  {
    "model": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "temperature": 0.0,
    "max_tokens": 4096,
    "streaming": true
  }
  ```

#### Embedding 모델 구성

`embed_model` 구성 매개변수는 세 가지 유형의 값을 허용합니다:

  - LlamaIndex `BaseEmbedding` 객체의 인스턴스를 전달할 수 있습니다. 이를 통해 Amazon Bedrock 이외의 embedding 백엔드에 대해 lexical-graph를 구성할 수 있습니다.
  - Amazon Bedrock 모델의 모델 이름을 전달할 수 있습니다. 예: `amazon.titan-embed-text-v1`.
  - LlamaIndex `Bedrock` 인스턴스의 JSON 문자열 표현을 전달할 수 있습니다. 예:

  ```
  {
    "model_name": "amazon.titan-embed-text-v2:0",
    "dimensions": 512
  }
  ```

embedding 모델을 구성할 때는 `embed_dimensions` 구성 매개변수도 설정해야 합니다.

#### 배치 쓰기

lexical-graph는 소스 데이터를 extract 및 build 단계를 통해 진행하기 위해 마이크로배칭을 사용합니다.

  - extract 단계에서는 소스 노드 배치가 하나 이상의 워커에 의해 병렬로 처리되며, 각 워커는 할당된 소스 노드에 대해 chunking, 명제 추출 및 토픽/진술/사실/엔티티 추출을 수행합니다. 주어진 소스 노드 배치에 대해, extract 단계는 해당 소스 노드에서 파생된 chunk 컬렉션을 내보냅니다.
  - build 단계에서는 extract 단계의 chunk가 소스, chunk, 토픽, 진술 및 사실을 나타내는 더 작은 *인덱싱 가능한* 노드로 분해됩니다. 이러한 인덱싱 가능한 노드는 그래프 구축 및 vector 인덱싱 핸들러에 의해 처리됩니다.

`batch_writes_enabled` 구성 매개변수는 수신 chunk 배치에서 파생된 모든 인덱싱 가능한 노드가 graph 및 vector 스토어에 개별적으로 기록될지 대량 작업으로 기록될지를 결정합니다. 대량/배치 작업은 build 단계의 처리량을 개선하는 경향이 있지만, 이 데이터를 쿼리할 수 있게 되기까지 약간의 추가 지연이 발생합니다.

#### Amazon Bedrock LLM 응답 캐싱

Amazon Bedrock을 사용하는 경우, 로컬 파일 시스템을 사용하여 LLM 응답을 캐시하고 재사용할 수 있습니다. `GraphRAGConfig.enable_cache`를 `True`로 설정하세요. LLM 응답은 `cache` 디렉토리에 일반 텍스트로 저장됩니다. 동일한 모델에 정확히 동일한 프롬프트로 후속 호출하면 캐시된 응답이 반환됩니다.

쿼리 엔진의 스트리밍 응답은 캐시되지 _않습니다_.

`cache` 디렉토리는 특히 매우 큰 수집에 대한 추출 응답을 캐싱하는 경우 매우 커질 수 있습니다. lexical-graph는 이 디렉토리의 크기를 관리하거나 이전 항목을 삭제하지 않습니다. 캐시를 활성화하면 캐시 디렉토리를 정기적으로 정리하거나 가지치기하세요.

### 로깅 구성

`graphrag_toolkit`은 애플리케이션에서 로깅을 구성하기 위한 두 가지 메서드를 제공합니다. 이 메서드들을 사용하면 로깅 수준을 설정하고, 특정 모듈이나 메시지를 포함하거나 제외하는 필터를 적용하며, 로깅 동작을 사용자 정의할 수 있습니다:

- `set_logging_config`
- `set_advanced_logging_config`

#### set_logging_config

`set_logging_config` 메서드를 사용하면 로깅 수준 및 모듈 필터와 같은 기본 옵션 세트로 로깅을 구성할 수 있습니다. 모듈 이름에 와일드카드가 지원되며, 포함 또는 제외 모듈에 단일 문자열 또는 문자열 목록을 전달할 수 있습니다. 예:

```python
from graphrag_toolkit.lexical_graph import set_logging_config

set_logging_config(
  logging_level='DEBUG',  # or logging.DEBUG
  debug_include_modules='graphrag_toolkit.lexical_graph.storage',  # single string or list of strings
  debug_exclude_modules=['opensearch', 'boto']  # single string or list of strings
)
```

#### set_advanced_logging_config

`set_advanced_logging_config` 메서드는 로깅 수준에 따라 포함 및 제외 모듈이나 메시지에 대한 필터를 지정하는 기능을 포함하여 더 고급 로깅 구성 옵션을 제공합니다. 와일드카드는 모듈 이름에만 지원되며, 모듈에 단일 문자열 또는 문자열 목록을 전달할 수 있습니다. 이 메서드는 로깅 동작에 대해 더 큰 유연성과 제어를 제공합니다.

##### 매개변수

| 매개변수           | 타입                          | 설명                                                                                 | 기본값  |
|---------------------|-------------------------------|---------------------------------------------------------------------------------------------|----------------|
| `logging_level`     | `str` 또는 `int`                | 적용할 로깅 수준 (예: `'DEBUG'`, `'INFO'`, `logging.DEBUG` 등).              | `logging.INFO` |
| `included_modules`  | `dict[int, str \| list[str]]` | 로깅에 포함할 모듈, 로깅 수준별로 그룹화. 와일드카드 지원.           | `None`         |
| `excluded_modules`  | `dict[int, str \| list[str]]` | 로깅에서 제외할 모듈, 로깅 수준별로 그룹화. 와일드카드 지원.         | `None`         |
| `included_messages` | `dict[int, str \| list[str]]` | 로깅에 포함할 특정 메시지, 로깅 수준별로 그룹화. 와일드카드 지원. | `None`         |
| `excluded_messages` | `dict[int, str \| list[str]]` | 로깅에서 제외할 특정 메시지, 로깅 수준별로 그룹화.                        | `None`         |

##### 사용 예제

다음은 `set_advanced_logging_config` 사용 방법의 예입니다:

```python
import logging
from graphrag_toolkit.lexical_graph import set_advanced_logging_config

set_advanced_logging_config(
    logging_level=logging.DEBUG,
    included_modules={
        logging.DEBUG: 'graphrag_toolkit',  # single string or list of strings
        logging.INFO: '*',  # wildcard supported
    },
    excluded_modules={
        logging.DEBUG: ['opensearch', 'boto', 'urllib'],  # single string or list of strings
        logging.INFO: ['opensearch', 'boto', 'urllib'],  # wildcard supported
    },
    excluded_messages={
        logging.WARNING: 'Removing unpickleable private attribute',  # single string or list of strings
    }
)
```

### AWS 프로필 구성

Bedrock 클라이언트 또는 `GraphRAGConfig`의 다른 AWS 서비스 클라이언트를 초기화할 때 사용할 AWS CLI 프로필과 리전을 명시적으로 구성할 수 있습니다. 이를 통해 로컬 개발, EC2/ECS 환경, 또는 AWS SSO와 같은 페더레이션 환경 간의 호환성을 보장합니다.

애플리케이션 코드에서 AWS 프로필과 리전을 설정할 수 있습니다:

```python
from graphrag_toolkit.lexical_graph import GraphRAGConfig

GraphRAGConfig.aws_profile = 'padmin'
GraphRAGConfig.aws_region = 'us-east-1'
```

또는 환경 변수를 사용하세요:

```bash
export AWS_PROFILE=padmin
export AWS_REGION=us-east-1
```

프로필이나 리전이 명시적으로 설정되지 않으면, 시스템은 환경 변수로 폴백하거나 기본 AWS CLI 구성을 사용합니다.

`GraphRAGConfig` 클래스를 활용하여 lexical-graph에서 **AWS 명명된 프로필**을 구성하고 사용하는 방법에 대한 자세한 내용은 [`GraphRAGConfig`에서 AWS 프로필 사용하기](./aws-profile.md)를 참조하세요.
