
[[Home](./)]

## Batch Extraction

### 목차

  - [개요](#overview)
  - [LexicalGraphIndex에서 batch inference 사용하기](#using-batch-inference-with-the-lexicalgraphindex)
  - [설정](#setup)
  - [Batch extraction 작업 요구 사항](#batch-extraction-job-requirements)

### 개요

인덱싱 프로세스의 extract 단계에서 [Amazon Bedrock batch inference](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html)를 사용하여 대규모 데이터셋의 extraction 성능을 향상시킬 수 있습니다.

대규모 수집을 위한 batch extraction 구성에 대한 자세한 내용은 [Batch Extraction 구성](./configuring-batch-extraction.md)을 참조하세요.

### LexicalGraphIndex에서 batch inference 사용하기

인덱싱 프로세스의 extract 단계에서 batch inference를 사용하려면, `BatchConfig` 객체를 생성하고 [`IndexingConfig`](./indexing.md#configuring-the-extract-and-build-stages)의 일부로 `LexicalGraphIndex`에 제공하세요:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph import GraphRAGConfig, IndexingConfig
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory
from graphrag_toolkit.lexical_graph.indexing.extract import BatchConfig

from llama_index.core import SimpleDirectoryReader

def batch_extract_and_load():

    GraphRAGConfig.extraction_batch_size = 1000

    batch_config = BatchConfig(
        region='us-west-2',
        bucket_name='my-bucket',
        key_prefix='batch-extract',
        role_arn='arn:aws:iam::111111111111:role/my-batch-inference-role',
        max_batch_size=40000
    )

    indexing_config = IndexingConfig(batch_config=batch_config)

    with (
        GraphStoreFactory.for_graph_store(os.environ['GRAPH_STORE']) as graph_store,
        VectorStoreFactory.for_vector_store(os.environ['VECTOR_STORE']) as vector_store
    ):

        graph_index = LexicalGraphIndex(
            graph_store,
            vector_store,
            indexing_config=indexing_config
        )

        reader = SimpleDirectoryReader(input_dir='path/to/directory')
        docs = reader.load_data()

        graph_index.extract_and_build(docs, show_progress=True)

batch_extract_and_load()
```

batch extraction을 사용할 때는, 많은 수의 소스 문서가 단일 배치로 batch inference 작업에 전달되도록 `GraphRAGConfig.extraction_batch_size` 구성 매개변수를 업데이트하세요. 위 예제에서 `GraphRAGConfig.extraction_batch_size`는 `1000`으로 설정되어 있으며, 이는 1000개의 소스 문서가 동시에 chunk로 분할되고 이 chunk들이 batch inference 작업으로 전송됨을 의미합니다. 문서당 10-50개의 chunk가 있는 경우, 여기서 batch inference 작업은 단일 배치에서 수천 개의 레코드를 처리하며, 최대 40,000개의 레코드(구성된 `max_batch_size` 값)까지 처리합니다.

### 설정

batch extraction을 처음 실행하기 전에 다음 사전 요구 사항을 충족해야 합니다:

  - batch extraction을 실행할 AWS 리전에 Amazon S3 버킷을 생성합니다
  - S3 버킷에 대한 접근 권한이 있는 [batch inference용 사용자 지정 서비스 역할을 생성](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-iam-sr.html)합니다 (필요한 경우 inference profile 호출 권한 포함)
  - 인덱싱 프로세스가 실행되는 IAM 자격 증명을 업데이트하여 [batch inference 작업을 제출하고 관리](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-prereq.html#batch-inference-permissions)할 수 있도록 하고, 사용자 지정 서비스 역할을 Bedrock에 전달할 수 있도록 합니다

아래 예제에서 `<account-id>`를 AWS 계정 ID로, `<region>`을 batch extraction을 실행할 AWS 리전 이름으로, `<model-id>`를 batch extraction에 사용할 Amazon Bedrock의 기초 모델 ID로, `<custom-service-role-arn>`을 새 사용자 지정 서비스 역할의 ARN으로 대체하세요.

#### 사용자 지정 서비스 역할

다음 신뢰 관계를 가진 [batch inference용 사용자 지정 서비스 역할을 생성](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-iam-sr.html)합니다:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": "<account-id>"
                },
                "ArnEquals": {
                    "aws:SourceArn": "arn:aws:bedrock:<region>:<account-id>:model-invocation-job/*"
                }
            }
        }
    ]
}
```

사용자 지정 서비스 역할에 [batch inference 입력 및 출력 파일이 저장될 Amazon S3 버킷에 대한 접근을 허용하는](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-iam-sr.html#batch-iam-sr-identity) 정책을 생성하고 연결합니다:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::<bucket>",
                "arn:aws:s3:::<bucket>/*"
            ],
            "Condition": {
                "StringEquals": {
                    "aws:ResourceAccount": [
                        "<account-id>"
                    ]
                }
             }
        }
    ]
}
```

inference profile로 batch inference를 실행하려면, 서비스 역할에 [AWS 리전에서 inference profile를 호출할 수 있는 권한](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-iam-sr.html#batch-iam-sr-ip)이 있어야 하며, inference profile의 각 리전에 있는 모델에 대한 권한도 있어야 합니다.

#### IAM 자격 증명 업데이트

인덱싱 프로세스가 실행되는 IAM 자격 증명(사용자 지정 서비스 역할이 아님)을 업데이트하여 [batch inference 작업을 제출하고 관리](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-prereq.html#batch-inference-permissions)할 수 있도록 해야 합니다:

```
{
    "Version": "2012-10-17",
    "Statement": [
        ...

        {
            "Effect": "Allow",
            "Action": [
                "bedrock:CreateModelInvocationJob",
                "bedrock:GetModelInvocationJob",
                "bedrock:ListModelInvocationJobs",
                "bedrock:StopModelInvocationJob"
            ],
            "Resource": [
                "arn:aws:bedrock:<region>::foundation-model/<model-id>",
                "arn:aws:bedrock:<region>:<account-id>:model-invocation-job/*"
            ]
        }
    ]
}
```

인덱싱 프로세스가 실행되는 IAM 자격 증명이 사용자 지정 서비스 역할을 Bedrock에 전달할 수 있도록 `iam:PassRole` 권한을 추가합니다:

```
{
    "Effect": "Allow",
    "Action": [
        "iam:PassRole"
    ],
    "Resource": "<custom-service-role-arn>"
}
```

### Batch extraction 작업 요구 사항

각 batch extraction 작업은 Amazon Bedrock의 [batch inference 할당량](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-data.html)을 따라야 합니다. lexical-graph의 batch extraction 기능은 작업당 하나의 입력 파일을 사용합니다.

#### 주요 요구 사항

  - 각 batch 작업에는 100-50,000개의 레코드가 필요합니다
  - 100개 미만의 레코드가 있는 작업은 batch가 아닌 개별적으로 처리됩니다
  - 이 기능은 입력 파일 크기를 확인하지 않습니다 — Bedrock 할당량을 초과하면 작업이 실패합니다

#### Worker 구성

batch extraction은 동시 batch 작업을 트리거하는 여러 worker를 사용할 수 있습니다:

  - (worker 수 x 동시 배치 수)가 Bedrock 할당량을 초과하면 용량이 사용 가능해질 때까지 작업이 대기합니다
