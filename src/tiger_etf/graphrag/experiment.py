"""Experiment framework for comparing GraphRAG configurations.

Each experiment uses the same Neptune + OpenSearch infrastructure
with configuration overrides from YAML files.
"""

from __future__ import annotations

import json
import logging
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
    """Run a full experiment.

    Flow:
      1. Apply config overrides to GraphRAGConfig
      2. Run indexing (unless skip_indexing)
      3. Collect graph metrics
      4. Run evaluation queries
      5. Save results JSON
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

    # Step 1: Configure GraphRAG
    _apply_config(config)

    if not skip_indexing:
        # Step 2: Run indexing
        logger.info("Step 1: Running indexing...")
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

    # Step 3: Collect metrics
    logger.info("Step 2: Collecting metrics...")
    result["metrics"] = collect_metrics()

    # Step 4: Eval queries
    logger.info("Step 3: Running eval queries...")
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

    GraphRAGConfig.aws_region = settings.graphrag_aws_region
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
    from tiger_etf.graphrag.indexer import _make_extraction_config

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
