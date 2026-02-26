[[Home](./)]

## Postgres를 Vector Store로 사용하기

### 목차

  - [개요](#overview)
  - [종속성 설치](#install-dependencies)
  - [Postgres vector store 생성하기](#creating-a-postgres-vector-store)
    - [IAM 인증이 활성화된 Postgres vector store에 연결하기](#connecting-to-an-iam-auth-enabled-postgres-vector-store)

### 개요

[pgvector](https://github.com/pgvector/pgvector) 확장이 포함된 Postgres 데이터베이스를 vector store로 사용할 수 있습니다.

### 종속성 설치

Postgres vector store에는 `psycopg2` 및 `pgvector` 패키지가 모두 필요합니다:

```
pip install psycopg2-binary pgvector
```

### Postgres vector store 생성하기

`VectorStoreFactory.for_vector_store()` 정적 팩토리 메서드를 사용하여 Postgres vector store 인스턴스를 생성하세요.

Postgres vector store를 생성하려면 다음 형식의 연결 문자열을 제공하세요:

```
postgresql://[user[:password]@][netloc][:port][/dbname][?param1=value1&...]
```

예를 들어:

```
postgresql://graphrag:!zfg%dGGh@mydbcluster.cluster-123456789012.us-west-2.rds.amazonaws.com:5432/postgres
```

#### IAM 인증이 활성화된 Postgres vector store에 연결하기

Postgres 데이터베이스가 [AWS Identity and Access Management(IAM) 데이터베이스 인증](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)을 지원하는 경우, 비밀번호를 생략하고 연결 문자열 쿼리 매개변수에 `enable_iam_db_auth=True`를 추가하세요:

```
postgresql://graphrag@mydbcluster.cluster-123456789012.us-west-2.rds.amazonaws.com:5432/postgres?enable_iam_db_auth=True
```

데이터베이스 사용자를 생성하고 IAM 인증을 사용하기 위해 [`rds_iam` 역할을 부여](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.DBAccounts.html#UsingWithRDS.IAMDBAuth.DBAccounts.PostgreSQL)해야 합니다.

