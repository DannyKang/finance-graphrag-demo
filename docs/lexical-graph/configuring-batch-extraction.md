[[Home](./)]

## Batch Extraction 구성

### 목차

  - [개요](#overview)
  - [BatchConfig 매개변수](#batchconfig-parameters)
    - [필수 매개변수](#required-parameters)
      - [bucket_name](#bucket_name)
      - [region](#region)
      - [role_arn](#role_arn)
    - [선택적 매개변수](#optional-parameters)
      - [key_prefix](#key_prefix)
      - [max_batch_size](#max_batch_size)
      - [max_num_concurrent_batches](#max_num_concurrent_batches)
      - [s3_encryption_key_id](#s3_encryption_key_id)
    - [VPC 보안 매개변수 (선택 사항)](#vpc-security-parameters-optional)
      - [subnet_ids](#subnet_ids)
      - [security_group_ids](#security_group_ids)
    - [파일 관리](#file-management)
      - [delete_on_success](#delete_on_success)
  - [batch extraction 성능 최적화](#optimizing-batch-extraction-performance)

### 개요

### BatchConfig 매개변수

`BatchConfig` 객체는 Amazon Bedrock batch inference 작업의 구성 설정을 관리합니다. 각 매개변수에 대한 자세한 설명은 다음과 같습니다:

#### 필수 매개변수

##### `bucket_name`

batch 처리 파일(입력 및 출력 모두)이 저장될 Amazon S3 버킷의 이름을 지정해야 합니다.

##### `region`

S3 버킷이 위치하고 Amazon Bedrock batch inference 작업이 실행될 AWS 리전 이름(예: "us-east-1")을 제공해야 합니다.

##### `role_arn`

batch inference 작업을 처리하는 서비스 역할의 Amazon Resource Name(ARN)입니다. 콘솔을 통해 기본 서비스 역할을 생성하거나 [batch inference용 서비스 역할 생성](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-iam-sr.html) 문서의 지침을 따를 수 있습니다.

#### 선택적 매개변수

##### `key_prefix`

원하는 경우 입력 및 출력 파일을 구성하기 위한 S3 키 접두사를 지정할 수 있습니다.

##### `max_batch_size`

각 batch inference 작업에 포함할 수 있는 레코드(chunk) 수를 제어합니다. 기본값은 `25000`개 레코드입니다.

##### `max_num_concurrent_batches`

worker당 동시에 실행할 수 있는 batch inference 작업 수를 결정합니다. 이 설정은 `GraphRAGConfig.extraction_num_workers`와 함께 작동합니다. 기본값은 worker당 `3`개의 동시 배치입니다.

##### `s3_encryption_key_id`

S3의 출력 데이터를 보호하기 위한 암호화 키의 고유 식별자를 제공할 수 있습니다.

#### VPC 보안 매개변수 (선택 사항)

VPC 보호에 대한 자세한 내용은 [VPC를 사용하여 batch inference 작업 보호](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-vpc)를 참조하세요.

##### `subnet_ids`

batch inference 작업을 보호하기 위한 Virtual Private Cloud(VPC) 내의 서브넷 ID 배열입니다.

##### `security_group_ids`

batch inference 작업을 보호하기 위한 VPC 내의 보안 그룹 ID 배열입니다.

#### 파일 관리

##### `delete_on_success`

batch 작업이 성공적으로 완료된 후 입력 및 출력 JSON 파일이 로컬 파일 시스템에서 자동으로 삭제되는지 여부를 제어합니다. 기본적으로 `True`로 설정되어 있습니다. 이 설정은 S3에 저장된 파일에는 영향을 미치지 않으며, S3 파일은 상관없이 보존됩니다.

### batch extraction 성능 최적화

batch extraction 성능을 제어하는 가장 중요한 설정은 다음과 같습니다:

  - `GraphRAGConfig.extraction_batch_size`: extraction 파이프라인으로 전달되는 소스 문서 수를 설정합니다. 이 값을 계산할 때, 총 chunk 수(소스 문서 수 x 문서당 평균 chunk 수)가 계획된 동시 batch 작업을 채우기에 충분해야 한다는 점을 고려하세요.
  - `GraphRAGConfig.extraction_num_workers`: 동시에 batch 작업을 실행하는 CPU 수를 설정합니다.
  - `BatchConfig.max_num_concurrent_batches`: 각 worker가 실행하는 동시 batch 작업 수를 설정합니다.
  - `BatchConfig.max_batch_size`: batch 작업당 최대 chunk 수를 설정합니다.

batch extraction의 효율성을 극대화하려면 다음 세 가지 핵심 원칙을 따르세요:

  - **파일 용량 극대화** 각 batch 작업 파일은 최대 50,000개의 레코드를 담을 수 있습니다. 그러나 Amazon Bedrock은 입력 파일 크기 제한을 적용하며, 일반적으로 1-5 GB 사이입니다. 사용 중인 모델의 구체적인 제한은 Amazon Bedrock 서비스 할당량 섹션의 **Batch inference job size** 할당량([Amazon Bedrock 서비스 할당량 섹션](https://docs.aws.amazon.com/general/latest/gr/bedrock.html#limits_bedrock)에서 확인)을 참조하세요. 툴킷은 파일 크기를 자동으로 확인하지 않으므로, 할당량을 초과하면 작업이 실패할 수 있습니다. 파일 크기 제한 내에 머물기 위해 최대 한도보다 적은 레코드를 사용해야 할 수 있습니다. `BatchConfig.max_batch_size`를 구성하여 batch 작업당 최대 레코드 수를 설정하세요.
  - **더 크고 적은 수의 파일 사용** 작업을 많은 수의 작은 파일로 분할하기보다는 최소한의 대용량 파일을 사용하는 데 집중하세요. 예를 들어, 40,000개의 레코드를 10,000개씩 4개의 병렬 작업으로 나누는 것보다 단일 작업으로 처리하는 것이 더 효율적입니다.
  - **병렬 처리 활용** `GraphRAGConfig.extraction_num_workers`와 `BatchConfig.max_num_concurrent_batches`를 사용하여 병렬 작업 실행을 활용하세요. 총 작업 수(worker 수 x 동시 배치 수)는 리전당 진행 중 및 제출된 batch inference 작업 합계 20개의 Bedrock 할당량 내에 있어야 합니다. 이 한도를 초과하면 용량이 사용 가능해질 때까지 추가 작업이 대기열에서 대기합니다.
