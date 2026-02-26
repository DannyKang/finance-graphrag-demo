[[Home](./)]

## 버전 관리 업데이트

### 목차

  - [개요](#overview)
  - [문서 서브그래프](#document-subgraphs)
    - [안정적인 문서 식별](#stable-document-identities)
  - [버전 관리 업데이트 사용하기](#using-versioned-updates)
    - [인덱싱](#indexing)
    - [쿼리](#querying)
    - [버전 관리 업데이트와 metadata 필터링 결합하기](#combining-versioned-updates-with-metadata-filtering)
  - [예제](#example)
  - [소스 metadata 검사하기](#inspecting-source-metadata)
    - [모든 소스 노드의 세부 정보 가져오기](#get-details-of-all-source-nodes)
    - [모든 현재 소스 노드의 세부 정보 가져오기](#get-details-of-all-current-source-nodes)
    - [모든 이전 소스 노드의 세부 정보 가져오기](#get-details-of-all-previous-source-nodes)
    - [특정 metadata가 있는 파일의 이전 버전 세부 정보 가져오기](#get-details-of-previous-versions-of-files-with-specific-metadata)
  - [문서 삭제하기](#deleting-documents)
    - [소스 id로 문서 삭제하기](#deleting-documents-by-source-id)
    - [문서의 모든 이전 버전 삭제하기](#deleting-all-previous-versions-of-a-document)
    - [버전별 metadata가 있는 문서 삭제하기](#deleting-a-document-with-version-specific-metadata)
  - [버전 관리 문서 자동 삭제](#automatically-delete-versioned-documents)
    - [삭제 보호 구현하기](#implementing-deletion-protection)
  - [기존 graph 및 vector store 업그레이드하기](#upgrading-existing-graph-and-vector-stores)
    - [특정 tenant 업그레이드하기](#upgrading-specific-tenants)
    - [특정 vector 인덱스 업그레이드하기](#upgrading-specific-vector-indexes)

### 개요

graphrag-toolkit을 사용하면 _extraction_ 타임스탬프를 기반으로 단일 타임라인을 따라 소스 문서의 버전을 관리할 수 있습니다. 이 버전 관리 업데이트 기능을 사용하면 마지막으로 추출된 이후 내용 및/또는 metadata가 변경된 문서를 다시 수집할 경우, 이전 문서는 아카이브되고 새로 수집된 문서가 소스 문서의 현재 버전으로 처리됩니다.

### 문서 서브그래프

lexical graph 모델의 `(source)<--(chunk)<--(topic)<--(statement)` 부분은 경계가 있는 문서 서브그래프를 나타냅니다. 소스 노드의 id는 소스 문서의 metadata와 텍스트 내용의 함수입니다. chunk, 토픽 및 statement의 id는 차례로 소스 id의 함수입니다. 소스 문서의 metadata 및/또는 내용이 변경되고 문서가 다시 처리되면 소스에 다른 id가 할당됩니다 – 그리고 해당 소스에서 파생된 모든 chunk, 토픽 및 statement도 마찬가지입니다.

![Versionable Subgraph](../../images/versionable-unit.png)

이는 서로 다른 시간에 문서의 두 가지 다른 버전(즉, 다른 내용 및/또는 metadata를 가진 버전)을 추출하면 두 개의 서로 다른 경계가 있는 문서 서브그래프가 생긴다는 것을 의미합니다: 두 개의 소스 노드, 그리고 각 소스 노드 아래에 독립적인 `(chunk)<--(topic)<--(statement)` 서브그래프. 툴킷의 버전 관리 기능이 활성화되면, 마지막으로 추출된 문서 버전이 현재 버전으로 처리되고 다른 모든 버전은 이력, 아카이브 버전으로 표시됩니다.

#### 안정적인 문서 식별

이 방식으로 문서의 버전을 관리하려면 서로 다른 텍스트 및 metadata 집합이 _동일한_ 문서의 _서로 다른_ 버전을 나타낸다는 것을 지정하는 방법이 있어야 합니다. 즉, 문서는 내용 및/또는 metadata의 변동과 무관하게 안정적인 식별을 가져야 합니다.

graphrag-toolkit은 이 안정적인 식별을 나타내기 위해 _버전 독립적 metadata 필드_라는 개념을 사용합니다. 문서를 인덱싱할 때 해당 문서의 어떤 metadata 필드가 안정적인 식별을 나타내는지 지정할 수 있습니다. 예를 들어, 문서에 `title`, `author`, `last_updated` metadata 필드가 있는 경우, `title`과 `author` metadata 필드의 조합이 해당 문서의 안정적인 식별을 나타내도록 지정할 수 있습니다. 문서가 인덱싱될 때, `title`과 `author` 필드 _값_이 새로 수집된 문서와 일치하는 이전에 인덱싱된 비버전 관리 문서는 아카이브됩니다.

> **중요** 서로 다른 문서의 안정적인 식별을 나타내기 위해 선택하는 metadata 필드는 문서의 버전 관리에 큰 영향을 미칩니다. 특정 버전 독립적 필드 값의 집합은 다른 문서를 포함하지 않고 특정 문서의 모든 버전과 일치해야 합니다. URI는 종종 웹 페이지를 고유하게 식별하기에 충분하지만, 파일 이름은 항상 파일을 고유하게 식별하지 못할 수 있습니다 - 예를 들어, `readme.md`라는 이름의 파일이 많습니다. 버전 독립적 metadata 필드 집합이 너무 느슨하면 잘못된 문서의 버전을 관리하거나 - 더 나쁜 경우 삭제할 - 위험이 있습니다. 의심스러운 경우 인덱싱하는 각 문서에 합성 문서 id metadata 필드를 추가하는 것을 고려하세요.

### 버전 관리 업데이트 사용하기

버전 3.14 이전의 graphrag-toolkit 버전으로 구축된 기존 graph 및 vector store가 있는 경우 먼저 업그레이드해야 합니다. [기존 graph 및 vector store 업그레이드하기](#upgrading-existing-graph-and-vector-stores)를 참조하세요.

#### 인덱싱

인덱싱된 문서는 _extraction_ 타임스탬프를 기반으로 버전이 관리됩니다. 문서는 추출된 타임스탬프부터 `valid_from`이 됩니다. 이후 문서의 다른 버전이 인덱싱되면 이전 버전은 새 버전의 extraction 타임스탬프까지 `valid_to`로 간주됩니다.

데이터를 _추출_할 때(`LexicalGraphIndex.extract()` 또는 `LexicalGraphIndex.extract_and_build()` 사용), 업데이트하고 버전을 관리하려는 각 문서의 metadata에 _버전 독립적 metadata 필드_의 이름을 추가해야 합니다. 

lexical graph를 _구축_할 때(`LexicalGraphIndex.build()` 또는 `LexicalGraphIndex.extract_and_build()` 사용), `GraphRAGConfig.enable_versioning=True` 전역 구성 매개변수를 사용하거나, `BuildConfig(enable_versioning=True)` 구성 객체를 `LexicalGraphIndex` 생성자에 전달하거나, `LexicalGraphIndex.build()` 또는 `LexicalGraphIndex.extract_and_build()` 메서드에 `enable_versioning=True`를 전달하여 버전 관리를 활성화해야 합니다. 

`enable_versioning=True`의 존재는 build 프로세스가 extract 단계에서 제공된 버전 독립적 metadata 필드로 식별되는 각 문서의 이전 버전을 확인하도록 강제합니다.

다음 예제는 `LexicalGraphIndex.extract_and_build()`를 사용하여 로컬 디렉토리에서 데이터를 추출하고 lexical graph를 구축합니다. `get_file_metadata()` 함수는 `default_file_metadata_func()`에 의해 생성된 metadata를 래핑하여 `file_name`과 `file_path` metadata 필드가 함께 버전 독립적 식별자로 작동함을 나타냅니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex, GraphRAGConfig
from graphrag_toolkit.lexical_graph import add_versioning_info
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

from llama_index.core import SimpleDirectoryReader
from llama_index.core.readers.file.base import default_file_metadata_func

GraphRAGConfig.enable_versioning = True

def get_file_metadata(file_path):
    metadata = default_file_metadata_func(file_path)
    return add_versioning_info(metadata, id_fields=['file_name', 'file_path'])

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store
    )
    
    reader = SimpleDirectoryReader(input_dir='./my_docs/', file_metadata=get_file_metadata)
    
    docs = reader.load_data()
    graph_index.extract_and_build(docs)
```

위 예제는 `GraphRAGConfig.enable_versioning = True`를 사용하여 build 단계에서 버전 관리 확인을 강제합니다. 또는 `BuildConfig` 객체를 제공할 수 있습니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex, BuildConfig

graph_index = LexicalGraphIndex(
  graph_store, 
  vector_store,
  indexing_config=BuildConfig(enable_versioning=True)
)
```

또는 build 메서드에 `enable_versioning=True` 키워드 인수를 전달할 수 있습니다:

```python
graph_index.extract_and_build(
  docs,
  enable_versioning=True
)
```

##### 모든 문서에 id 필드를 지정해야 하나요?

아니요. 업데이트하고 버전을 관리하려는 문서에 대해서만 버전 독립적 metadata 필드의 이름을 지정하면 됩니다. 문서를 처음 인덱싱할 때 이러한 필드를 지정할 필요는 없지만(지정할 수는 있음), 문서를 재인덱싱할 때만 필요합니다.

버전 관리 업데이트 기능을 사용할 것으로 예상되는 경우, 향후 업데이트되고 버전이 관리될 수 있는 모든 문서가 버전 독립적 metadata 필드로 작동할 수 있는 metadata 필드를 포함하도록 해야 합니다. 소스 문서가 lexical graph에 추가된 후에는 첨부된 metadata를 추가하거나 수정할 수 없습니다. 이는 향후 버전이 관리될 수 있는 데이터를 수집할 때 미리 계획해야 함을 의미합니다.

#### 쿼리

lexical graph를 쿼리할 때 버전 관리 업데이트 기능을 활용하려면 `LexicalGraphQueryEngine`을 생성할 때 `GraphRAGConfig.enable_versioning=True` 전역 구성 매개변수 또는 `versioning` 키워드 인수를 사용해야 합니다. `versioning` 키워드 인수는 boolean 또는 `VersioningConfig` 객체를 허용합니다. 후자를 사용하면 이력 타임스탬프를 지정하여 특정 시점의 그래프 상태를 쿼리할 수 있습니다.

버전 관리를 사용하도록 지정하지 않으면 쿼리 엔진은 lexical graph의 모든 버전 관리 정보를 무시하는 응답을 생성합니다.

다음 예제는 `GraphRAGConfig.enable_versioning = True`를 사용하여 lexical graph의 현재 상태에 대해 쿼리합니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine, GraphRAGConfig

GraphRAGConfig.enable_versioning = True

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, 
        vector_store
    )
    
    response = query_engine.query('Which instance families are available for Amazon Neptune?')
```

다음 예제는 `LexicalGraphQueryEngine`에 제공된 `versioning=True` 키워드 인수를 사용하여 lexical graph의 현재 상태에 대해 쿼리합니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, 
        vector_store,
        versioning=True
    )
    
    response = query_engine.query('Which instance families are available for Amazon Neptune?')
```

다음 예제는 `VersioningConfig` 객체를 사용하여 특정 시점의 lexical graph 이력 상태에 대해 쿼리합니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine, VersioningConfig

GraphRAGConfig.enable_versioning = True

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, 
        vector_store,
        versioning=VersioningConfig(at_timestamp=1761899971500)
    )
    
    response = query_engine.query('Which instance families are available for Amazon Neptune?')
```

#### 버전 관리 업데이트와 metadata 필터링 결합하기

버전 관리 업데이트와 metadata 필터링을 결합할 수 있습니다. Metadata 필터링을 사용하면 제어하는 도메인별 metadata를 기반으로 문서를 필터링할 수 있고, 버전 관리를 사용하면 extraction 타임라인을 따른 이력을 기반으로 문서를 필터링할 수 있습니다.

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.metadata import FilterConfig
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, 
        vector_store,
        versioning=True,
        filter_config = FilterConfig(
            MetadataFilter(
                key='url',
                value='https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
                operator=FilterOperator.EQ
            )
        )
    )
    
    response = query_engine.query('What are the differences between Neptune Database and Neptune Analytics?')
```

### 예제

다음 다이어그램은 네 번의 extraction 라운드를 보여줍니다:

![Versioning](../../images/versioning-1.png)

문서는 다음 순서로 삽입되고 버전이 관리됩니다:

| extraction 타임스탬프 | 소스 id | metadata | 버전 독립적 필드 | 대체 |
| --- | --- | --- | --- | --- |
| 1761899971000 | s1 | `{'doc_id': 'D1', 'revision': 1}` | | |
| | s2 | `{'title': 'T1', 'app': 'app_01', 'month': '06'}` | | |
| | s3 | `{'url': 'http://xyz', 'accessed': 'Mon'}` | | |
| 1761899972000 | s4 | `{'title': 'T1', 'app': 'app_01', 'month': '07'}` | `['title', 'app']` | s2 |
| | s5 | `{'url': 'http://xyz', 'accessed': 'Tues'}` | `['url']` | s3 |
| 1761899973000 | s6 | `{'url': 'http://xyz', 'accessed': 'Wed'}` | `['url']` | s5 |
| | s7 | `{'doc_id': 'D1', 'revision': 2}` | `['doc_id']` | s1 |
| 1761899974000 | s8 | `{'doc_id': 'D2', 'revision': 1}` | `['doc_id']` | |
| | s9 | `{'url': 'http://xyz', 'accessed': 'Mon'}` | `['url']` | s6 |

#### 현재 문서 쿼리하기

네 번의 extraction 라운드가 끝나면 문서 s7, s4, s8, s9가 현재로 간주됩니다:

![Current](../../images/versioning-2.png)

#### 특정 시점에서 쿼리하기

타임스탬프 1761899972500에서 쿼리하면 문서 s1, s4, s5가 현재로 간주됩니다:

![Historical](../../images/versioning-3.png)

### 소스 metadata 검사하기

`LexicalGraphIndex.get_sources()` 메서드를 사용하여 소스 노드에 첨부된 metadata 및 버전 관리 정보를 검사할 수 있습니다.

#### 모든 소스 노드의 세부 정보 가져오기

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    sources = graph_index.get_sources()
    
    print(json.dumps(sources, indent=2))
```

결과는 다음과 같이 포맷됩니다:

```json
[
  {
    "metadata": {
      "file_path": "/home/myuser/docs/readme.md",
      "creation_date": "2025-12-16T00:00:00.000Z",
      "file_name": "readme.md",
      "title": "How to play",
      "file_size": 93,
      "last_modified_date": "2025-12-16T00:00:00.000Z",
      "file_type": "text/markdown",
      "version": "v1"
    },
    "versioning": {
      "build_timestamp": 1765880067513,
      "id_fields": [
        "file_name",
        "title"
      ],
      "valid_from": 1761899971000,
      "valid_to": 1761899972000,
      "extract_timestamp": 1765880063557
    },
    "sourceId": "aws:tenant123:31141440:6de6"
  },
  {
    "metadata": {
      "file_path": "/home/myuser/docs/readme.md",
      "creation_date": "2025-12-16T00:00:00.000Z",
      "file_name": "readme.md",
      "title": "How to play",
      "file_size": 91,
      "last_modified_date": "2025-12-16T00:00:00.000Z",
      "file_type": "text/markdown",
      "version": "v2"
    },
    "versioning": {
      "build_timestamp": 1765880102994,
      "id_fields": [
        "file_name",
        "title"
      ],
      "valid_from": 1761899972000,
      "valid_to": 1761899973000,
      "extract_timestamp": 1765880098515
    },
    "sourceId": "aws:tenant123:34570f12:0726"
  },
  {
    "metadata": {
      "file_path": "/home/myuser/docs/readme.md",
      "creation_date": "2025-12-16T00:00:00.000Z",
      "file_name": "readme.md",
      "title": "How to play",
      "file_size": 93,
      "last_modified_date": "2025-12-16T00:00:00.000Z",
      "file_type": "text/markdown",
      "version": "v3"
    },
    "versioning": {
      "build_timestamp": 1765880173432,
      "id_fields": [
        "file_name",
        "title"
      ],
      "valid_from": 1761899973000,
      "valid_to": 1761899974000,
      "extract_timestamp": 1765880166001
    },
    "sourceId": "aws:tenant123:07ca52e6:8960"
  },
  {
    "metadata": {
      "file_path": "/home/myuser/docs/readme.md",
      "creation_date": "2025-12-16T00:00:00.000Z",
      "file_name": "readme.md",
      "title": "How to play",
      "file_size": 83,
      "last_modified_date": "2025-12-16T00:00:00.000Z",
      "file_type": "text/markdown",
      "version": "v4"
    },
    "versioning": {
      "build_timestamp": 1765880242134,
      "id_fields": [
        "file_name",
        "title"
      ],
      "valid_from": 1761899974000,
      "valid_to": 10000000000000,
      "extract_timestamp": 1765880236433
    },
    "sourceId": "aws:tenant123:7a54612d:57b8"
  }
]
```

#### 모든 현재 소스 노드의 세부 정보 가져오기

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.versioning import VersioningConfig, VersioningMode

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    versioning_config = VersioningConfig(versioning_mode=VersioningMode.CURRENT)
    
    sources = graph_index.get_sources(versioning_config=versioning_config)
    
    print(json.dumps(sources, indent=2))
```

#### 모든 이전 소스 노드의 세부 정보 가져오기

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.versioning import VersioningConfig, VersioningMode

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    versioning_config = VersioningConfig(versioning_mode=VersioningMode.PREVIOUS)
    
    sources = graph_index.get_sources(versioning_config=versioning_config)
    
    print(json.dumps(sources, indent=2))
```

#### 특정 metadata가 있는 파일의 이전 버전 세부 정보 가져오기

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.versioning import VersioningConfig, VersioningMode

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    versioning_config = VersioningConfig(versioning_mode=VersioningMode.PREVIOUS)
    
    sources = graph_index.get_sources(
        filter={
            'file_name': 'readme.md',
            'title': 'How to play'
        },
        versioning_config=versioning_config
    )
    
    print(json.dumps(sources, indent=2))
```

### 문서 삭제하기

`LexicalGraphIndex.delete_sources()` 메서드를 사용하여 개별 문서 서브그래프를 삭제할 수 있습니다.

> **경고** 문서 삭제는 파괴적인 작업입니다: 문서 서브그래프가 graph store에서 물리적으로 제거되고 embedding이 vector store에서 제거됩니다. `delete_sources()`를 실행하기 전에 `LexicalGraphIndex.get_sources()` 메서드를 사용하여 삭제될 소스를 확인할 수 있습니다. 추가 예방 조치로 삭제를 시작하기 전에 graph 및 vector store를 백업하는 것을 고려하세요. 다양한 graph 및 vector store 백엔드의 백업 프로세스는 툴킷의 범위 밖입니다.

`delete_sources()`는 `get_sources()`와 동일한 시그니처를 가집니다. `delete_sources()`를 실행하기 전에 `get_sources()`를 사용하여 삭제될 문서 버전을 검토할 수 있습니다.

버전 관리 문서가 삭제되면 소스 노드와 모든 chunk, 토픽 및 statement 노드가 lexical graph에서 삭제됩니다. 삭제 프로세스는 더 이상 하나 이상의 문서에 연결되지 않은 고아 fact 및 entity도 제거합니다.

#### 소스 id로 문서 삭제하기

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    deleted = graph_index.delete_sources(source_ids=[
      'aws:tenant123:31141440:6de6',
      'aws:tenant123:34570f12:0726'
    ])
    
    print(json.dumps(deleted, indent=2))
```

#### 문서의 모든 이전 버전 삭제하기

다음 예제는 버전 독립적 metadata 필드(이 경우 `file_name` 및 `title`)를 사용하여 특정 문서의 모든 버전(현재 및 이전)을 식별한 다음, `versioning_mode=VersioningMode.PREVIOUS`를 가진 versioning config를 사용하여 더 이상 현재가 아닌 해당 문서의 모든 버전으로 선택을 좁힙니다. 그런 다음 이러한 이전 버전의 문서가 삭제됩니다:

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.versioning import VersioningConfig, VersioningMode

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    versioning_config = VersioningConfig(versioning_mode=VersioningMode.PREVIOUS)
    
    deleted = graph_index.delete_sources(
        filter={
            'file_name': 'readme.md',
            'title': 'How to play'
        },
        versioning_config=versioning_config
    )
    
    print(json.dumps(deleted, indent=2))
```

#### 버전별 metadata가 있는 문서 삭제하기

다음 예제는 'How to play'이라는 제목의 `readme.md` 파일의 각 버전이 고유한 `version` metadata 값을 가지고 있다고 가정합니다(`version`은 인덱싱 시 애플리케이션이 제공하는 도메인별 metadata이며, 버전 관리 업데이트 기능이 사용하는 내부 버전 관리 metadata의 일부가 아닙니다). 여기서는 버전 관리 문서의 `v2` 버전을 삭제합니다.

```python
import os
import json

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

with (
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):

    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store,
        tenant_id='tenant123' # optional - uses default tenant if not specified
    )
    
    deleted = graph_index.delete_sources(
        filter={
            'file_name': 'readme.md',
            'title': 'How to play',
            'version': 'v2'
        }
    )
    
    print(json.dumps(deleted, indent=2))
```

### 버전 관리 문서 자동 삭제

`DeletePrevVersions` 노드 핸들러를 사용하여 build 프로세스가 버전 관리 문서를 자동으로 삭제하도록 구성할 수 있습니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex, GraphRAGConfig
from graphrag_toolkit.lexical_graph import add_versioning_info
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.indexing.build import DeletePrevVersions

from llama_index.core import SimpleDirectoryReader
from llama_index.core.readers.file.base import default_file_metadata_func

GraphRAGConfig.enable_versioning = True

def get_file_metadata(file_path):
    metadata = default_file_metadata_func(file_path)
    return add_versioning_info(metadata, id_fields=['file_name', 'file_path'])

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store
    )
    
    reader = SimpleDirectoryReader(input_dir='./my_docs/', file_metadata=get_file_metadata)  
    docs = reader.load_data()

    graph_index.extract_and_build(docs, handler=DeletePrevVersions(lexical_graph=graph_index))
```

> **경고** `DeletePrevVersions`를 주의해서 사용하세요. 버전 독립적 metadata 필드가 너무 느슨하면 잘못된 문서의 버전을 관리하고 삭제할 수 있습니다.

#### 삭제 보호 구현하기

`DeletePrevVersions`는 사용자 정의 필터 함수를 허용합니다. 이 함수는 삭제 후보인 각 버전 관리 문서의 metadata와 함께 호출됩니다. 함수가 `True`를 반환하면 문서가 삭제되고, `False`를 반환하면 문서가 삭제되지 않습니다. 이 사용자 정의 필터 함수와 사용자 정의 metadata 필드를 사용하여 삭제 보호를 구현할 수 있습니다. 다음 예제는 인덱싱할 각 문서에 `deletionProtection` metadata 필드를 추가합니다. 사용자 정의 필터 함수는 이 필드의 값을 확인합니다:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex, GraphRAGConfig
from graphrag_toolkit.lexical_graph import add_versioning_info
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.indexing.build import DeletePrevVersions

from llama_index.core import SimpleDirectoryReader
from llama_index.core.readers.file.base import default_file_metadata_func

GraphRAGConfig.enable_versioning = True

def get_file_metadata(file_path):
    metadata = default_file_metadata_func(file_path)
    metadata['deletionProtection'] = True # custom metadata field
    return add_versioning_info(metadata, id_fields=['file_name', 'file_path'])

def deletion_protection_filter_fn(metadata):
    deletion_protection = metadata.get('deletionProtection', False)
    return not deletion_protection 

with(
    GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
    VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
):
    graph_index = LexicalGraphIndex(
        graph_store, 
        vector_store
    )
    
    reader = SimpleDirectoryReader(input_dir='./my_docs/', file_metadata=get_file_metadata) 
    docs = reader.load_data()

    graph_index.extract_and_build(
      docs, 
      handler=DeletePrevVersions(
        lexical_graph=graph_index,
        filter_fn=deletion_protection_filter_fn # do not delete docs with deletionProtection == True
      )
    )
```

### 기존 graph 및 vector store 업그레이드하기

버전 3.14.x 이전의 graphrag-toolkit 버전으로 생성된 기존 graph 및 vector store가 있는 경우, 버전 관리 업데이트 기능을 사용하기 전에 업그레이드해야 합니다. graphrag-toolkit에는 버전 관리 업데이트를 사용할 수 있도록 graph 및 vector store를 업그레이드하는 `upgrade_for_versioning.py` 스크립트가 포함되어 있습니다.

> 업그레이드 스크립트가 실행되는 동안 문서를 인덱싱하지 마세요.

[`upgrade_for_versioning.py`](https://github.com/awslabs/graphrag-toolkit/blob/main/examples/lexical-graph/scripts/upgrade_for_versioning.py) 스크립트를 graph 및 vector store에 접근할 수 있는 환경에 다운로드하세요. 그런 다음 실행합니다:

```
python upgrade_for_versioning.py --graph-store <graph_store_info> --vector_store <vector_store_info>
```

#### 특정 tenant 업그레이드하기

기본적으로 스크립트는 graph 및 vector store의 모든 [tenant](./multi-tenancy.md)를 업그레이드합니다. `--tenant-ids <공백으로_구분된_tenant_id>` 매개변수를 사용하여 tenant 목록을 제한할 수 있습니다. 예를 들어:

```
python upgrade_for_versioning.py --graph-store <graph_store_info> --vector_store <vector_store_info> --tenant-ids t1 t2 _default
```

`_default`는 기본 tenant를 식별합니다.

#### 특정 vector 인덱스 업그레이드하기

기본적으로 스크립트는 각 tenant의 chunk 인덱스만 업데이트합니다. vector store에는 [semantic-guided search](./semantic-guided-search.md)에서 사용하는 statement 인덱스도 포함될 수 있습니다. Semantic-guided search는 향후 툴킷 버전에서 제거될 가능성이 높으므로, 불필요한 작업을 피하기 위해 이 인덱스를 업그레이드하지 _않는_ 것을 권장합니다.

그러나 statement 인덱스를 업그레이드하려면 `--index-names <공백으로_구분된_인덱스_이름>` 매개변수를 제공하세요:

```
python upgrade_for_versioning.py --graph-store <graph_store_info> --vector_store <vector_store_info> --index_names chunk statement
```
