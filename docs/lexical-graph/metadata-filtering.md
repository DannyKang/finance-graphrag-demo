[[Home](./)]

## Metadata 필터링

### 목차

  - [개요](#overview)
  - [인덱싱 시 metadata 추가하기](#adding-metadata-when-indexing)
    - [Metadata와 버전 관리 업데이트](#metadata-and-versioned-uupdates)
    - [웹 페이지에 metadata 추가하기](#adding-metadata-to-web-pages)
    - [JSON 문서에 metadata 추가하기](#adding-metadata-to-json-documents)
    - [PDF 문서에 metadata 추가하기](#adding-metadata-to-pdf-documents)
    - [제한 사항](#restrictions)
  - [Metadata를 사용하여 쿼리 필터링하기](#using-metadata-to-filter-queries)
    - [Metadata 필터는 어떻게 적용되나요?](#how-are-metadata-filters-applied)
    - [복합 및 중첩 필터 표현식](#complex-and-nested-filter-expressions)
    - [지원되는 필터 연산자](#supported-filter-operators)
  - [날짜 및 datetime](#dates-and-datetimes)
  - [Extract 및 build 단계에서 metadata를 사용하여 문서 필터링하기](#using-metadata-to-filter-documents-in-the-extract-and-build-stages)
    - [Extract 단계에서 metadata 필터링 사용하기](#using-metadata-filtering-in-the-extract-stage)
    - [Build 단계에서 metadata 필터링 사용하기](#using-metadata-filtering-in-the-build-stage)
  - [Metadata와 문서 식별](#metadata-and-document-identity)
  - [Metadata 필터링과 multi-tenancy](#metadata-filtering-and-multi-tenancy)


### 개요

Metadata 필터링을 사용하면 lexical graph를 쿼리할 때 metadata 필터와 관련 값을 기반으로 제한된 소스, 토픽 및 statement 집합을 검색할 수 있습니다.

Metadata는 소스 문서의 metadata 딕셔너리에 추가된 모든 데이터입니다. 소스 문서에 따라 metadata의 예로는 `title`, `url`, `filepath`, `date published`, `author` 등이 있습니다. 소스 문서의 metadata는 해당 문서에서 추출된 모든 chunk, 토픽 및 statement와 연결됩니다.

Metadata 필터링에는 두 가지 부분이 있습니다:

  - **인덱싱** 인덱싱 프로세스에 전달되는 소스 문서에 metadata를 추가합니다
  - **쿼리** lexical graph를 쿼리할 때 metadata 필터를 제공합니다

인덱싱 프로세스의 [extract 및 build 단계에서 문서와 chunk를 필터링](#using-metadata-to-filter-documents-in-the-extract-and-build-stages)하는 데에도 metadata 필터링을 사용할 수 있습니다.

### 인덱싱 시 metadata 추가하기

쿼리 시 metadata 필터링의 효과는 수집 중 소스 문서에 첨부된 metadata의 품질에 달려 있습니다. [다양한 로더](https://docs.llamaindex.ai/en/stable/understanding/loading/loading/)는 수집된 문서에 metadata를 추가하는 서로 다른 메커니즘을 가지고 있습니다. 다음은 몇 가지 예입니다.

#### Metadata와 버전 관리 업데이트

lexical graph는 [버전 관리 업데이트](./versioned-updates.mds)를 지원합니다. 버전 관리 업데이트를 사용하면 마지막으로 추출된 이후 내용 및/또는 metadata가 변경된 문서를 다시 수집할 경우, 이전 문서는 아카이브되고 새로 수집된 문서가 소스 문서의 현재 버전으로 처리됩니다.

버전 관리 업데이트는 문서의 안정적인(즉, 버전 독립적인) 식별을 나타내기 위해 _버전 독립적 metadata 필드_라는 개념을 사용합니다. 문서를 인덱싱할 때 해당 문서의 어떤 metadata 필드가 안정적인 식별을 나타내는지 지정할 수 있습니다. 예를 들어, 문서에 `title`, `author`, `last_updated` metadata 필드가 있는 경우, `title`과 `author` metadata 필드의 조합이 해당 문서의 안정적인 식별을 나타내도록 지정할 수 있습니다. 문서가 인덱싱될 때, `title`과 `author` 필드 _값_이 새로 수집된 문서와 일치하는 이전에 인덱싱된 비버전 관리 문서는 아카이브됩니다.

각 소스 문서에 추가할 metadata를 선택할 때, 버전 관리 업데이트를 위한 metadata의 이러한 사용을 염두에 두세요. 필드 중 하나 또는 여러 필드 값의 조합이 안정적인 식별을 구성하도록 하세요.


#### 웹 페이지에 metadata 추가하기

LlamaIndex `SimpleWebPageReader`는 url을 받아 metadata 딕셔너리를 반환하는 함수를 허용합니다. 다음 예제는 metadata 딕셔너리를 url과 페이지에 접근한 날짜로 채웁니다.

```python
from datetime import date
from llama_index.readers.web import SimpleWebPageReader

doc_urls = [
    'https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html',
    'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html'
]

def web_page_metadata(url):
    return {
        'url': url, 
        'last_accessed_date': date.today()
    }

docs = SimpleWebPageReader(
    html_to_text=True,
    metadata_fn=web_page_metadata
).load_data(doc_urls)
```

#### JSON 문서에 metadata 추가하기

`JSONArrayReader`를 사용하면 JSON 배열 문서를 배열의 요소당 하나씩 별도의 문서로 분할하고 각 하위 문서에서 metadata를 추출할 수 있습니다. 다음 예제는 뉴스 기사가 포함된 JSON 소스 문서를 기사당 하나씩 별도의 문서로 분할합니다. `get_text()` 및 `get_metadata()` 함수는 각 기사의 본문 텍스트와 관련 metadata를 추출합니다.


```python
from graphrag_toolkit.lexical_graph.indexing.load import JSONArrayReader    

def get_text(data):
    return data.get('body', '')

def get_metadata(data):
	return { 
		field : data[field] 
		for field in ['title', 'author', 'source', 'published_date'] 
		if field in data
	}

docs = JSONArrayReader(
    text_fn=get_text, 
    metadata_fn=get_metadata
).load_data('./articles.json')
```

#### PDF 문서에 metadata 추가하기

다음 예제는 PDF 문서를 로드하고 각 문서에 metadata를 첨부하는 한 가지 방법을 보여줍니다.

```python
from pathlib import Path
from pypdf import PdfReader
from llama_index.core.schema import Document

def get_pdf_docs(pdf_dir):
    
    pdf_dir_path = Path(pdf_dir)
    
    file_paths = [
        file_path for file_path in pdf_dir_path.iterdir() 
        if file_path.is_file()
    ]

    for pdf_path in file_paths:
        reader = PdfReader(pdf_path)
        for page_num, page_content in enumerate(reader.pages):
            doc = Document(
                text=page_content.extract_text(), 
                metadata={
                    'filename': pdf_path.name, 
                    'page_num': page_num
                }
            )
            yield doc
    
docs = get_pdf_docs('./pdfs')
```

#### 제한 사항

Metadata 필드 값은 string, int, float, [date 및 datetime](#dates-and-datetimes) 단일 값으로 구성될 수 있습니다. 리스트, 배열, 집합 및 중첩 딕셔너리는 지원되지 않습니다.

### Metadata를 사용하여 쿼리 필터링하기

lexical graph는 필터 기준을 지정하기 위해 LlamaIndex vector store 타입인 `MetadataFilters`, `MetadataFilter`, `FilterOperator`, `FilterCondition`을 사용합니다. 이러한 항목을 `FilterConfig` 객체에 담아 쿼리 엔진에 제공합니다. 다음 예제는 소스 문서의 url을 기반으로 lexical graph를 필터링하도록 traversal-based retriever를 구성합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.metadata import FilterConfig
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    filter_config = FilterConfig(
        MetadataFilter(
            key='url',
            value='https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
            operator=FilterOperator.EQ
        )
    )
)
```

#### Metadata 필터는 어떻게 적용되나요?

쿼리 엔진에 제공하는 metadata 필터는 검색 프로세스의 두 지점에서 적용됩니다:

  - 필터는 모든 vector store top-k 쿼리에 적용됩니다. vector store는 일반적으로 그래프 순회의 시작점을 찾는 데 사용됩니다: 따라서 필터는 retriever의 그래프 진입점을 효과적으로 제한합니다.
  - 이후 필터는 그래프에서 반환된 모든 결과에 적용됩니다.

그래프는 본질적으로 서로 다른 소스를 연결할 수 있습니다: 순회는 한 소스에 속하는 토픽과 statement에서 완전히 다른 소스와 연결된 토픽과 statement로 이동할 수 있습니다. 따라서 단순히 순회의 시작점을 제한하는 것만으로는 충분하지 않으며, retriever는 결과도 필터링해야 합니다. metadata 필터의 이중 적용의 이점은 쿼리의 시작점을 제공하는 시맨틱 유사도 기반 검색을 잘 정의된 소스 집합으로 제한하되, 쿼리가 lexical graph의 구조적으로 관련이 있지만 시맨틱으로 유사하지 않은 부분에 접근할 수 있도록 허용한 다음, 최종적으로 필터 기준을 통과하는 요소만으로 결과를 제한한다는 것입니다.

#### 복합 및 중첩 필터 표현식

`FilterConfig` 객체의 생성자는 `MetadataFilters` 객체, 단일 `MetadataFilter` 또는 `MetadataFilter` 객체의 리스트를 허용합니다.

`MetadataFilters` 객체는 `MetadataFilter` 객체의 컬렉션과 다른 중첩된 `MetadataFilters` 객체를 보유할 수 있습니다. `MetadataFilters` 객체의 `filters` 컬렉션에 있는 요소들은 `FilterCondition.AND` 또는 `FilterCondition.OR` 조건을 사용하여 복합 조건을 형성하도록 연결됩니다.

`MetadataFilters`는 세 번째 조건인 `FilterCondition.NOT`도 지원합니다. `MetadataFilters` 객체에 `FilterCondition.NOT` 조건을 사용하는 경우, 해당 객체의 `filters` 컬렉션은 단일 중첩 `MetadataFilters` 객체를 포함해야 합니다.

다음 예제는 중첩된 `MetadataFilters` 객체를 사용하여 복합 조건을 표현하는 것을 보여줍니다: 소스가 `https://docs.aws.amazon.com/neptune/latest/userguide/intro.html`이거나, 발행일이 `2024-01-01`과 `2024-12-31` 사이에 있어야 합니다:

```python
FilterConfig(
    MetadataFilters(
        filters=[
            MetadataFilter(
                key='url',
                value='https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
                operator=FilterOperator.EQ
            ),
            MetadataFilters(
                filters=[
                    MetadataFilter(
                        key='pub_date',
                        value='2024-01-01',
                        operator=FilterOperator.GT
                    ),
                    MetadataFilter(
                        key='pub_date',
                        value='2024-12-31',
                        operator=FilterOperator.LT
                    )
                ],
                condition=FilterCondition.AND
            )
        ],
        condition=FilterCondition.OR
    )       
)
```

다음 예제는 `FilterCondition.NOT` 조건을 가진 중첩된 `MetadataFilters` 객체의 사용을 보여줍니다. 여기서 부정되는 `MetadataFilter`가 하나뿐이지만, `MetadataFilters` 객체 내에 중첩되어야 합니다.

```python
FilterConfig(
    MetadataFilters(
        filters=[
            MetadataFilters(
                filters=[
                    MetadataFilter(
                        key='url',
                        value='https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
                        operator=FilterOperator.EQ
                    )
                ]
            )
        ],
        condition=FilterCondition.NOT
    )       
)
```

#### 지원되는 필터 연산자

lexical graph는 다음 필터 연산자를 지원합니다:

| 연산자  | 설명 | 데이터 타입 |
| ------------- | ------------- | ------------- |
| `EQ` | 같음 - 기본 연산자 | string, int, float, date/datetime |
| `GT` | 보다 큼 | int, float, date/datetime |
| `LT` | 보다 작음 | int, float, date/datetime |
| `NE` | 같지 않음 | string, int, float, date/datetime |
| `GTE` | 크거나 같음 | int, float, date/datetime |
| `LTE` | 작거나 같음 | int, float, date/datetime |
| `TEXT_MATCH` | 전체 텍스트 매칭 (텍스트 필드 내에서 특정 부분 문자열, 토큰 또는 구문을 검색할 수 있음) | string |
| `TEXT_MATCH_INSENSITIVE` | 전체 텍스트 매칭 (대소문자 구분 없음) | string |
| `IS_EMPTY` | 필드가 존재하지 않음 ||

다음 연산자는 지원되지 않습니다:

| 연산자  | 설명 | 데이터 타입 |
| ------------- | ------------- | ------------- |
| `IN` | 배열 내에 있음 | string 또는 number |
| `NIN` | 배열 내에 없음 | string 또는 number |
| `ANY` | 하나라도 포함 | string 배열 |
| `ALL` | 모두 포함 | string 배열 |
| `CONTAINS` | Metadata 배열이 값(string 또는 number)을 포함 |  |

### 날짜 및 datetime

Metadata 필터링은 date 및 datetime 값에 의한 필터링을 지원합니다. 인덱싱 및 쿼리 중에 datetime 필터링이 적용되도록 하는 두 가지 방법이 있습니다:

  - 소스 문서에 첨부된 metadata 필드와 쿼리 시 적용되는 metadata 필터에 Python `date` 또는 `datetime` 객체를 제공합니다.
  - 필드 이름에 `_date` 또는 `_datetime` 접미사를 붙여 해당 필드가 datetime 값으로 처리되어야 함을 나타냅니다. 그런 다음 인덱싱 및 쿼리 시 `date` 또는 `datetime` 객체나 날짜 및 datetime 값의 문자열 표현을 제공할 수 있습니다.

build 단계에서 Python `date` 및 `datetime` metadata 값은 graph 및 vector store에 저장되기 전에 ISO 형식의 datetime 값으로 변환됩니다. 쿼리 중에도 Python `date` 및 `datetime` metadata 값은 필터에 적용되기 전에 마찬가지로 ISO 형식의 datetime 값으로 변환됩니다. `date` 및 `datetime` Python 객체는 값이 date 또는 datetime으로 처리되어야 함을 명시적으로 전달합니다. 이 접근 방식을 사용하면 metadata 필드 이름에 `_date` 또는 `_datetime` 접미사를 추가할 필요가 없습니다. 그러나 인덱싱과 쿼리 모두에서 `date` 및/또는 `datetime` 객체가 사용되도록 해야 합니다: 이러한 단계 중 하나가 날짜 또는 datetime의 문자열 표현을 받으면 필터링이 의도한 대로 작동하지 않을 수 있습니다.

`_date` 또는 `_datetime`으로 끝나는 metadata 필드는 graph 및 vector store에 저장되기 전에 ISO 형식의 datetime 값으로 변환됩니다. 마찬가지로, 키가 `_date` 또는 `_datetime`으로 끝나는 metadata 필터의 값은 평가되기 전에 ISO 형식의 datetime 값으로 변환됩니다.

### Extract 및 build 단계에서 metadata를 사용하여 문서 필터링하기

검색 프로세스를 제한하기 위해 metadata 필터링을 사용하는 것 외에도, 인덱싱 프로세스의 extract 및 build 단계에서 문서를 필터링하는 데에도 사용할 수 있습니다.

#### Extract 단계에서 metadata 필터링 사용하기

`ExtractionConfig` 객체의 `extraction_filters`에 필터 기준을 제공하여 extract 단계를 통과하는 문서를 필터링할 수 있습니다. `extraction_filters`는 `MetadataFilters` 객체, 단일 `MetadataFilter` 또는 `MetadataFilter` 객체의 리스트를 허용합니다.

다음 예제는 `amazon.com` 이메일 주소를 포함하는 `email` metadata 필드가 있는 문서만 extraction 파이프라인을 통과하도록 소스 문서를 필터링하는 방법을 보여줍니다. 다른 모든 소스 문서는 폐기됩니다.

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex, ExtractionConfig 
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

graph_index = LexicalGraphIndex(
    graph_store, 
    vector_store,
    indexing_config=ExtractionConfig(
        extraction_filters=MetadataFilter(
            key='email',
            value='amazon.com',
            operator=FilterOperator.TEXT_MATCH
        )       
    )
)
```

문서의 하위 집합에서만 lexical graph를 추출하고 싶지만 수집 프로세스에 제출되는 문서를 제어할 수 없는 경우 extract 단계 metadata 필터링을 사용하세요.

#### Build 단계에서 metadata 필터링 사용하기

`source_filters` 속성에 필터 기준이 포함된 `BuildFilters` 객체를 `BuildConfig` 객체에 제공하여 lexical graph를 구축하는 데 사용되는 문서를 필터링할 수 있습니다. `source_filters`는 `MetadataFilters` 객체, 단일 `MetadataFilter` 또는 `MetadataFilter` 객체의 리스트를 허용합니다.

다음 예제는 `url` metadata 필드에 `https://docs.aws.amazon.com/neptune/`이 포함된 문서만 build 파이프라인을 통과하도록 추출된 문서를 필터링하는 방법을 보여줍니다. 다른 모든 추출된 문서는 무시됩니다. 결과 lexical graph는 `neptune` tenant에 할당됩니다.

```python
from graphrag_toolkit.lexical_graph import LexicalGraphIndex, BuildConfig
from graphrag_toolkit.lexical_graph.indexing.build import BuildFilters
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

graph_index = LexicalGraphIndex(
    graph_store, 
    vector_store,
    indexing_config=BuildConfig(
        build_filters=BuildFilters(
            source_filters=MetadataFilter(
                key='url',
                value='https://docs.aws.amazon.com/neptune/',
                operator=FilterOperator.TEXT_MATCH
            )           
        )
    ),
    tenant_id='neptune'   
)
```

Build 단계 metadata 필터링은 한 번 추출하고 여러 번 구축하는 워크로드에서 잘 작동합니다. 전체 코퍼스를 `S3BasedDocs` 싱크 또는 `FileBasedDocs` 싱크로 추출한 다음([Extract 및 build 단계를 별도로 실행](./indexing.md#run-the-extract-and-build-stages-separately) 참조), 추출된 문서에서 여러 lexical graph를 구축할 수 있습니다. 서로 다른 필터링 기준 세트와 [multi-tenancy](./multi-tenancy.md) 기능을 사용하면 동일한 기본 소스에서 서로 다른 콘텐츠를 가진 여러 개의 개별 lexical graph를 구축할 수 있습니다.

### Metadata와 문서 식별

소스 문서와 연결된 metadata는 해당 문서 식별의 일부를 구성합니다. 소스 문서의 id는 문서의 내용과 metadata의 함수입니다. Chunk, 토픽 및 statement id는 차례로 소스 id의 함수입니다. 소스 문서의 metadata를 변경하고(필드 추가 또는 제거, 또는 필드 값 변경) 문서를 다시 처리하면, lexical graph의 새로운 소스, chunk, 토픽 및 statement 노드로 인덱싱됩니다.

### Metadata 필터링과 multi-tenancy

Metadata 필터링은 특정 lexical graph 내의 하나 이상의 서브그래프로 검색을 제한합니다. [Multi-tenancy](./multi-tenancy.md)는 동일한 기본 graph 및 vector store 내에 완전히 분리된 lexical graph를 생성합니다. Metadata 필터링과 multi-tenancy는 함께 잘 작동합니다. [위에서 설명한 것처럼](#using-metadata-filtering-in-the-build-stage), metadata 필터링을 사용하여 동일한 추출된 코퍼스에서 서로 다른 tenant 그래프를 구축할 수 있습니다. 쿼리할 때에도 metadata 필터링과 multi-tenancy를 사용할 수 있습니다. 다음 예제는 `neptune` tenant의 lexical graph 컨텍스트에서 쿼리에 metadata 필터링을 적용합니다:

```python
from graphrag_toolkit.lexical_graph import LexicalGraphQueryEngine
from graphrag_toolkit.lexical_graph.metadata import FilterConfig
from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

query_engine = LexicalGraphQueryEngine.for_traversal_based_search(
    graph_store, 
    vector_store,
    filter_config = FilterConfig(
        MetadataFilter(
            key='url',
            value='https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
            operator=FilterOperator.EQ
        )
    ),
	tenant_id='neptune'
)
```
