[[Home](./)]

## 인덱싱

### 주제

  - [개요](#overview)
    - [Extract](#extract)
    - [Build](#build)
  - [LexicalGraphIndex를 사용하여 그래프 구축](#using-the-lexicalgraphindex-to-construct-a-graph)
    - [연속 수집](#continous-ingest)
    - [extract 및 build 단계를 별도로 실행](#run-the-extract-and-build-stages-separately)
    - [extract 및 build 단계 구성](#configuring-the-extract-and-build-stages)
    - [커스텀 프롬프트](#custom-prompts)
    - [배치 추출](#batch-extraction)
    - [메타데이터 필터링](#metadata-filtering)
    - [버전 관리 업데이트](#versioned-updates)
    - [체크포인트](#checkpoints)

### 개요

인덱싱에는 extract와 build 두 단계가 있습니다. lexical-graph는 이러한 각 단계에 대해 별도의 파이프라인과 마이크로 배칭을 사용하여 연속 수집 기능을 제공합니다. 이는 추출이 시작된 직후 그래프가 채워지기 시작한다는 것을 의미합니다.

extract 및 build 파이프라인을 함께 실행하여 위에 설명한 연속 수집을 제공할 수 있습니다. 또는 두 파이프라인을 별도로 실행하여 먼저 파일 기반 chunk로 추출한 다음 나중에 이 chunk에서 그래프를 빌드할 수 있습니다.

`LexicalGraphIndex`를 사용하면 extract 및 build 파이프라인을 함께 또는 별도로 실행할 수 있습니다. 아래 [LexicalGraphIndex를 사용하여 그래프 구축](#using-the-lexicalgraphindex-to-construct-a-graph) 섹션을 참조하세요.

인덱싱은 동일한 백엔드 graph 및 vector 스토어에 별도의 lexical graph를 저장할 수 있는 [멀티 테넌시](multi-tenancy.md)를 지원합니다.

#### 코드 예제

여기의 코드 예제는 Jupyter 노트북에서 실행되도록 포맷되어 있습니다. 메인 진입점이 있는 애플리케이션을 구축하는 경우, 애플리케이션 로직을 메서드 안에 넣고 [`if __name__ == '__main__'` 블록](./faq.md#runtimeerror-please-use-nest_asyncioapply-to-allow-nested-event-loops)을 추가하세요.

#### Extract

추출 단계는 기본적으로 3단계 프로세스입니다:

  1. 소스 문서가 chunk로 분할됩니다.
  2. 각 chunk에 대해 LLM이 비정형 콘텐츠에서 명제 세트를 추출합니다. 이 명제 추출은 복잡한 문장을 단순한 문장으로 분리하고, 대명사를 구체적인 이름으로 바꾸고, 가능한 경우 약어를 대체하여 콘텐츠를 '정리'하고 후속 엔티티/토픽/진술/사실 추출을 개선합니다. 이러한 명제는 chunk의 메타데이터에 `aws::graph::propositions` 키 아래에 추가됩니다.
  3. 명제 추출 후, 두 번째 LLM 호출이 추출된 명제 세트에서 엔티티, 관계, 토픽, 진술 및 사실을 추출합니다. 이러한 세부 사항은 chunk의 메타데이터에 `aws::graph::topics` 키 아래에 추가됩니다.

여기서 세 번째 단계만 필수입니다. 소스 데이터가 이미 chunk로 분할된 경우, 1단계를 생략할 수 있습니다. LLM 호출 감소와 성능 개선을 위해 엔티티/토픽/진술/사실 추출의 품질 감소를 감수할 의향이 있다면, 2단계를 생략할 수 있습니다.

추출은 추출 프로세스가 선호하는 엔티티 분류 목록으로 시드되는 가볍게 안내되는 전략을 사용합니다. LLM은 새로운 분류를 만들기 전에 목록에서 기존 분류를 사용하도록 지시받습니다. LLM이 도입한 새로운 분류는 후속 호출에 전달됩니다. 이 접근 방식은 엔티티 분류의 원치 않는 변형을 줄이지만 완전히 제거하지는 못합니다.

추출 프로세스를 시드하는 데 사용되는 `DEFAULT_ENTITY_CLASSIFICATIONS` 목록은 [여기](https://github.com/awslabs/graphrag-toolkit/blob/main/src/graphrag_toolkit/indexing/constants.py)에서 찾을 수 있습니다. 이러한 분류가 워크로드에 적합하지 않은 경우 교체할 수 있습니다 (아래 [extract 및 build 단계 구성](#configuring-the-extract-and-build-stages) 섹션 참조).

관계 값은 현재 안내되지 않습니다(상대적으로 간결하지만).

#### Build

build 단계에서는 extract 단계에서 내보낸 LlamaIndex chunk 노드가 개별 소스, chunk, 토픽, 진술 및 사실 LlamaIndex 노드의 스트림으로 더 분해됩니다. 그래프 구축 및 vector 인덱싱 핸들러가 이러한 노드를 처리하여 그래프 콘텐츠를 빌드하고 인덱싱합니다. 각 노드에는 vector store에서 노드를 인덱싱하는 데 사용할 수 있는 데이터가 포함된 `aws::graph::index` 메타데이터 항목이 있습니다(현재 구현에서는 chunk 및 statement 노드만 실제로 인덱싱됩니다).

### LexicalGraphIndex를 사용하여 그래프 구축

`LexicalGraphIndex`는 연속 수집 또는 별도의 extract 및 build 단계를 통해 그래프를 구축하는 편리한 수단을 제공합니다. `LexicalGraphIndex`를 구성할 때 graph store와 vector store를 제공해야 합니다 (자세한 내용은 [스토리지 모델](./storage-model.md) 참조). 아래 예제에서는 graph store 및 vector store 연결 문자열이 환경 변수에서 가져옵니다.

`LexicalGraphIndex` 생성자에는 `extraction_dir` 명명 인수가 있습니다. 이것은 중간 결과물(예: [체크포인트](#checkpoints))이 기록될 로컬 디렉토리 경로입니다. 기본적으로 `extraction_dir`의 값은 'output'으로 설정됩니다.

#### 연속 수집

`LexicalGraphIndex.extract_and_build()`를 사용하여 연속 수집을 지원하는 방식으로 그래프를 추출하고 빌드합니다.

추출 단계는 LlamaIndex 노드를 소비합니다 - 추출 중에 chunk로 분할될 문서 또는 미리 chunk로 분할된 텍스트 노드입니다. LlamaIndex 리더를 사용하여 [소스 문서를 로드](https://docs.llamaindex.ai/en/stable/understanding/loading/loading/)합니다. 아래 예제는 LlamaIndex `SimpleWebReader`를 사용하여 여러 HTML 페이지를 로드합니다.

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

from llama_index.readers.web import SimpleWebPageReader

doc_urls = [
    'https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html'
]

docs = SimpleWebPageReader(
    html_to_text=True,
    metadata_fn=lambda url:{'url': url}
).load_data(doc_urls)

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store,
        vector_store
    )

    graph_index.extract_and_build(docs)
```

#### extract 및 build 단계를 별도로 실행

`LexicalGraphIndex`를 사용하면 extract 및 build 단계를 별도로 수행할 수 있습니다. 이는 그래프를 한 번 추출한 다음 여러 번 빌드하려는 경우(예: 다른 환경에서)에 유용합니다.

extract 및 build 단계를 별도로 실행할 때, extract 단계 끝에 추출된 문서를 Amazon S3 또는 파일 시스템에 저장한 다음, build 단계에서 이러한 동일한 문서를 사용할 수 있습니다. graphrag-toolkit의 `S3BasedDocs` 및 `FileBasedDocs` 클래스를 사용하여 JSON 직렬화된 LlamaIndex 노드를 저장하고 검색합니다.

다음 예제는 extract 단계 끝에 `S3BasedDocs` 핸들러를 사용하여 추출된 문서를 Amazon S3 버킷에 저장하는 방법을 보여줍니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.indexing.load import S3BasedDocs

from llama_index.readers.web import SimpleWebPageReader

extracted_docs = S3BasedDocs(
    region='us-east-1',
    bucket_name='my-bucket',
    key_prefix='extracted',
    collection_id='12345',
    s3_encryption_key_id='arn:aws:kms:us-east-1:222222222222:key/99169dcb-12ce-4493-942b-1523125d7339'
)

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store,
        vector_store
    )

    doc_urls = [
        'https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html'
    ]

    docs = SimpleWebPageReader(
        html_to_text=True,
        metadata_fn=lambda url:{'url': url}
    ).load_data(doc_urls)

    graph_index.extract(docs, handler=extracted_docs)
```

extract 단계 후, 이전에 추출된 문서에서 그래프를 빌드할 수 있습니다. extract 단계에서 `S3BasedDocs` 객체가 추출된 문서를 저장하는 핸들러 역할을 했던 반면, build 단계에서는 `S3BasedDocs` 객체가 LlamaIndex 노드의 소스 역할을 하므로 `build()` 메서드의 첫 번째 인수로 전달됩니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.indexing.load import S3BasedDocs

docs = S3BasedDocs(
    region='us-east-1',
    bucket_name='my-bucket',
    key_prefix='extracted',
    collection_id='12345',
    s3_encryption_key_id='arn:aws:kms:us-east-1:222222222222:key/99169dcb-12ce-4493-942b-1523125d7339'
)

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store,
        vector_store
    )

    graph_index.build(docs)
```

`S3BasedDocs` 객체에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 필수 |
| ------------- | ------------- | ------------- |
| `region` | S3 버킷이 위치한 AWS 리전 (예: `us-east-1`) | 예 |
| `bucket_name` | Amazon S3 버킷 이름 | 예 |
| `key_prefix` | S3 키 접두사 | 예 |
| `collection_id` | 특정 추출된 문서 컬렉션의 ID. 선택 사항: `collection_id`가 제공되지 않으면 lexical-graph가 타임스탬프 값을 생성합니다. 추출된 문서는 `s3://<bucket>/<key_prefix>/<collection_id>/`에 기록됩니다. | 아니오 |
| `s3_encryption_key_id` | 객체 암호화에 사용할 KMS 키 ID (Key ID, Key ARN 또는 Key Alias). 선택 사항: `s3_encryption_key_id`가 제공되지 않으면 lexical-graph는 Amazon S3 관리형 키를 사용하여 S3의 객체를 암호화합니다. | 아니오 |

Amazon Web Services KMS 키를 사용하여 S3의 객체를 암호화하는 경우, lexical-graph가 실행되는 ID에 다음 IAM 정책이 포함되어야 합니다. `<kms-key-arn>`을 객체를 암호화하는 데 사용할 KMS 키의 ARN으로 바꾸세요:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
            	"kms:GenerateDataKey",
            	"kms:Decrypt"
            ],
            "Resource": [
            	"<kms-key-arn>"
            ],
            "Effect": "Allow"
        }
    ]
}
```

S3 버킷 대신 로컬 파일 시스템에 추출된 문서를 저장하려면 `FileBasedDocs` 객체를 대신 사용하세요:

```python
from graphrag_toolkit.lexical_graph.indexing.load import FileBasedDocs

chunks = FileBasedDocs(
    docs_directory='./extracted/',
    collection_id='12345'
)
```

`FileBasedChunks` 객체에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 필수 |
| ------------- | ------------- | ------------- |
| `docs_directory` | 추출된 문서의 루트 디렉토리 | 예 |
| `collection_id` | 특정 추출된 문서 컬렉션의 ID. 선택 사항: `collection_id`가 제공되지 않으면 lexical-graph가 타임스탬프 값을 생성합니다. 추출된 문서는 `/<docs_directory>/<collection_id>/`에 기록됩니다. | 아니오 |


#### extract 및 build 단계 구성

`GraphRAGConfig` 객체를 사용하여 `LexicalGraphIndex`의 extract 및 build 단계에 대한 워커 수와 배치 크기를 구성할 수 있습니다. 구성 객체 사용에 대한 자세한 내용은 [구성](./configuration.md)을 참조하세요.

워커와 배치 크기를 구성하는 것 외에도, `LexicalGraphIndex` 생성자에 `IndexingConfig` 인스턴스를 전달하여 chunking, 명제 추출 및 엔티티 분류, 그리고 graph 및 vector store 내용에 대한 인덱싱 프로세스를 구성할 수 있습니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex, IndexingConfig, ExtractionConfig

...

graph_index = LexicalGraphIndex(
    graph_store,
    vector_store,
    indexing_config = IndexingConfig(
      chunking=None,
      extraction=ExtractionConfig(
        enable_proposition_extraction=False
      )

    )
)
```

`IndexingConfig` 객체에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 기본값 |
| ------------- | ------------- | ------------- |
| `chunking` | 소스 문서를 chunking하는 데 사용할 노드 파서 목록(예: LlamaIndex `SentenceSplitter`). chunking을 건너뛰려면 `chunking`을 `None`으로 설정하세요. | `chunk_size=256` 및 `chunk_overlap=20`인 `SentenceSplitter` |
| `extraction` | 추출 옵션을 지정하는 `ExtractionConfig` 객체 | 기본값을 가진 `ExtractionConfig` |
| `batch_config` | [배치 추출](./batch-extraction.md)을 수행하는 경우 사용할 배치 구성. `batch_config`가 `None`이면 툴킷은 chunk 단위 추출을 수행합니다. | `None` |

`ExtractionConfig` 객체에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 기본값 |
| ------------- | ------------- | ------------- |
| `enable_proposition_extraction` | 토픽, 진술, 사실 및 엔티티를 추출하기 전에 명제 추출을 수행합니다 | `True` |
| `preferred_entity_classifications` | 엔티티 추출을 시드하는 데 사용되는 쉼표로 구분된 선호 엔티티 분류 목록 | `DEFAULT_ENTITY_CLASSIFICATIONS` |
| `infer_entity_classifications` | 중요한 도메인 엔티티 분류를 식별하기 위해 문서를 사전 처리할지 결정합니다. `True` 또는 `False`, 또는 `InferClassificationsConfig` 객체를 제공하세요. | `False` |
| `extract_propositions_prompt_template` | chunk에서 명제를 추출하는 데 사용되는 프롬프트. `None`이면 [기본 명제 추출 템플릿](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L29-L72)이 사용됩니다. 아래 [커스텀 프롬프트](#custom-prompts) 참조. | `None` |
| `extract_topics_prompt_template` | chunk에서 토픽, 진술 및 엔티티를 추출하는 데 사용되는 프롬프트. `None`이면 [기본 토픽 추출 템플릿](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L74-L191)이 사용됩니다. 아래 [커스텀 프롬프트](#custom-prompts) 참조. | `None` |


`InferClassificationsConfig` 객체에는 다음 매개변수가 있습니다:

| 매개변수  | 설명 | 기본값 |
| ------------- | ------------- | ------------- |
| `num_iterations` | 소스 문서에 대한 사전 처리를 실행할 횟수 | 1 |
| `num_samples` | 반복당 분류가 추출되는 chunk 수(무작위 선택) | 5 |
| `prompt_template` | 샘플링된 chunk에서 분류를 추출하는 데 사용되는 프롬프트. `None`이면 [기본 도메인 엔티티 분류 템플릿](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L4-L27)이 사용됩니다. 아래 [커스텀 프롬프트](#custom-prompts) 참조. | `None` |


#### 커스텀 프롬프트

extract 단계는 최대 세 가지 LLM 프롬프트를 사용합니다:

  - [**도메인 엔티티 분류:**](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L4-L27) 문서를 처리하기 전에 소스 문서 샘플에서 중요한 도메인 엔티티 분류를 추출합니다. 이러한 분류는 선호하는 엔티티 분류 목록으로 토픽 추출 프롬프트에 제공됩니다.
  - [**명제 추출:**](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L29-L72) chunk에서 독립적이고 잘 구성된 명제 세트를 추출합니다.
  - [**토픽 추출:**](https://github.com/awslabs/graphrag-toolkit/blob/main/lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/prompts.py#L74-L191) 명제 세트 또는 원시 chunk 텍스트에서 토픽, 진술, 엔티티 및 그 관계를 추출합니다.

`ExtractionConfig` 및 `InferClassificationsConfig`를 사용하여 이러한 프롬프트 중 하나 이상을 사용자 정의할 수 있습니다.

**도메인 엔티티 분류:**

프롬프트 템플릿에는 샘플링된 chunk가 삽입될 `{text_chunks}` 플레이스홀더가 포함되어야 합니다.

템플릿은 다음 형식으로 분류를 반환해야 합니다:

```
<entity_classifications>
Classification1
Classification2
Classification3
</entity_classifications>
```

**명제 추출:**

프롬프트 템플릿에는 chunk 텍스트가 삽입될 `{text}` 플레이스홀더가 포함되어야 합니다.

템플릿은 다음 형식으로 명제를 반환해야 합니다:

```
proposition
proposition
proposition
```

**토픽 추출:**

프롬프트 템플릿에는 명제 세트(또는 원시 chunk 텍스트)가 삽입될 `{text}` 플레이스홀더, 토픽 목록이 삽입될 `{preferred_topics}` 플레이스홀더, 엔티티 분류 목록이 삽입될 `{preferred_entity_classifications}` 플레이스홀더가 포함되어야 합니다.

템플릿은 다음 형식으로 추출된 토픽, 진술, 엔티티 및 관계를 반환해야 합니다:

```
topic: topic

  entities:
    entity|classification
    entity|classification

  proposition: [exact proposition text]
    entity-attribute relationships:
    entity|RELATIONSHIP|attribute
    entity|RELATIONSHIP|attribute

    entity-entity relationships:
    entity|RELATIONSHIP|entity
    entity|RELATIONSHIP|entity

  proposition: [exact proposition text]
    entity-attribute relationships:
    entity|RELATIONSHIP|attribute
    entity|RELATIONSHIP|attribute

    entity-entity relationships:
    entity|RELATIONSHIP|entity
    entity|RELATIONSHIP|entity
```


#### 배치 추출

인덱싱 프로세스의 extract 단계에서 [Amazon Bedrock 배치 추론](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html)을 사용할 수 있습니다. 자세한 내용은 [배치 추출](./batch-extraction.md)을 참조하세요.

#### 메타데이터 필터링

수집 시 소스 문서에 메타데이터를 추가하고, 이 메타데이터를 사용하여 extract 및 build 단계에서 문서를 필터링할 수 있습니다. 소스 메타데이터는 lexical graph를 쿼리할 때 메타데이터 필터링에도 사용됩니다. 자세한 내용은 [메타데이터 필터링](./metadata-filtering.md) 섹션을 참조하세요.

#### 버전 관리 업데이트

lexical graph는 [버전 관리 업데이트](./versioned-updates.mds)를 지원합니다. 버전 관리 업데이트를 사용하면, 마지막으로 추출된 이후 내용 및/또는 메타데이터가 변경된 문서를 다시 수집할 경우, 이전 문서는 아카이브되고 새로 수집된 문서가 소스 문서의 현재 버전으로 처리됩니다.

#### 체크포인트

lexical-graph는 성공하지 못한 upsert 작업과 LLM 및 embedding 모델 호출을 재시도합니다. 그러나 실패는 여전히 발생할 수 있습니다. extract 또는 build 단계가 중간에 실패한 경우, 일반적으로 전체 그래프 구축 파이프라인을 성공적으로 통과한 chunk를 다시 처리하고 싶지 않을 것입니다.

이전 실행에서 성공적으로 처리된 chunk를 다시 처리하지 않으려면, `extract_and_build()`, `extract()` 및/또는 `build()` 메서드에 `Checkpoint` 인스턴스를 제공하세요. 체크포인트는 extract 및 build 단계의 단계에 체크포인트 *필터*를, build 단계의 끝에 체크포인트 *작성기*를 추가합니다. chunk가 그래프 구축 *및* vector 인덱싱 핸들러에 의해 성공적으로 처리된 후 build 단계에서 내보내지면, 해당 ID가 그래프 인덱스 `extraction_dir`의 저장 지점에 기록됩니다. 동일한 ID를 가진 chunk가 이후 extract 또는 build 단계에 도입되면, 체크포인트 필터에 의해 필터링됩니다.

다음 예제는 `extract_and_build()` 메서드에 체크포인트를 전달합니다:

```python
from graphrag_toolkit.lexical_graph.indexing.build import Checkpoint

checkpoint = Checkpoint('my-checkpoint')

...

graph_index.extract_and_build(docs, checkpoint=checkpoint)
```

`Checkpoint`를 생성할 때 이름을 지정해야 합니다. 체크포인트 필터는 동일한 이름의 체크포인트 작성기에 의해 체크포인트된 chunk만 필터링합니다. [별도의 extract 및 build 프로세스를 실행](#run-the-extract-and-build-stages-separately)할 때 체크포인트를 사용하는 경우, 체크포인트에 다른 이름을 사용하세요. 별도의 extract 및 build 프로세스에 동일한 이름을 사용하면, build 단계가 extract 단계에서 생성된 모든 chunk를 무시합니다.

체크포인트는 트랜잭션 보장을 제공하지 않습니다. chunk가 그래프 구축 핸들러에 의해 성공적으로 처리되었지만 vector 인덱싱 핸들러에서 실패한 경우, build 파이프라인의 끝까지 도달하지 못하므로 체크포인트되지 않습니다. build 단계가 재시작되면, chunk가 그래프 구축 및 vector 인덱싱 핸들러 모두에 의해 다시 처리됩니다. upsert를 지원하는 스토어(예: Amazon Neptune Database 및 Amazon Neptune Analytics)의 경우 이는 문제가 되지 않습니다.

lexical-graph는 체크포인트를 정리하지 않습니다. 체크포인트를 사용하는 경우, 오래된 체크포인트 파일의 체크포인트 디렉토리를 주기적으로 정리하세요.
