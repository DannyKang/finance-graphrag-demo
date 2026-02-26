[[Home](./)]

## 보안

### 주제

  - [개요](#overview)
  - [Amazon Neptune 접근 관리](#managing-access-to-amazon-neptune)
  - [Amazon OpenSearch Serverless 접근 관리](#managing-access-to-amazon-opensearch-serverless)
    - [OpenSearch API 작업 IAM 정책](#opensearch-api-operations-iam-policy)
    - [데이터 접근 정책](#data-access-policy)
    - [네트워크 접근 정책](#network-access-policy)
    - [암호화 정책](#encryption-policy)
  - [Amazon Bedrock 접근 관리](#managing-access-to-amazon-bedrock)

### 개요

lexical-graph 라이브러리로 애플리케이션을 구축할 때, 소스 데이터와 사용하는 graph store, vector store 및 파운데이션 모델 API에 대한 접근을 보호하는 것은 사용자의 책임입니다. 다음 섹션에서는 AWS Identity and Access Management (IAM) 정책을 사용하여 Amazon Neptune, Amazon OpenSearch Serverless 및 Amazon Bedrock에 대한 접근을 제어하는 방법에 대한 가이드를 제공합니다.

### Amazon Neptune 접근 관리

인덱스 작업은 Amazon Neptune 데이터베이스에 대한 읽기 및 쓰기 접근이 필요합니다. 쿼리 작업은 데이터베이스에 대한 읽기 접근만 필요합니다.

애플리케이션이 Amazon Neptune 데이터베이스에서 데이터를 읽을 수 있도록 하려면, 다음 예제 IAM 정책을 애플리케이션이 실행되는 AWS ID에 연결하세요. `<account-id>`를 AWS 계정 ID로, `<region>`을 Amazon Neptune 데이터베이스 클러스터가 위치한 AWS 리전 이름으로, `<cluster-resource-id>`를 데이터베이스 클러스터의 [클러스터 리소스 ID](https://docs.aws.amazon.com/neptune/latest/userguide/iam-data-resources.html)로 바꾸세요.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "NeptuneDBReadAccessStatement",
            "Effect": "Allow",
            "Action": [
                "neptune-db:ReadDataViaQuery"
            ],
            "Resource": "arn:aws:neptune-db:<region>:<account-id>:<cluster-resource-id>/*",
            "Condition": {
                "StringEquals": {
                    "neptune-db:QueryLanguage": "OpenCypher"
                }
            }
        }
    ]
}
```

애플리케이션이 Amazon Neptune 데이터베이스에 데이터를 쓸 수 있도록 하려면, 다음 예제 IAM 정책을 애플리케이션이 실행되는 AWS ID에 연결하세요. `<account-id>`를 AWS 계정 ID로, `<region>`을 Amazon Neptune 데이터베이스 클러스터가 위치한 AWS 리전 이름으로, `<cluster-resource-id>`를 데이터베이스 클러스터의 [클러스터 리소스 ID](https://docs.aws.amazon.com/neptune/latest/userguide/iam-data-resources.html)로 바꾸세요.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "NeptuneDBWriteAccessStatement",
            "Effect": "Allow",
            "Action": [
                "neptune-db:WriteDataViaQuery",
                "neptune-db:DeleteDataViaQuery"
            ],
            "Resource": "arn:aws:neptune-db:<region>:<account-id>:<cluster-resource-id>/*",
            "Condition": {
                "StringEquals": {
                    "neptune-db:QueryLanguage": "OpenCypher"
                }
            }
        }
    ]
}
```

IAM 정책을 사용하여 Amazon Neptune에 대한 접근을 보호하는 방법에 대한 자세한 내용은 [IAM 정책을 사용하여 Amazon Neptune 데이터베이스 접근 관리](https://docs.aws.amazon.com/neptune/latest/userguide/security-iam-access-manage.html)를 참조하세요.

### Amazon OpenSearch Serverless 접근 관리

애플리케이션이 Amazon OpenSearch Serverless 컬렉션에서 데이터를 읽고 쓸 수 있도록 하려면, 컬렉션에 데이터 접근, 네트워크 및 암호화 정책을 연결해야 합니다. 또한, 연결된 보안 주체에 IAM 권한 `aoss:APIAccessAll`에 대한 접근 권한을 부여해야 하며, 이는 IAM 정책을 사용하여 수행할 수 있습니다.

Amazon OpenSearch Serverless 컬렉션에 대한 접근을 보호하는 방법에 대한 자세한 내용은 [Amazon OpenSearch Serverless의 보안 개요](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-security.html)를 참조하세요.

#### OpenSearch API 작업 IAM 정책

OpenSearch API 작업에 대한 데이터 플레인 접근을 허용하려면, 다음 예제 IAM 정책을 애플리케이션이 실행되는 AWS ID에 연결하세요. `<account-id>`를 AWS 계정 ID로, `<region>`을 Amazon OpenSearch Serverless 컬렉션이 위치한 AWS 리전 이름으로, `<collection-id>`를 컬렉션의 ID(이름이 아님)로 바꾸세요.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "OpenSearchServerlessAPIAccessAllStatement",
            "Effect": "Allow",
            "Action": [
                "aoss:APIAccessAll"
            ],
            "Resource": [
                "arn:aws:aoss:<region>:<account>:collection/<collection-id>"
            ]
        }
    ]
}
```

#### 데이터 접근 정책

[데이터 접근 정책](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-data-access.html)은 OpenSearch Serverless가 지원하는 OpenSearch 작업에 대한 접근을 제어합니다.

기존 데이터 접근 정책을 사용하거나 아래 예제 정책을 사용하여 새로운 정책을 생성할 수 있습니다. `<collection-name>`을 OpenSearch Serverless 컬렉션의 이름으로, `<principal-arn>`을 애플리케이션에 연결된 IAM 역할 또는 사용자의 ARN으로 바꾸세요.

```
[
    {
        "Rules": [
            {
                "Resource": [
                    "collection/<collection-name>"
                ],
                "Permission": [
                    "aoss:DescribeCollectionItems",
                    "aoss:CreateCollectionItems",
                    "aoss:UpdateCollectionItems"
                ],
                "ResourceType": "collection"
            },
            {
                "Resource": [
                    "index/<collection-name>/*"
                ],
                "Permission": [
                    "aoss:UpdateIndex",
                    "aoss:DescribeIndex",
                    "aoss:ReadDocument",
                    "aoss:WriteDocument",
                    "aoss:CreateIndex"
                ],
                "ResourceType": "index"
            }
        ],
        "Principal": [
            "<principal-arn>"
        ]
    }
]
```

#### 네트워크 접근 정책

[네트워크 접근 정책](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-network.html)은 OpenSearch Serverless 컬렉션의 엔드포인트에 대한 네트워크 접근을 정의합니다. Amazon OpenSearch Serverless 컬렉션의 네트워크 설정은 컬렉션이 퍼블릭 네트워크에서 인터넷을 통해 접근 가능한지, 아니면 VPC 엔드포인트를 통해 비공개로 접근해야 하는지를 결정합니다.

기존 네트워크 접근 정책을 사용하거나 아래 예제 정책을 사용하여 새로운 정책을 생성할 수 있습니다. 이 예제 정책은 컬렉션의 OpenSearch 엔드포인트에 대한 퍼블릭 접근을 제공합니다. `<collection-name>`을 OpenSearch Serverless 컬렉션의 이름으로 바꾸세요:

```
[
    {
        "Rules": [
            {
                "Resource": [
                    "collection/<collection-name>"
                ],
                "ResourceType": "collection"
            }
        ],
        "AllowFromPublic": true
    }
]
```

#### 암호화 정책

[암호화 정책](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-encryption.html)은 컬렉션에 암호화 키를 할당합니다. 컬렉션은 AWS 소유 키 또는 고객 관리 키를 사용하여 암호화됩니다.

기존 암호화 정책을 사용하거나 아래 예제 정책을 사용하여 새로운 정책을 생성할 수 있습니다. 이 예제 정책은 AWS 소유 키를 사용하여 컬렉션을 암호화합니다. `<collection-name>`을 OpenSearch Serverless 컬렉션의 이름으로 바꾸세요:

```
[
    {
        "Rules":[
          {
              "ResourceType":"collection",
              "Resource":[
                  "collection/<collection-name>"
              ]
          }
      ],
      "AWSOwnedKey": true
    }
]
```

### Amazon Bedrock 접근 관리

애플리케이션이 graphrag-toolkit에서 사용하는 Amazon Bedrock 파운데이션 모델을 호출할 수 있도록 하려면, 다음 예제 IAM 정책을 애플리케이션이 실행되는 AWS ID에 연결하세요. `<region>`을 Amazon Bedrock이 위치한 AWS 리전 이름으로, `<geography>`를 추론 프로필이 커버하는 지역을 나타내는 리전 접두사(예: `us-east-1` 및 `us-west-2`와 같은 미국 기반 AWS 리전의 경우 `us`)로 바꾸세요.

이 예제 IAM 정책은 툴킷의 기본 모델인 `us.anthropic.claude-3-7-sonnet-20250219-v1:0` 및 `cohere.embed-english-v3`를 사용한다고 가정합니다. 애플리케이션을 실행하기 전에 이 모델에 대한 [접근을 활성화](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)해야 합니다. 사용할 수 있는 사전 정의된 추론 프로필과 애플리케이션 추론 프로필을 지원하는 리전 및 모델에 대한 자세한 내용은 [추론 프로필에 대한 지원 리전 및 모델](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)을 참조하세요.

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockInvokeModelStatement",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0",
                "arn:aws:bedrock:<region>::inference-profile/<geography>.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "arn:aws:bedrock:<region>::foundation-model/cohere.embed-english-v3"
            ]
        }
    ]
}
```
