
## 커스텀 프롬프트 제공자 사용

GraphRAG Toolkit은 다양한 소스에서 프롬프트 템플릿을 동적으로 로드할 수 있도록 플러그인 방식의 프롬프트 제공자를 지원합니다. 모든 제공자는 구조화된 출력을 위한 AWS 템플릿 통합을 지원하며, `{query}` 변수를 통해 문서-그래프 쿼리 결과를 원활하게 처리합니다.

### AWS 템플릿 지원

모든 프롬프트 제공자는 자동 AWS 템플릿 로딩 및 대체를 지원합니다:
- 사용자 프롬프트에서 `{aws_template_structure}` 플레이스홀더 사용
- 템플릿은 S3 또는 로컬 파일에서 자동으로 로드됩니다 (txt, json, md 등 모든 형식)
- 컴플라이언스 및 자동화를 위한 구조화된 출력 활성화

### 문서-그래프 통합

시스템은 문서-그래프 쿼리와 원활하게 통합됩니다:
- 문서-그래프 결과는 텍스트로 `{query}` 변수를 통해 전달됩니다
- 특별한 처리가 필요 없음 - 시스템은 입력에 구애받지 않습니다
- 복잡한 지식 그래프 탐색 -> RAG -> LLM 워크플로우를 지원합니다

### 시스템 프롬프트 vs 사용자 프롬프트

GraphRAG Toolkit은 LlamaIndex ChatPromptTemplate을 따르는 두 개의 프롬프트 아키텍처를 사용합니다:

**시스템 프롬프트:**
- **역할**: AI의 정체성, 전문성 및 동작을 정의합니다
- **내용**: 어떻게 행동할지에 대한 지침 (예: "You are an AWS security expert")
- **목적**: 컨텍스트, 톤 및 도메인 지식을 설정합니다
- **변수**: 동적 변수 없음 - 정적 지침

**사용자 프롬프트:**
- **역할**: 실제 작업과 동적 콘텐츠를 포함합니다
- **내용**: 변수 플레이스홀더가 있는 작업 지침
- **목적**: 입력 데이터를 처리하고 출력 형식을 정의합니다
- **변수**: `{query}`, `{search_results}`, `{additionalContext}`, `{aws_template_structure}`

**예제 구조:**
```
System: "You are an AWS security expert specializing in compliance reporting."
User: "Generate evidence report for: {query} using context: {search_results}"
```

---

## 내장 제공자

네 가지 내장 제공자가 있습니다:

### 1. StaticPromptProvider

시스템 및 사용자 프롬프트가 코드베이스에서 상수로 정의된 경우 사용합니다.

```python
from graphrag_toolkit.lexical_graph.prompts.static_prompt_provider import StaticPromptProvider

prompt_provider = StaticPromptProvider()
```

이 제공자는 사전 정의된 상수 `ANSWER_QUESTION_SYSTEM_PROMPT`와 `ANSWER_QUESTION_USER_PROMPT`를 사용합니다. 템플릿을 사용할 수 없는 경우 AWS 템플릿 플레이스홀더가 자동으로 제거됩니다.

---

### 2. FilePromptProvider

프롬프트가 로컬 디스크에 저장된 경우 사용합니다.

```python
from graphrag_toolkit.lexical_graph.prompts.file_prompt_provider import FilePromptProvider
from graphrag_toolkit.lexical_graph.prompts.prompt_provider_config import FilePromptProviderConfig

prompt_provider = FilePromptProvider(
    FilePromptProviderConfig(base_path="./prompts"),
    system_prompt_file="system.txt",
    user_prompt_file="user.txt",
    aws_template_file="aws_template.json"  # optional AWS template (any format)
)
```

프롬프트 파일은 디렉토리(`base_path`)에서 읽히며, 필요에 따라 파일 이름을 재정의할 수 있습니다. AWS 템플릿은 자동으로 로드되어 `{aws_template_structure}` 플레이스홀더에 대체됩니다.

---

### 3. S3PromptProvider

프롬프트가 Amazon S3 버킷에 저장된 경우 사용합니다.

```python
from graphrag_toolkit.lexical_graph.prompts.s3_prompt_provider import S3PromptProvider
from graphrag_toolkit.lexical_graph.prompts.prompt_provider_config import S3PromptProviderConfig

prompt_provider = S3PromptProvider(
    S3PromptProviderConfig(
        bucket="ccms-prompts",
        prefix="prompts",
        aws_region="us-east-1",        # optional if set via env
        aws_profile="my-profile",      # optional if using default profile
        system_prompt_file="my_system.txt",  # optional override
        user_prompt_file="my_user.txt",      # optional override
        aws_template_file="aws_template.json" # optional AWS template (any format)
    )
)
```

프롬프트는 `boto3`와 AWS 자격 증명을 사용하여 로드됩니다. AWS 템플릿은 S3에서 자동으로 로드되어 `{aws_template_structure}` 플레이스홀더에 대체됩니다. 환경 또는 `~/.aws/config`가 SSO, 역할 또는 키로 구성되어 있는지 확인하세요.

---

### 4. BedrockPromptProvider

프롬프트가 Amazon Bedrock 프롬프트 ARN을 사용하여 저장되고 버전 관리되는 경우 사용합니다.

```python
from graphrag_toolkit.lexical_graph.prompts.bedrock_prompt_provider import BedrockPromptProvider
from graphrag_toolkit.lexical_graph.prompts.prompt_provider_config import BedrockPromptProviderConfig

prompt_provider = BedrockPromptProvider(
    config=BedrockPromptProviderConfig(
        system_prompt_arn="arn:aws:bedrock:us-east-1:123456789012:prompt/my-system",
        user_prompt_arn="arn:aws:bedrock:us-east-1:123456789012:prompt/my-user",
        system_prompt_version="DRAFT",
        user_prompt_version="DRAFT",
        aws_template_s3_bucket="my-templates",    # optional S3 bucket for templates
        aws_template_s3_key="templates/aws.json"  # optional S3 key for templates (any format)
    )
)
```

이 제공자는 STS를 사용하여 프롬프트 ARN을 동적으로 해석하며, AWS 템플릿 로딩을 위해 S3로 폴백할 수 있습니다. 템플릿은 `{aws_template_structure}` 플레이스홀더에 대체됩니다.
