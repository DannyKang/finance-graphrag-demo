# GraphRAG Reader 제공자

## 개요
GraphRAG Toolkit은 다양한 소스에서 문서를 읽기 위한 통합되고 확장 가능한 시스템을 제공합니다. Reader 제공자는 문서 수집의 세부 사항을 추상화하여, 일관된 인터페이스를 사용하여 파일, 데이터베이스, API, 클라우드 스토리지 등에서 작업할 수 있게 합니다.

## 아키텍처

### 핵심 추상화
- **ReaderProvider**: 모든 문서 리더의 추상 기본 클래스입니다. 모든 구체적인 리더는 `read(input_source)` 메서드를 구현하여 `Document` 객체 목록을 반환합니다.
- **BaseReaderProvider**: GraphRAG `ReaderProvider`와 LlamaIndex `BaseReader` 인터페이스를 모두 구현하여, 새 리더를 위한 호환성과 표준 패턴을 제공합니다.
- **LlamaIndexReaderProviderBase**: LlamaIndex 리더를 위한 간단한 래퍼로, 기존 LlamaIndex 리더를 GraphRAG 시스템에 쉽게 적용할 수 있게 합니다.
- **ValidatedReaderProviderBase**: `LlamaIndexReaderProviderBase`를 확장하여 입력, 출력 및 구성 검증을 추가합니다.

### 구성 클래스
각 reader 제공자는 구성 클래스(예: `PDFReaderConfig`, `WebReaderConfig`)와 쌍을 이룹니다. 이러한 클래스는 각 데이터 소스에 필요한 매개변수를 정의하며, 검증을 위해 Python dataclass를 사용합니다.

## 사용 방법

1. 데이터 소스에 맞는 **제공자와 구성을 선택**합니다
2. 필요한 매개변수로 **구성을 인스턴스화**합니다
3. 구성으로 **제공자를 생성**합니다
4. **`.read(input_source)`를 호출**하여 문서를 추출합니다

```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import PDFReaderProvider, PDFReaderConfig

config = PDFReaderConfig(
    return_full_document=False,
    metadata_fn=lambda path: {'source': 'pdf', 'file_path': path}
)
reader = PDFReaderProvider(config)
documents = reader.read("/path/to/file.pdf")
```

## 리더에서 메타데이터 사용

많은 reader 제공자는 구성 클래스의 `metadata_fn` 매개변수를 통해 각 문서에 커스텀 메타데이터를 첨부하는 것을 지원합니다. 이 함수는 입력을 받아 메타데이터 딕셔너리를 반환해야 합니다.

```python
def custom_metadata(path):
    return {
        "source": path,
        "document_type": "technical_doc",
        "project": "GraphRAG"
    }

config = PDFReaderConfig(
    return_full_document=False,
    metadata_fn=custom_metadata
)
```

## 내장 제공자

### 문서 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `PDFReaderProvider` | `PDFReaderConfig` | PDF 문서 | `pymupdf`, `llama-index-readers-file` |
| `DocxReaderProvider` | `DocxReaderConfig` | Word 문서 | `python-docx` |
| `PPTXReaderProvider` | `PPTXReaderConfig` | PowerPoint 파일 | `python-pptx` |
| `MarkdownReaderProvider` | `MarkdownReaderConfig` | Markdown 파일 | 내장 |
| `CSVReaderProvider` | `CSVReaderConfig` | CSV 파일 | 내장 |
| `JSONReaderProvider` | `JSONReaderConfig` | JSON/JSONL 파일 | 내장 |
| `StructuredDataReaderProvider` | `StructuredDataReaderConfig` | 스트리밍 지원 CSV/Excel 파일 | `pandas`, `openpyxl`, `llama-index-readers-structured-data` |

### 웹 및 지식 베이스 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `WebReaderProvider` | `WebReaderConfig` | 웹 페이지 | `requests`, `beautifulsoup4` |
| `WikipediaReaderProvider` | `WikipediaReaderConfig` | Wikipedia 문서 | `wikipedia` |
| `YouTubeReaderProvider` | `YouTubeReaderConfig` | YouTube 자막 | `youtube-transcript-api` |

### 클라우드 스토리지 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `S3DirectoryReaderProvider` | `S3DirectoryReaderConfig` | AWS S3 버킷 | `boto3` |
| `DirectoryReaderProvider` | `DirectoryReaderConfig` | 로컬 디렉토리 | 내장 |

### 데이터베이스 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `DatabaseReaderProvider` | `DatabaseReaderConfig` | SQL 데이터베이스 | 데이터베이스별 드라이버 |


### 코드 및 리포지토리 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `GitHubReaderProvider` | `GitHubReaderConfig` | GitHub 리포지토리 | `PyGithub` |


### 특수 리더
| 제공자 | 구성 | 설명 | 의존성 |
|----------|--------|-------------|--------------|
| `DocumentGraphReaderProvider` | `DocumentGraphReaderConfig` | 문서 그래프 | 내장 |


## S3 지원

GraphRAG Toolkit은 S3 통합을 위한 두 가지 접근 방식을 제공합니다:

### 1. S3DirectoryReaderProvider (권장)
LlamaIndex의 S3Reader를 사용하여 직접 S3에 접근하는 최신 S3 리더:

```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import S3DirectoryReaderProvider, S3DirectoryReaderConfig

# For a single file
config = S3DirectoryReaderConfig(
    bucket="my-bucket",
    key="documents/file.pdf",  # Use 'key' for single file
    metadata_fn=lambda path: {'source': 's3'}
)

# For a directory/prefix
config = S3DirectoryReaderConfig(
    bucket="my-bucket",
    prefix="documents/",  # Use 'prefix' for directory
    metadata_fn=lambda path: {'source': 's3'}
)

# Note: Use either 'key' OR 'prefix', not both
reader = S3DirectoryReaderProvider(config)
docs = reader.read()
```

### 2. 레거시 S3BasedDocs
S3 문서 저장 및 검색을 위한 레거시 시스템(여전히 지원됨):

```python
from graphrag_toolkit.lexical_graph.indexing.load import S3BasedDocs

s3_docs = S3BasedDocs(
    region="us-east-1",
    bucket_name="my-bucket",
    key_prefix="documents/",
    collection_id="my-collection"
)

# Iterate through stored documents
for doc in s3_docs:
    # Process document
    pass
```

### S3 인증
S3 접근은 AWS 자격 증명을 위해 `GraphRAGConfig.session`을 사용합니다. 다음을 통해 구성하세요:
- AWS 자격 증명 파일 (`~/.aws/credentials`)
- 환경 변수 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- IAM 역할 (AWS에서 실행 시)
- AWS SSO 프로필

### 대용량 파일을 위한 S3 스트리밍
`StructuredDataReaderProvider`는 다운로드를 피하기 위해 대용량 S3 파일 스트리밍을 지원합니다:

```python
config = StructuredDataReaderConfig(
    stream_s3=True,  # Enable streaming
    stream_threshold_mb=100,  # Stream files > 100MB
    pandas_config={"sep": ","}
)
```

## 구성 예제

### PDF Reader
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import PDFReaderProvider, PDFReaderConfig

config = PDFReaderConfig(
    return_full_document=False,
    metadata_fn=lambda path: {'source': 'pdf', 'file_path': path}
)
reader = PDFReaderProvider(config)
docs = reader.read('document.pdf')
```

### Web Reader
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import WebReaderProvider, WebReaderConfig

config = WebReaderConfig(
    html_to_text=True,
    metadata_fn=lambda url: {'source': 'web', 'url': url}
)
reader = WebReaderProvider(config)
docs = reader.read('https://example.com')
```

### YouTube Reader
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import YouTubeReaderProvider, YouTubeReaderConfig

config = YouTubeReaderConfig(
    language="en",
    metadata_fn=lambda url: {'source': 'youtube', 'url': url}
)
reader = YouTubeReaderProvider(config)
docs = reader.read('https://www.youtube.com/watch?v=VIDEO_ID')
```

### Structured Data Reader (CSV/Excel)
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import StructuredDataReaderProvider, StructuredDataReaderConfig

config = StructuredDataReaderConfig(
    col_index=0,  # Column to use as index
    col_joiner=', ',  # How to join columns
    pandas_config={"sep": ","},  # Pandas options
    stream_s3=True,  # Enable S3 streaming
    stream_threshold_mb=50,  # Stream files > 50MB
    metadata_fn=lambda path: {'source': 'structured', 'file': path}
)
reader = StructuredDataReaderProvider(config)

# Works with local and S3 files
docs = reader.read(['data.csv', 's3://bucket/large-file.xlsx'])
```

### S3 Directory Reader
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import S3DirectoryReaderProvider, S3DirectoryReaderConfig

# Reading from a directory/prefix
config = S3DirectoryReaderConfig(
    bucket="my-bucket",
    prefix="documents/",  # For directory access
    metadata_fn=lambda path: {'source': 's3', 'path': path}
)
reader = S3DirectoryReaderProvider(config)
docs = reader.read()  # No parameter needed

# Reading a single file
config = S3DirectoryReaderConfig(
    bucket="my-bucket",
    key="documents/specific-file.pdf",  # For single file
    metadata_fn=lambda path: {'source': 's3', 'path': path}
)
reader = S3DirectoryReaderProvider(config)
docs = reader.read()  # No parameter needed
```

### Database Reader
```python
from graphrag_toolkit.lexical_graph.indexing.load.readers import DatabaseReaderProvider, DatabaseReaderConfig

config = DatabaseReaderConfig(
    connection_string="postgresql://user:pass@localhost/db",
    query="SELECT id, content FROM documents",
    metadata_fn=lambda row: {'source': 'database', 'id': row.get('id')}
)
reader = DatabaseReaderProvider(config)
docs = reader.read(config.query)
```

## 설치 요구 사항

리더마다 서로 다른 의존성이 필요합니다. 필요에 따라 설치하세요:

```bash
# PDF processing
pip install pymupdf llama-index-readers-file

# Web scraping
pip install requests beautifulsoup4 llama-index-readers-web

# YouTube transcripts
pip install youtube-transcript-api

# AWS services
pip install boto3

# Structured data processing
pip install pandas openpyxl llama-index-readers-structured-data

# Office documents
pip install python-docx python-pptx

# GitHub integration
pip install PyGithub

# Notion integration
pip install notion-client

# Wikipedia
pip install wikipedia
```

## 확장: 커스텀 리더 작성

새로운 데이터 소스를 추가하려면:

1. dataclass로 **구성 클래스를 생성**합니다:
```python
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from .reader_provider_config_base import ReaderProviderConfig

@dataclass
class MyReaderConfig(ReaderProviderConfig):
    api_key: str = ""
    metadata_fn: Optional[Callable[[str], Dict[str, Any]]] = None
```

2. **기본 제공자를 상속**합니다:
```python
from .base_reader_provider import BaseReaderProvider

class MyReaderProvider(BaseReaderProvider):
    def __init__(self, config: MyReaderConfig):
        self.config = config

    def read(self, input_source):
        # Implement your reading logic
        documents = []
        # ... process input_source ...
        return documents
```

3. 쉬운 임포트를 위해 **`__init__.py`에 등록**합니다.

## 참고
- [Base Classes](../../lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/load/readers/)
- [Configuration Classes](../../lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/load/readers/reader_provider_config.py)
- [Provider Implementations](../../lexical-graph/src/graphrag_toolkit/lexical_graph/indexing/load/readers/providers/)
