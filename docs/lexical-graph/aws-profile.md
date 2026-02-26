# `GraphRAGConfig`에서 AWS 프로필 사용하기

이 가이드는 `GraphRAGConfig` 클래스를 활용하여 lexical-graph에서 **AWS 명명된 프로필**을 구성하고 사용하는 방법을 설명합니다.

## AWS 프로필이란?

AWS CLI와 SDK는 명명된 프로필을 사용하여 서로 다른 자격 증명 세트를 관리할 수 있습니다. 각 프로필에는 일반적으로 다음이 포함됩니다:
- Access key ID
- Secret access key
- (선택 사항) Session token
- (선택 사항) 기본 리전

이러한 프로필은 다음 위치에 저장됩니다:
- `~/.aws/credentials`
- `~/.aws/config`

---

## `GraphRAGConfig`에서 AWS 프로필을 사용하는 방법

### 1. **자동 감지**
프로필이 명시적으로 제공되지 않으면, `GraphRAGConfig`는 다음을 사용하려고 시도합니다:
```python
os.environ.get("AWS_PROFILE")
```

이것이 설정되지 않은 경우, 기본 AWS 동작으로 폴백합니다.

---

### 2. **명시적 프로필 설정**

프로그래밍 방식으로 프로필을 설정할 수 있습니다:

```python
from graphrag_toolkit.config import GraphRAGConfig

GraphRAGConfig.aws_profile = "padmin"
```

이렇게 하면 이전에 캐시된 클라이언트나 세션이 자동으로 재설정되어 모든 AWS 서비스 상호작용이 새로운 자격 증명을 사용하도록 보장합니다.

---

### 3. **프로필이 사용되는 곳**

다음을 호출할 때:

```python
GraphRAGConfig.session
```

또는 다음과 같은 속성을 사용할 때:

```python
GraphRAGConfig.bedrock
GraphRAGConfig.s3
GraphRAGConfig.rds
```

SDK는 활성 프로필과 리전을 사용하여 해당 클라이언트를 생성합니다.

---

## 환경 변수를 사용한 예제

앱을 실행하기 전에 프로필과 리전을 내보낼 수 있습니다:

```bash
export AWS_PROFILE=padmin
export AWS_REGION=us-east-1
python my_app.py
```

또는 인라인으로 설정할 수 있습니다:

```bash
AWS_PROFILE=padmin AWS_REGION=us-east-1 python my_app.py
```

---

## 프로필 기반 다중 계정 테스트

AWS 계정 간에 테스트하려면:
```python
GraphRAGConfig.aws_profile = "dev-profile"
GraphRAGConfig.aws_region = "us-west-2"

bedrock = GraphRAGConfig.bedrock  # Will use dev-profile in us-west-2
```

---

## 일반적인 함정

- **프로필 누락**: `~/.aws/credentials`에 프로필이 존재하고 철자가 올바른지 확인하세요.
- **접근 거부**: 접근하려는 서비스에 대한 IAM 권한을 확인하세요.
- **리전 불일치**: Bedrock은 특정 리전(예: `us-east-1`)에서만 사용 가능할 수 있습니다.

---

## 요약

| 사용 사례                     | 방법                                              |
|-----------------------------|------------------------------------------------------------|
| 기본 프로필              | 환경 변수 또는 기본 구성에 의존           |
| 프로그래밍 방식 재정의        | `GraphRAGConfig.aws_profile = "my-profile"`               |
| 리전 전환               | `GraphRAGConfig.aws_region = "us-east-2"`                 |
| 전체 재정의                | `.session` 호출 전에 프로필과 리전 모두 설정    |
| boto3 클라이언트 생성         | `.bedrock`, `.s3`, 또는 `.rds` 속성 사용               |
