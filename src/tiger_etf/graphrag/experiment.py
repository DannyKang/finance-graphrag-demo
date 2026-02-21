"""Experiment framework for comparing GraphRAG configurations.

Each experiment runs in isolated Docker containers with separate volumes,
so data from previous experiments is preserved.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from llama_index.core.schema import Document

from tiger_etf.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
CONFIGS_DIR = EXPERIMENTS_DIR / "configs"
RESULTS_DIR = EXPERIMENTS_DIR / "results"
COMPOSE_DIR = PROJECT_ROOT / "docker" / "graphrag"
COMPOSE_TEMPLATE = COMPOSE_DIR / "docker-compose.yml"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_experiment_config(config_name: str) -> dict[str, Any]:
    config_path = CONFIGS_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def list_configs() -> list[str]:
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.yaml"))


def list_results() -> list[dict[str, Any]]:
    results = []
    for p in sorted(RESULTS_DIR.glob("*.json")):
        with open(p) as f:
            data = json.load(f)
        results.append({
            "name": data.get("name", p.stem),
            "description": data.get("description", ""),
            "extraction_llm": data.get("config", {}).get("extraction_llm", ""),
            "embedding_model": data.get("config", {}).get("embedding_model", ""),
            "total_nodes": data.get("metrics", {}).get("total_nodes", 0),
            "total_edges": data.get("metrics", {}).get("total_edges", 0),
            "duration_min": data.get("duration_minutes", 0),
            "file": p.name,
        })
    return results


# ---------------------------------------------------------------------------
# Docker container management
# ---------------------------------------------------------------------------

def _compose_file_for(experiment_name: str) -> Path:
    return COMPOSE_DIR / f"docker-compose.{experiment_name}.yml"


def generate_compose_file(experiment_name: str) -> Path:
    """Generate a docker-compose file with experiment-specific volume names."""
    content = f"""# Auto-generated for experiment: {experiment_name}
services:
  neo4j:
    image: neo4j:5-community
    container_name: graphrag-neo4j-{experiment_name}
    ports:
      - "7476:7474"
      - "7689:7687"
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '[\"apoc\"]'
    volumes:
      - neo4j_data:/data

  graphrag-postgres:
    image: pgvector/pgvector:pg16
    container_name: graphrag-pg-{experiment_name}
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: graphrag
      POSTGRES_PASSWORD: graphragpass
      POSTGRES_DB: graphrag_db
    volumes:
      - graphrag_pg_data:/var/lib/postgresql/data

  neodash:
    image: neo4jlabs/neodash:latest
    container_name: graphrag-neodash-{experiment_name}
    ports:
      - "5005:5005"
    environment:
      ssoEnabled: "false"
      standalone: "false"
    depends_on:
      - neo4j

volumes:
  neo4j_data:
    name: graphrag_neo4j_{experiment_name}
  graphrag_pg_data:
    name: graphrag_pg_{experiment_name}
"""
    path = _compose_file_for(experiment_name)
    path.write_text(content)
    logger.info("Generated compose file: %s", path)
    return path


def stop_all_experiments() -> None:
    """Stop any running graphrag experiment containers."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=graphrag-", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    if not containers:
        logger.info("No running experiment containers found.")
        return

    logger.info("Stopping containers: %s", ", ".join(containers))
    subprocess.run(["docker", "stop", *containers], check=True)
    subprocess.run(["docker", "rm", *containers], check=False)


def start_experiment_containers(experiment_name: str) -> None:
    """Stop any running experiment containers, then start this experiment's."""
    stop_all_experiments()

    compose_file = _compose_file_for(experiment_name)
    if not compose_file.exists():
        compose_file = generate_compose_file(experiment_name)

    logger.info("Starting containers for experiment: %s", experiment_name)
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=str(COMPOSE_DIR), check=True,
    )
    _wait_for_services()


def _wait_for_services(timeout: int = 60) -> None:
    """Wait until Neo4j and PostgreSQL are accepting connections."""
    import socket

    services = [("localhost", 7689, "Neo4j"), ("localhost", 5433, "PostgreSQL")]
    deadline = time.time() + timeout

    for host, port, name in services:
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=2):
                    logger.info("%s is ready (port %d)", name, port)
                    break
            except OSError:
                time.sleep(2)
        else:
            raise TimeoutError(f"{name} did not become ready within {timeout}s")


def get_active_experiment() -> str | None:
    """Return the name of the currently running experiment, or None."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=graphrag-neo4j-",
         "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    name = result.stdout.strip()
    if name and name.startswith("graphrag-neo4j-"):
        return name.replace("graphrag-neo4j-", "")
    return None


def list_experiment_volumes() -> list[dict[str, str]]:
    """List Docker volumes for each experiment."""
    result = subprocess.run(
        ["docker", "volume", "ls", "--filter", "name=graphrag_",
         "--format", "{{.Name}}"],
        capture_output=True, text=True,
    )
    volumes = [v.strip() for v in result.stdout.strip().split("\n") if v.strip()]

    experiments: dict[str, dict[str, str]] = {}
    for vol in volumes:
        if vol.startswith("graphrag_neo4j_"):
            exp = vol.replace("graphrag_neo4j_", "")
            experiments.setdefault(exp, {})["neo4j"] = vol
        elif vol.startswith("graphrag_pg_"):
            exp = vol.replace("graphrag_pg_", "")
            experiments.setdefault(exp, {})["pg"] = vol

    return [{"name": k, **v} for k, v in sorted(experiments.items())]


# ---------------------------------------------------------------------------
# Metrics & evaluation
# ---------------------------------------------------------------------------

def collect_metrics() -> dict[str, Any]:
    from tiger_etf.graphrag.query import get_graph_stats

    stats = get_graph_stats()
    total_nodes = sum(stats["nodes"].values())
    total_edges = sum(stats["edges"].values())

    source_count = 0
    for label_str, count in stats["nodes"].items():
        if "Source" in label_str:
            source_count = count

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "source_count": source_count,
        "node_distribution": stats["nodes"],
        "edge_distribution": stats["edges"],
    }


def run_eval_queries(config: dict[str, Any]) -> list[dict[str, Any]]:
    from tiger_etf.graphrag.query import query

    results = []
    for q in config.get("eval_queries", []):
        logger.info("Eval query: %s", q)
        start = time.time()
        try:
            response = query(q)
            elapsed = time.time() - start
            results.append({
                "query": q,
                "response": response[:2000],
                "latency_seconds": round(elapsed, 2),
                "status": "success",
            })
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "query": q,
                "response": str(e),
                "latency_seconds": round(elapsed, 2),
                "status": "error",
            })
        logger.info("  -> %.1fs", elapsed)
    return results


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def run_experiment(config_name: str, skip_indexing: bool = False) -> dict[str, Any]:
    """Run a full experiment with isolated Docker containers.

    Flow:
      1. Stop running containers
      2. Start containers with experiment-specific volumes
      3. Run indexing (unless skip_indexing)
      4. Collect graph metrics
      5. Run evaluation queries
      6. Save results JSON
    """
    config = load_experiment_config(config_name)
    exp_name = config["name"]
    logger.info("=== Experiment: %s ===", exp_name)

    result: dict[str, Any] = {
        "name": exp_name,
        "description": config.get("description", ""),
        "config": {
            "extraction_llm": config["extraction_llm"],
            "response_llm": config["response_llm"],
            "embedding_model": config["embedding_model"],
            "pdf_limit": config.get("pdf_limit"),
        },
        "started_at": datetime.now().isoformat(),
    }

    # Step 1: Switch Docker containers
    logger.info("Step 1: Switching to experiment containers...")
    start_experiment_containers(exp_name)

    # Step 2: Configure GraphRAG
    _apply_config(config)

    if not skip_indexing:
        # Step 3: Run indexing
        logger.info("Step 2: Running indexing...")
        from tiger_etf.graphrag.loader import load_pdfs
        docs = load_pdfs(limit=config.get("pdf_limit"))
        if not docs:
            raise RuntimeError("No PDF documents found.")

        start_time = time.time()
        _run_indexing(docs)
        elapsed = time.time() - start_time
        result["indexing_duration_seconds"] = round(elapsed, 1)
        result["duration_minutes"] = round(elapsed / 60, 1)
        result["document_count"] = len(docs)
    else:
        logger.info("Skipping indexing (--skip-indexing)")

    # Step 4: Collect metrics
    logger.info("Step 3: Collecting metrics...")
    result["metrics"] = collect_metrics()

    # Step 5: Eval queries
    logger.info("Step 4: Running eval queries...")
    result["eval_results"] = run_eval_queries(config)

    successful = [r for r in result["eval_results"] if r["status"] == "success"]
    avg_latency = (
        sum(r["latency_seconds"] for r in successful) / len(successful)
        if successful else 0
    )
    result["avg_query_latency_seconds"] = round(avg_latency, 2)
    result["completed_at"] = datetime.now().isoformat()

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"{exp_name}_{ts}.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info("Results saved to %s", result_path)
    return result


def _apply_config(config: dict[str, Any]) -> None:
    from graphrag_toolkit.lexical_graph import GraphRAGConfig

    GraphRAGConfig.aws_region = "us-east-1"
    GraphRAGConfig.extraction_llm = config["extraction_llm"]
    GraphRAGConfig.response_llm = config["response_llm"]
    GraphRAGConfig.embedding_model = config["embedding_model"]
    GraphRAGConfig.enable_cache = config.get("enable_cache", True)
    GraphRAGConfig.extraction_num_workers = config.get("extraction_num_workers", 1)
    GraphRAGConfig.extraction_num_threads_per_worker = config.get(
        "extraction_num_threads_per_worker", 8,
    )


def _run_indexing(docs: list[Document]) -> None:
    from graphrag_toolkit.lexical_graph import LexicalGraphIndex
    from graphrag_toolkit.lexical_graph.storage import (
        GraphStoreFactory,
        VectorStoreFactory,
    )
    from graphrag_toolkit.lexical_graph.storage.graph.neo4j_graph_store_factory import (
        Neo4jGraphStoreFactory,
    )
    from tiger_etf.graphrag.indexer import _make_extraction_config

    GraphStoreFactory.register(Neo4jGraphStoreFactory)
    graph_store = GraphStoreFactory.for_graph_store(settings.graph_store)
    vector_store = VectorStoreFactory.for_vector_store(settings.vector_store)

    extraction_config = _make_extraction_config()
    logger.info("Building index from %d documents...", len(docs))
    graph_index = LexicalGraphIndex(
        graph_store, vector_store,
        indexing_config=extraction_config,
    )
    graph_index.extract_and_build(docs, show_progress=True)
    logger.info("Indexing complete.")
