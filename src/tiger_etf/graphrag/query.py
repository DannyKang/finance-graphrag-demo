"""Query the LexicalGraph using traversal-based search."""

from __future__ import annotations

import logging

from tiger_etf.config import settings

logger = logging.getLogger(__name__)


def get_query_engine():
    """Create and return a LexicalGraphQueryEngine."""
    from graphrag_toolkit.lexical_graph import GraphRAGConfig, LexicalGraphQueryEngine
    from graphrag_toolkit.lexical_graph.storage import (
        GraphStoreFactory,
        VectorStoreFactory,
    )
    from graphrag_toolkit.lexical_graph.storage.graph.neo4j_graph_store_factory import (
        Neo4jGraphStoreFactory,
    )

    GraphRAGConfig.aws_region = "us-east-1"
    GraphRAGConfig.extraction_llm = settings.graphrag_extraction_llm
    GraphRAGConfig.response_llm = settings.graphrag_response_llm
    GraphRAGConfig.embedding_model = settings.graphrag_embedding_model

    GraphStoreFactory.register(Neo4jGraphStoreFactory)

    graph_store = GraphStoreFactory.for_graph_store(settings.graph_store)
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


def get_graph_stats() -> dict:
    """Return node/edge counts from Neo4j."""
    from neo4j import GraphDatabase

    # Parse bolt URI and auth from settings.graph_store
    # Format: bolt://user:pass@host:port
    uri = settings.graph_store
    auth = None
    if "://" in uri:
        scheme_rest = uri.split("://", 1)
        scheme = scheme_rest[0]
        rest = scheme_rest[1]
        if "@" in rest:
            creds, host_port = rest.rsplit("@", 1)
            user, password = creds.split(":", 1)
            auth = (user, password)
            uri = f"{scheme}://{host_port}"

    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        with driver.session() as session:
            node_result = session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt"
            )
            nodes = {str(r["labels"]): r["cnt"] for r in node_result}

            edge_result = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt"
            )
            edges = {r["type"]: r["cnt"] for r in edge_result}

            return {"nodes": nodes, "edges": edges}
    finally:
        driver.close()
