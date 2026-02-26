[[Home](./)]

## FAQ

  - [오류 및 경고](#errors-and-warnings)
    - [RuntimeError: Please use nest_asyncio.apply() to allow nested event loops](#runtimeerror-please-use-nest_asyncioapply-to-allow-nested-event-loops)
    - [ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: \<identity\> is not authorized to perform: bedrock:InvokeModel](#modelerror-an-error-occurred-accessdeniedexception-when-calling-the-invokemodel-operation-identity-is-not-authorized-to-perform-bedrockinvokemodel)
    - [ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: You don't have access to the model with the specified model ID](#modelerror-an-error-occurred-accessdeniedexception-when-calling-the-invokemodel-operation-you-dont-have-access-to-the-model-with-the-specified-model-id)
    - [WARNING:graph_store:Retrying query in x seconds because it raised ConcurrentModificationException](#warninggraph_storeretrying-query-in-x-seconds-because-it-raised-concurrentmodificationexception)

### 오류 및 경고

#### RuntimeError: Please use nest_asyncio.apply() to allow nested event loops

`nest_asyncio.apply()`는 중첩된 이벤트 루프를 활성화하고 Python에서 복잡한 비동기 프로그래밍 상황을 더 쉽게 처리할 수 있게 하는 편리한 솔루션을 제공합니다. 문서의 모든 코드 예제에는 `nest_asyncio.apply()`가 포함되어 있습니다. 그러나 이 예제들은 Jupyter 노트북에서 실행되도록 포맷되어 있습니다. 메인 진입점이 있는 애플리케이션을 구축하는 경우 이 런타임 오류가 발생할 수 있습니다. 해결하려면 애플리케이션 로직을 메서드 안에 넣고 `if __name__ == '__main__'` 블록을 추가하세요:

```python
import os

from graphrag_toolkit.lexical_graph import LexicalGraphIndex
from graphrag_toolkit.lexical_graph.storage import GraphStoreFactory
from graphrag_toolkit.lexical_graph.storage import VectorStoreFactory

from llama_index.readers.web import SimpleWebPageReader

import nest_asyncio
nest_asyncio.apply()

def run_extract_and_build():

    graph_store = GraphStoreFactory.for_graph_store(
        'neptune-db://my-graph.cluster-abcdefghijkl.us-east-1.neptune.amazonaws.com'
    )

    vector_store = VectorStoreFactory.for_vector_store(
        'aoss://https://abcdefghijkl.us-east-1.aoss.amazonaws.com'
    )

    graph_index = LexicalGraphIndex(
        graph_store,
        vector_store
    )

    doc_urls = [
        'https://docs.aws.amazon.com/neptune/latest/userguide/intro.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html',
        'https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html'
    ]

    docs = SimpleWebPageReader(
        html_to_text=True,
        metadata_fn=lambda url:{'url': url}
    ).load_data(doc_urls)

    graph_index.extract_and_build(docs, show_progress=True)

if __name__ == '__main__':
    run_extract_and_build()
```

---

#### ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: \<identity\> is not authorized to perform: bedrock:InvokeModel

애플리케이션이 실행되는 AWS Identity and Access Management (IAM) ID에 Amazon Bedrock 파운데이션 모델을 호출할 권한이 없는 경우, 다음과 유사한 오류가 발생합니다:

```
graphrag_toolkit.errors.ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: <identity> is not authorized to perform: bedrock:InvokeModel on resource: arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0 because no identity-based policy allows the bedrock:InvokeModel action [Model config: {"system_prompt": null, "pydantic_program_mode": "default", "model": "anthropic.claude-3-5-haiku-20241022-v1:0", "temperature": 0.0, "max_tokens": 4096, "context_size": 200000, "profile_name": null, "max_retries": 10, "timeout": 60.0, "additional_kwargs": {}, "class_name": "Bedrock_LLM"}]
```

해결하려면, Amazon Bedrock에서 적절한 파운데이션 모델에 대한 [접근을 활성화](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)한 다음, ID에 연결된 IAM 정책을 업데이트하세요:

```
{
    "Effect": "Allow",
    "Action": [
        "bedrock:InvokeModel"
    ],
    "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0"
    ]
}
```

---

#### ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: You don't have access to the model with the specified model ID

Amazon Bedrock 파운데이션 모델에 대한 접근은 기본적으로 부여되지 않습니다. 파운데이션 모델에 대한 접근을 활성화하지 않은 경우, 다음과 유사한 오류가 발생합니다:

```
graphrag_toolkit.errors.ModelError: An error occurred (AccessDeniedException) when calling the InvokeModel operation: You don't have access to the model with the specified model ID. [Model config: {"system_prompt": null, "pydantic_program_mode":"default", "model": "anthropic.claude-3-7-sonnet-20250219-v1:0", "temperature": 0.0, "max_tokens": 4096, "context_size": 200000, "profile_name": null, "max_retries": 10, "timeout": 60.0, "additional_kwargs": {}, "class_name": "Bedrock_LLM"}]
```

해결하려면, Amazon Bedrock에서 적절한 파운데이션 모델에 대한 [접근을 활성화](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)한 다음, [모델에 IAM 권한을 부여](#modelerror-an-error-occurred-accessdeniedexception-when-calling-the-invokemodel-operation-identity-is-not-authorized-to-perform-bedrockinvokemodel)하세요.

---

#### WARNING:graph_store:Retrying query in x seconds because it raised ConcurrentModificationException

Amazon Neptune Database에서 데이터를 인덱싱하는 동안, Neptune은 때때로 `ConcurrentModificationException`을 발생시킬 수 있습니다. 이는 여러 워커가 [동일한 정점 세트를 업데이트](https://docs.aws.amazon.com/neptune/latest/userguide/transactions-exceptions.html)하려고 시도하기 때문에 발생합니다. GraphRAG Toolkit은 `ConcurrentModificationException`으로 인해 취소된 트랜잭션을 자동으로 재시도합니다. 최대 재시도 횟수를 초과하여 인덱싱이 실패하면, [`GraphRAGConfig.build_num_workers`](./configuration.md#graphragconfig)를 사용하여 build 단계의 워커 수를 줄이는 것을 고려하세요.

---
