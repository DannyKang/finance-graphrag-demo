[[Home](./)]

## Amazon S3 Vectors를 Vector Store로 사용하기

### 목차

  - [개요](#overview)
  - [S3 Vectors vector store 생성하기](#creating-an-s3-vectors-vector-store)
    - [연결 문자열 매개변수](#connection-string-parameters)
  - [Amazon S3 Vectors를 vector store로 사용하기 위한 IAM 권한](#iam-permissions-required-to-use-amazon-s3-vectors-as-a-vector-store)
    - [인덱싱](#indexing)
    - [쿼리](#querying)

### 개요

[Amazon S3 Vectors](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html)를 vector store로 사용할 수 있습니다.

### S3 Vectors vector store 생성하기

`VectorStoreFactory.for_vector_store()` 정적 팩토리 메서드를 사용하여 Amazon S3 Vectors vector store 인스턴스를 생성하세요.

Amazon S3 Vectors store를 생성하려면 다음 형식의 연결 문자열을 제공하세요:

```
s3vectors://<bucket_name>[/<index_prefix>]
```

예를 들어:

```python
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

s3_vectors_connection_info = 's3vectors://my-s3-vectors-bucket/app1'

with VectorStoreFactory.for_vector_store(s3_vectors_connection_info) as vector_store:
    ...
```

#### 연결 문자열 매개변수

연결 문자열에는 두 가지 매개변수가 포함됩니다:

#####  `bucket_name` 

필수. graphrag-toolkit을 실행하는 애플리케이션과 동일한 AWS 리전에 있는 Amazon S3 vector 버킷의 이름입니다. vector 버킷이 아직 존재하지 않는 경우 인덱싱 프로세스가 새 버킷을 생성합니다.

#####  `index_prefix` 

선택 사항. 인덱싱 프로세스에서 생성된 각 인덱스 이름에 첨부될 접두사입니다. 접두사를 사용하면 서로 다른 graphrag-toolkit 애플리케이션에서 생성된 인덱스를 동일한 vector 버킷에 저장할 수 있습니다.

기본 tenant와 `admin` tenant 두 개의 [tenant](./multi-tenancy.md)가 있는 애플리케이션과 다음 연결 문자열을 사용하는 S3 Vectors vector store에 대한 연결을 가정합니다:

```
s3vectors://my-s3-vectors-bucket
```

vector store 연결 문자열이 버킷 이름만으로 구성되어 있으므로 애플리케이션은 다음 chunk 인덱스를 생성합니다:

   - `chunk`
   - `chunk-admin`

연결 문자열에 다음과 같은 접두사가 포함된 경우 -

```
s3vectors://my-s3-vectors-bucket/app1
```

애플리케이션은 다음 chunk 인덱스를 생성합니다:

   - `app1.chunk`
   - `app1.chunk-admin`

### Amazon S3 Vectors를 vector store로 사용하기 위한 IAM 권한

#### 인덱싱

graphrag-toolkit의 인덱싱 프로세스가 실행되는 자격 증명에는 다음 IAM 권한이 필요합니다:

  - `s3Vectors:GetVectorBucket`
  - `s3Vectors:CreateVectorBucket`
  - `s3Vectors:GetIndex`
  - `s3Vectors:CreateIndex`
  - `s3Vectors:DeleteVectors`
  - `s3Vectors:GetVectors`
  - `s3Vectors:PutVectors`

#### 쿼리

graphrag-toolkit의 쿼리 프로세스가 실행되는 자격 증명에는 다음 IAM 권한이 필요합니다:

  - `s3Vectors:GetVectorBucket`
  - `s3Vectors:GetIndex`
  - `s3Vectors:QueryVectors`
  - `s3Vectors:GetVectors`

S3 Vectors의 AWS 보안 모범 사례에 대한 자세한 내용은 [S3 Vectors의 Identity and Access Management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-access-management.html)를 참조하세요.