"""Query the LexicalGraph using traversal-based search."""

from __future__ import annotations

import json
import logging

import boto3

from tiger_etf.config import settings

logger = logging.getLogger(__name__)


def get_query_engine():
    """Create and return a LexicalGraphQueryEngine."""
    from graphrag_toolkit.lexical_graph import GraphRAGConfig, LexicalGraphQueryEngine
    from graphrag_toolkit.lexical_graph.storage import (
        GraphStoreFactory,
        VectorStoreFactory,
    )

    GraphRAGConfig.aws_region = settings.graphrag_aws_region
    GraphRAGConfig.extraction_llm = settings.graphrag_extraction_llm
    GraphRAGConfig.response_llm = settings.graphrag_response_llm
    GraphRAGConfig.embed_model = settings.graphrag_embedding_model

    graph_store = GraphStoreFactory.for_graph_store(settings.graph_store_reader)
    vector_store = VectorStoreFactory.for_vector_store(settings.vector_store)

    return LexicalGraphQueryEngine.for_traversal_based_search(
        graph_store, vector_store
    )


def query(question: str) -> str:
    """Run a traversal-based search query and return the response text."""
    engine = get_query_engine()
    logger.info("Querying: %s", question)
    response = engine.query(question)
    return str(response)


def _parse_graph_store_uri(uri: str) -> tuple[str, str]:
    """Parse graph_store URI and return (type, identifier).

    Returns:
        ("analytics", graph_id) for neptune-graph://<graph-id>
        ("database", endpoint)  for neptune-db://<endpoint> or *.neptune.amazonaws.com
    """
    if uri.startswith("neptune-graph://"):
        return "analytics", uri.replace("neptune-graph://", "")
    if uri.startswith("neptune-db://"):
        return "database", uri.replace("neptune-db://", "")
    if "neptune.amazonaws.com" in uri:
        endpoint = uri.replace("https://", "").split(":")[0]
        return "database", endpoint
    raise ValueError(f"Unsupported graph_store URI for stats: {uri}")


def _extract_region_from_endpoint(endpoint: str) -> str:
    """Extract AWS region from a Neptune endpoint hostname.

    Example: 'db-xxx.cluster-yyy.ap-northeast-2.neptune.amazonaws.com' → 'ap-northeast-2'
    """
    parts = endpoint.split(".")
    for i, part in enumerate(parts):
        if part == "neptune" and i > 0:
            return parts[i - 1]
    return settings.graphrag_aws_region


def get_graph_stats() -> dict:
    """Return node/edge counts from Neptune using OpenCypher queries."""
    store_type, identifier = _parse_graph_store_uri(settings.graph_store_reader)

    if store_type == "analytics":
        return _stats_neptune_analytics(identifier)
    else:
        return _stats_neptune_database(identifier)


def _stats_neptune_analytics(graph_id: str) -> dict:
    """Collect graph stats from Neptune Analytics."""
    region = _extract_region_from_endpoint(graph_id)
    session = boto3.Session(region_name=region)
    client = session.client("neptune-graph")

    def run_query(cypher: str) -> list:
        response = client.execute_query(
            graphIdentifier=graph_id,
            queryString=cypher,
            parameters={},
            language="OPEN_CYPHER",
            planCache="DISABLED",
        )
        return json.loads(response["payload"].read())["results"]

    node_results = run_query(
        "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt"
    )
    nodes = {str(r["labels"]): r["cnt"] for r in node_results}

    edge_results = run_query(
        "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt"
    )
    edges = {r["type"]: r["cnt"] for r in edge_results}

    return {"nodes": nodes, "edges": edges}


def _stats_neptune_database(endpoint: str) -> dict:
    """Collect graph stats from Neptune Database."""
    region = _extract_region_from_endpoint(endpoint)
    session = boto3.Session(region_name=region)
    client = session.client(
        "neptunedata",
        endpoint_url=f"https://{endpoint}:8182",
    )

    def run_query(cypher: str) -> list:
        response = client.execute_open_cypher_query(
            openCypherQuery=cypher,
        )
        return response["results"]

    node_results = run_query(
        "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt"
    )
    nodes = {str(r["labels"]): r["cnt"] for r in node_results}

    edge_results = run_query(
        "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt"
    )
    edges = {r["type"]: r["cnt"] for r in edge_results}

    return {"nodes": nodes, "edges": edges}
