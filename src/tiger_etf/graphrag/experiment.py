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


def run_eval_queries(
    config: dict[str, Any],
    eval_questions_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Run evaluation queries from eval_questions.yaml (or config fallback).

    If eval_questions_path is provided and exists, all questions from the YAML
    are used.  Otherwise falls back to ``config["eval_queries"]``.
    """
    from tiger_etf.graphrag.evaluator import load_eval_questions
    from tiger_etf.graphrag.query import query

    # Determine question list
    questions: list[str] = []
    if eval_questions_path and eval_questions_path.exists():
        eq_list = load_eval_questions(eval_questions_path)
        questions = [eq.question for eq in eq_list]
        logger.info("Loaded %d eval questions from %s", len(questions), eval_questions_path)
    else:
        questions = config.get("eval_queries", [])
        logger.info("Using %d eval queries from experiment config", len(questions))

    results = []
    for idx, q in enumerate(questions, 1):
        logger.info("[%d/%d] Eval query: %s", idx, len(questions), q)
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

def run_experiment(
    config_name: str,
    skip_indexing: bool = False,
    use_llm_judge: bool = True,
    eval_questions_path: Path | None = None,
) -> dict[str, Any]:
    """Run a full experiment.

    Flow:
      1. Apply config overrides to GraphRAGConfig
      2. Run indexing (unless skip_indexing)
      3. Collect graph metrics
      4. Run evaluation queries
      5. Run evaluation scoring
      6. Save results JSON
    """
    from tiger_etf.graphrag.evaluator import (
        EVAL_QUESTIONS_PATH,
        format_eval_report,
        load_eval_questions,
        report_to_dict,
        run_evaluation,
    )

    eval_path = eval_questions_path or EVAL_QUESTIONS_PATH
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
    result["eval_results"] = run_eval_queries(config, eval_questions_path=eval_path)

    successful = [r for r in result["eval_results"] if r["status"] == "success"]
    avg_latency = (
        sum(r["latency_seconds"] for r in successful) / len(successful)
        if successful else 0
    )
    result["avg_query_latency_seconds"] = round(avg_latency, 2)

    # Step 5: Evaluation scoring
    logger.info("Step 4: Running evaluation scoring (llm_judge=%s)...", use_llm_judge)
    try:
        eq_list = load_eval_questions(eval_path)
        eval_report = run_evaluation(
            eval_results=result["eval_results"],
            eval_questions=eq_list,
            use_llm_judge=use_llm_judge,
        )
        result["evaluation"] = report_to_dict(eval_report)
        logger.info("Overall score: %.3f", eval_report.overall_score)
        logger.info("\n%s", format_eval_report(eval_report))
    except FileNotFoundError:
        logger.warning("eval_questions.yaml not found — skipping evaluation scoring")
    except Exception as e:
        logger.warning("Evaluation scoring failed: %s", e)

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
