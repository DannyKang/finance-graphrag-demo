"""Build a LexicalGraphIndex from LlamaIndex Documents."""

from __future__ import annotations

import logging
from typing import Optional

from llama_index.core.schema import Document

from tiger_etf.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ETF 도메인 온톨로지: Entity Classifications
# ---------------------------------------------------------------------------
ETF_ENTITY_CLASSIFICATIONS = [
    "ETF",                       # ETF 상품 (TIGER 미국S&P500, TIGER NVDA-UST 등)
    "Asset Management Company",  # 자산운용사 (미래에셋자산운용)
    "Index",                     # 추적 지수 (S&P500, KOSPI200, KEDI 미국 등)
    "Stock",                     # 개별 종목 (NVIDIA, Apple, Samsung 등)
    "Bond",                      # 채권 (US Treasury, 국고채 등)
    "Exchange",                  # 거래소 (한국거래소, NYSE 등)
    "Regulatory Body",           # 규제기관 (금융위원회, 금융감독원)
    "Regulation",                # 법률/규정 (자본시장법, 예금자보호법)
    "Trustee",                   # 수탁회사 (한국씨티은행 등)
    "Distributor",               # 판매회사 (증권사, 은행 등)
    "Sector",                    # 업종/섹터 (반도체, IT, 에너지)
    "Country",                   # 투자 국가 (미국, 한국, 일본)
    "Risk Factor",               # 위험 요소 (환율위험, 시장위험)
    "Fee",                       # 수수료/비용 (총보수, 판매수수료)
    "Benchmark",                 # 비교지수
    "Person",                    # 펀드매니저 등 인물
    "Derivative",                # 파생상품 (swap, option, futures)
]

# ---------------------------------------------------------------------------
# ETF 도메인 커스텀 프롬프트 (Topic + Entity + Relation 추출)
# ---------------------------------------------------------------------------
EXTRACT_TOPICS_PROMPT_ETF = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph for Korean ETF (Exchange Traded Fund) products.
Your input consists of carefully crafted propositions - simple, atomic, and decontextualized statements. Your task is to:
   1. Organize these propositions into topics
   2. Extract entities and their attributes
   3. Identify relationships between entities

Try to capture as much information from the text as possible without sacrificing accuracy. Do not add any information that is not explicitly mentioned in the input propositions.

## Domain-Specific Rules for ETF Knowledge Graph:

### Entity Classification Rules:
1. Entity classifications MUST be chosen from the Preferred Entity Classifications list below.
2. Do NOT create new classifications outside the list.
3. Classification guidance:
   - ETF products (투자신탁, 상장지수투자신탁, ETF) → "ETF"
   - 자산운용사, 집합투자업자 → "Asset Management Company"
   - 추적 지수, 기초지수 → "Index"
   - 개별 주식 종목 → "Stock"
   - 채권, 국채, 회사채 → "Bond"
   - 거래소 → "Exchange"
   - 금융위원회, 금융감독원 등 감독기관 → "Regulatory Body"
   - 법률, 규정, 시행령 → "Regulation"
   - 수탁회사, 신탁업자 → "Trustee"
   - 판매회사, 증권사, 은행 (판매 역할) → "Distributor"
   - 업종, 산업, 섹터 → "Sector"
   - 국가, 지역 → "Country"
   - 위험 요소 → "Risk Factor"
   - 수수료, 보수 → "Fee"
   - 비교지수 → "Benchmark"
   - 파생상품 (swap, option, futures) → "Derivative"
   - 펀드매니저 등 인물 → "Person"

### Relationship Type Rules:
1. Use ONLY the following relationship types:
   - MANAGES: 운용사가 ETF를 운용
   - TRACKS: ETF가 지수를 추적
   - INVESTS_IN: ETF가 종목/자산에 투자
   - LISTED_ON: ETF가 거래소에 상장
   - REGULATED_BY: 규제기관에 의해 규제
   - DISTRIBUTED_BY: 판매회사에 의해 판매
   - TRUSTEED_BY: 수탁회사에 의해 수탁
   - BENCHMARKED_AGAINST: 비교지수 대비
   - BELONGS_TO_SECTOR: 섹터에 속함
   - HAS_FEE: 수수료/보수 보유
   - HAS_RISK: 위험요소 보유
   - ISSUED_BY: 발행주체
   - LOCATED_IN: 국가/지역에 위치
   - HOLDS: 보유종목/자산
   - COMPONENT_OF: 지수의 구성종목
   - GOVERNED_BY: 법률/규정에 의해 규율
   - SUBSIDIARY_OF: 자회사 관계

### Entity Name Normalization Rules:
1. Use official Korean names for Korean entities (e.g., "미래에셋자산운용" not "Mirae Asset" or "Miraeasset")
2. For well-known indices, use standard names (e.g., "S&P 500", "KOSPI 200")
3. For stocks, use the company's most recognized name (e.g., "NVIDIA", "Apple")
4. Do NOT extract generic document structure entities (articles, sections, chapters, 제1조, 제2호)
5. Do NOT extract generic roles as entities (투자자, 수익자) unless they refer to specific named entities
6. Merge duplicate entities: if the same entity appears in Korean and English, use the Korean name

## Topic Extraction:
   1. Read the entire set of propositions and then extract a list of specific topics. Topic names should provide a clear, highly descriptive summary of the content.
      - Compare each topic with the list of Preferred Topics. If a preferred topic matches the new topic in its meaning and specificity, use the preferred topic. Otherwise, use the new topic.
   2. Each proposition must be assigned to at least one topic.
   3. For each topic, perform the following Entity Extraction and Proposition Organization tasks.

## Entity Extraction:
   1. Extract a list of all named entities mentioned in the propositions within each topic.
   2. DO NOT treat numerical values, dates, times, measurements, or object attributes as entities.
   3. Classify each entity using ONLY the Preferred Entity Classifications list.
   4. Ensure consistency in identifying entities:
      - Always use the most complete identifier for an entity.
      - Avoid using articles at the beginning of identifiers.
      - Maintain entity consistency by resolving coreferences.
      - If an entity is referred to by different names, always use the most complete identifier.

## Proposition Organization:
   1. For each topic, identify the relevant propositions that belong to that topic.
   2. Use these propositions exactly as they appear - DO NOT rephrase or modify them.
   3. For each proposition, perform the following Relationship Extraction and Attribute Extraction tasks.

## Relationship Extraction:
   1. Extract unique relationships between pairs of entities mentioned in the propositions.
   2. Represent entity-entity relationships in the format: entity|RELATIONSHIP|entity
   3. Use ONLY the allowed relationship types listed above.
   4. Relationship names should be all uppercase, with underscores instead of spaces.

   Example: TIGER 미국S&P500 ETF|TRACKS|S&P 500
            미래에셋자산운용|MANAGES|TIGER 미국S&P500 ETF
            TIGER 미국S&P500 ETF|INVESTS_IN|Apple

## Attribute Extraction:
   1. For each extracted entity, identify and extract its quantitative and qualitative attributes.
   2. Represent entity attributes in the format: entity|ATTRIBUTE_NAME|attribute
   3. Attribute names should be all uppercase, with underscores instead of spaces.
   4. Key attributes for ETF domain:
      - ETF: HAS_TICKER, HAS_NAV, HAS_AUM, HAS_INCEPTION_DATE, HAS_TYPE
      - Fee: HAS_RATE, HAS_TYPE
      - Stock: HAS_WEIGHT, HAS_MARKET_CAP

## Response Format:
topic: topic

  entities:

    entity|label
    entity|label

  proposition: [exact proposition text]

    entity-entity relationships:
    entity|RELATIONSHIP|entity
    entity|RELATIONSHIP|entity

    entity-attributes:
    entity|ATTRIBUTE_NAME|value
    entity|ATTRIBUTE_NAME|value

  proposition: [exact proposition text]

    entity-entity relationships:
    entity|RELATIONSHIP|entity
    entity|RELATIONSHIP|entity

    entity-attributes:
    entity|ATTRIBUTE_NAME|value
    entity|ATTRIBUTE_NAME|value


## Quality Criteria:
   - Complete: Capture all input propositions and their relationships
   - Accurate: Faithfully represent the information without adding or omitting details
   - Consistent: Use consistent entity labels, relationship types, and attribute names

## Strict Compliance:
   - Use propositions exactly as provided - do not rephrase or modify them
   - Assign every proposition to at least one topic
   - Follow the specified format exactly
   - Do not provide any other explanatory text
   - Extract only information explicitly stated in the propositions
   - Use ONLY the allowed entity classifications and relationship types

Adhere strictly to the provided instructions. Non-compliance will result in termination.

<propositions>
{text}
</propositions>

<preferredTopics>
{preferred_topics}
</preferredTopics>

<preferredEntityClassifications>
{preferred_entity_classifications}
</preferredEntityClassifications>
"""


def _configure() -> None:
    """Set GraphRAGConfig before creating stores."""
    from graphrag_toolkit.lexical_graph import GraphRAGConfig

    GraphRAGConfig.aws_region = settings.graphrag_aws_region
    GraphRAGConfig.extraction_llm = settings.graphrag_extraction_llm
    GraphRAGConfig.response_llm = settings.graphrag_response_llm
    GraphRAGConfig.embed_model = settings.graphrag_embedding_model
    GraphRAGConfig.enable_cache = settings.graphrag_enable_cache
    GraphRAGConfig.extraction_num_workers = settings.graphrag_extraction_num_workers
    GraphRAGConfig.extraction_num_threads_per_worker = settings.graphrag_extraction_num_threads_per_worker
    # Neptune DB: configurable via config.yaml graphrag.build_num_workers / batch_writes_enabled
    GraphRAGConfig.build_num_workers = settings.graphrag_build_num_workers
    GraphRAGConfig.batch_writes_enabled = settings.graphrag_batch_writes_enabled


def _make_stores():
    """Create graph and vector store instances.

    Neptune Analytics is auto-detected by graphrag_toolkit via
    connection string prefix (neptune-graph://).
    Both graph and vector use the same Neptune Analytics endpoint.
    """
    from graphrag_toolkit.lexical_graph.storage import (
        GraphStoreFactory,
        VectorStoreFactory,
    )

    graph_store = GraphStoreFactory.for_graph_store(settings.graph_store)
    vector_store = VectorStoreFactory.for_vector_store(settings.vector_store)
    return graph_store, vector_store


def _make_extraction_config():
    """Create ExtractionConfig with ETF domain ontology."""
    from graphrag_toolkit.lexical_graph.lexical_graph_index import ExtractionConfig

    return ExtractionConfig(
        preferred_entity_classifications=ETF_ENTITY_CLASSIFICATIONS,
        extract_topics_prompt_template=EXTRACT_TOPICS_PROMPT_ETF,
    )


def build_index(documents: list[Document]) -> None:
    """Extract entities/relations and build the lexical graph index."""
    from graphrag_toolkit.lexical_graph import LexicalGraphIndex

    _configure()
    graph_store, vector_store = _make_stores()
    extraction_config = _make_extraction_config()

    logger.info("Building LexicalGraphIndex from %d documents ...", len(documents))
    logger.info("Using ETF domain ontology: %d entity classes, custom prompt",
                len(ETF_ENTITY_CLASSIFICATIONS))
    graph_index = LexicalGraphIndex(
        graph_store, vector_store,
        indexing_config=extraction_config,
    )
    graph_index.extract_and_build(documents, show_progress=True)
    logger.info("Index build complete.")


def build_from_pdfs(limit: Optional[int] = None) -> None:
    """Load PDFs and build index."""
    from tiger_etf.graphrag.loader import load_pdfs

    docs = load_pdfs(limit=limit)
    if not docs:
        logger.warning("No PDF documents found.")
        return
    build_index(docs)


def build_from_rdb(limit: Optional[int] = None) -> None:
    """Load RDB data and build index."""
    from tiger_etf.graphrag.loader import load_rdb

    docs = load_rdb(limit=limit)
    if not docs:
        logger.warning("No RDB documents found.")
        return
    build_index(docs)


def reset_graph() -> int:
    """Delete all nodes and edges from Neptune graph store.

    Returns the number of deleted nodes.
    """
    import boto3

    from tiger_etf.graphrag.query import _extract_region_from_endpoint, _parse_graph_store_uri

    store_type, identifier = _parse_graph_store_uri(settings.graph_store)
    region = _extract_region_from_endpoint(identifier)
    session = boto3.Session(region_name=region)

    if store_type == "database":
        client = session.client(
            "neptunedata",
            endpoint_url=f"https://{identifier}:8182",
        )
        # Count before delete
        count_result = client.execute_open_cypher_query(
            openCypherQuery="MATCH (n) RETURN count(n) AS cnt",
        )
        total = count_result["results"][0]["cnt"] if count_result["results"] else 0

        # Delete in batches to avoid timeout on large graphs
        deleted = 0
        batch_size = 10000
        while True:
            result = client.execute_open_cypher_query(
                openCypherQuery=f"MATCH (n) WITH n LIMIT {batch_size} DETACH DELETE n RETURN count(*) AS cnt",
            )
            cnt = result["results"][0]["cnt"] if result["results"] else 0
            deleted += cnt
            logger.info("Deleted %d nodes (total: %d)", cnt, deleted)
            if cnt < batch_size:
                break

        logger.info("Graph reset complete. Deleted %d nodes total.", deleted)
        return total
    else:
        # Neptune Analytics
        client = session.client("neptune-graph")
        count_resp = client.execute_query(
            graphIdentifier=identifier,
            queryString="MATCH (n) RETURN count(n) AS cnt",
            parameters={},
            language="OPEN_CYPHER",
            planCache="DISABLED",
        )
        import json
        results = json.loads(count_resp["payload"].read())["results"]
        total = results[0]["cnt"] if results else 0

        client.execute_query(
            graphIdentifier=identifier,
            queryString="MATCH (n) DETACH DELETE n",
            parameters={},
            language="OPEN_CYPHER",
            planCache="DISABLED",
        )
        logger.info("Graph reset complete. Deleted %d nodes.", total)
        return total


def reset_vector() -> int:
    """Delete vector embeddings from Neptune Analytics.

    Removes the vector property from all nodes that have embeddings.
    Returns the number of nodes that had embeddings removed.
    """
    import json

    import boto3

    from tiger_etf.graphrag.query import _parse_graph_store_uri

    store_type, identifier = _parse_graph_store_uri(settings.vector_store)
    if store_type != "analytics":
        raise ValueError(
            f"reset_vector only supports Neptune Analytics (neptune-graph://), got: {settings.vector_store}"
        )

    region = settings.graphrag_aws_region
    session = boto3.Session(region_name=region)
    client = session.client("neptune-graph")

    def run_query(cypher: str) -> list:
        response = client.execute_query(
            graphIdentifier=identifier,
            queryString=cypher,
            parameters={},
            language="OPEN_CYPHER",
            planCache="DISABLED",
        )
        return json.loads(response["payload"].read())["results"]

    # Count nodes with vector embeddings (chunk and statement labels)
    deleted_total = 0
    for label in ["Chunk", "Statement"]:
        results = run_query(
            f"MATCH (n:`{label}`) RETURN count(n) AS cnt"
        )
        count = results[0]["cnt"] if results else 0
        if count > 0:
            run_query(f"MATCH (n:`{label}`) DETACH DELETE n")
            logger.info("Deleted %d '%s' vector nodes.", count, label)
            deleted_total += count
        else:
            logger.info("No '%s' vector nodes found, skipping.", label)

    logger.info("Vector reset complete. Deleted %d nodes total.", deleted_total)
    return deleted_total


def reset_all() -> dict:
    """Reset both graph and vector stores. Returns counts."""
    graph_count = reset_graph()
    vector_count = reset_vector()
    return {"graph_nodes_deleted": graph_count, "vector_docs_deleted": vector_count}


def build_all(pdf_limit: Optional[int] = None, rdb_limit: Optional[int] = None) -> None:
    """Load all sources (PDFs + RDB) and build index."""
    from tiger_etf.graphrag.loader import load_pdfs, load_rdb

    docs: list[Document] = []
    docs.extend(load_pdfs(limit=pdf_limit))
    docs.extend(load_rdb(limit=rdb_limit))

    if not docs:
        logger.warning("No documents found.")
        return
    build_index(docs)
