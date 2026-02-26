"""Click CLI entry point for tiger-etf."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from tiger_etf.utils.logging_config import setup_logging

console = Console()


@click.group()
def cli() -> None:
    """TIGER ETF data pipeline CLI."""
    setup_logging()


# --- db commands ---


@cli.group()
def db() -> None:
    """Database management commands."""


@db.command("init")
def db_init() -> None:
    """Create schema and tables."""
    from tiger_etf.db import init_schema

    console.print("[bold]Initializing database schema...[/bold]")
    init_schema()
    console.print("[green]Schema created successfully.[/green]")


# --- scrape commands ---


@cli.group()
def scrape() -> None:
    """Data scraping commands."""


@scrape.command("list")
def scrape_list() -> None:
    """Scrape ETF product list."""
    from tiger_etf.scrapers.product_list import ProductListScraper

    console.print("[bold]Scraping ETF product list...[/bold]")
    s = ProductListScraper()
    try:
        s.run()
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("detail")
@click.option("--limit", type=int, default=None, help="Limit number of products to scrape.")
def scrape_detail(limit: int | None) -> None:
    """Scrape ETF product detail pages."""
    from tiger_etf.scrapers.product_detail import ProductDetailScraper

    console.print(f"[bold]Scraping ETF detail pages (limit={limit})...[/bold]")
    s = ProductDetailScraper()
    try:
        s.run(limit=limit)
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("perf")
@click.option("--limit", type=int, default=None, help="Limit number of products.")
def scrape_perf(limit: int | None) -> None:
    """Scrape performance data."""
    from tiger_etf.scrapers.performance import PerformanceScraper

    console.print("[bold]Scraping performance data...[/bold]")
    s = PerformanceScraper()
    try:
        s.run(limit=limit)
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("holdings")
@click.option("--limit", type=int, default=None, help="Limit number of products.")
def scrape_holdings(limit: int | None) -> None:
    """Scrape holdings data."""
    from tiger_etf.scrapers.holdings import HoldingsScraper

    console.print("[bold]Scraping holdings data...[/bold]")
    s = HoldingsScraper()
    try:
        s.run(limit=limit)
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("dist")
@click.option("--limit", type=int, default=None, help="Limit number of products.")
def scrape_dist(limit: int | None) -> None:
    """Scrape distribution data."""
    from tiger_etf.scrapers.distribution import DistributionScraper

    console.print("[bold]Scraping distribution data...[/bold]")
    s = DistributionScraper()
    try:
        s.run(limit=limit)
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("docs")
@click.option("--limit", type=int, default=None, help="Limit number of products.")
@click.option("--no-download", is_flag=True, help="Only record metadata, skip PDF downloads.")
def scrape_docs(limit: int | None, no_download: bool) -> None:
    """Download PDF documents."""
    from tiger_etf.scrapers.documents import DocumentsScraper

    console.print("[bold]Scraping documents...[/bold]")
    s = DocumentsScraper()
    try:
        s.run(limit=limit, download=not no_download)
    finally:
        s.close()
    console.print("[green]Done.[/green]")


@scrape.command("all")
@click.option("--limit", type=int, default=None, help="Limit per-step product count.")
def scrape_all(limit: int | None) -> None:
    """Run all scrapers sequentially."""
    from tiger_etf.scrapers.distribution import DistributionScraper
    from tiger_etf.scrapers.documents import DocumentsScraper
    from tiger_etf.scrapers.holdings import HoldingsScraper
    from tiger_etf.scrapers.performance import PerformanceScraper
    from tiger_etf.scrapers.product_detail import ProductDetailScraper
    from tiger_etf.scrapers.product_list import ProductListScraper

    steps: list[tuple[str, type]] = [
        ("Product list", ProductListScraper),
        ("Product detail", ProductDetailScraper),
        ("Performance", PerformanceScraper),
        ("Holdings", HoldingsScraper),
        ("Distributions", DistributionScraper),
        ("Documents", DocumentsScraper),
    ]

    for name, cls in steps:
        console.print(f"\n[bold cyan]>>> {name}[/bold cyan]")
        s = cls()
        try:
            kwargs = {}
            if limit and name != "Product list":
                kwargs["limit"] = limit
            s.run(**kwargs)
        except Exception as e:
            console.print(f"[red]Error in {name}: {e}[/red]")
        finally:
            s.close()

    console.print("\n[green bold]All scrapers finished.[/green bold]")


# --- report commands ---


@cli.group()
def report() -> None:
    """Reporting commands."""


@report.command("summary")
def report_summary() -> None:
    """Print data collection summary."""
    from sqlalchemy import func

    from tiger_etf.db import get_session
    from tiger_etf.models import (
        EtfDailyPrice,
        EtfDistribution,
        EtfDocument,
        EtfHolding,
        EtfPerformance,
        EtfProduct,
        ScrapeRun,
    )

    with get_session() as session:
        table = Table(title="TIGER ETF Data Summary")
        table.add_column("Table", style="cyan")
        table.add_column("Rows", justify="right", style="green")

        counts = [
            ("etf_products", session.query(func.count(EtfProduct.id)).scalar()),
            ("etf_daily_prices", session.query(func.count(EtfDailyPrice.id)).scalar()),
            ("etf_holdings", session.query(func.count(EtfHolding.id)).scalar()),
            ("etf_distributions", session.query(func.count(EtfDistribution.id)).scalar()),
            ("etf_documents", session.query(func.count(EtfDocument.id)).scalar()),
            ("etf_performance", session.query(func.count(EtfPerformance.id)).scalar()),
            ("scrape_runs", session.query(func.count(ScrapeRun.id)).scalar()),
        ]
        for name, count in counts:
            table.add_row(name, str(count))

        console.print(table)

        # Recent scrape runs
        recent = (
            session.query(ScrapeRun)
            .order_by(ScrapeRun.started_at.desc())
            .limit(10)
            .all()
        )
        if recent:
            run_table = Table(title="Recent Scrape Runs")
            run_table.add_column("ID", justify="right")
            run_table.add_column("Scraper")
            run_table.add_column("Status")
            run_table.add_column("Processed", justify="right")
            run_table.add_column("Failed", justify="right")
            run_table.add_column("Started")

            for r in recent:
                status_style = {
                    "success": "green",
                    "failed": "red",
                    "running": "yellow",
                }.get(r.status, "white")
                run_table.add_row(
                    str(r.id),
                    r.scraper_name,
                    f"[{status_style}]{r.status}[/{status_style}]",
                    str(r.items_processed),
                    str(r.items_failed),
                    r.started_at.strftime("%Y-%m-%d %H:%M") if r.started_at else "-",
                )
            console.print(run_table)

        # Sample products
        samples = session.query(EtfProduct).limit(5).all()
        if samples:
            prod_table = Table(title="Sample Products")
            prod_table.add_column("Ticker")
            prod_table.add_column("Name")
            prod_table.add_column("NAV", justify="right")
            prod_table.add_column("AUM (억)", justify="right")

            for p in samples:
                prod_table.add_row(
                    p.ticker,
                    p.name_ko[:40],
                    f"{p.nav:,.0f}" if p.nav else "-",
                    f"{p.aum:,.0f}" if p.aum else "-",
                )
            console.print(prod_table)


# --- graphrag commands ---


@cli.group()
def graphrag() -> None:
    """GraphRAG (Lexical Graph) commands."""


@graphrag.command("build")
@click.option("--pdf-limit", type=int, default=None, help="Limit number of PDFs.")
@click.option("--rdb-limit", type=int, default=None, help="Limit number of RDB products.")
def graphrag_build(pdf_limit: int | None, rdb_limit: int | None) -> None:
    """Build graph index from all sources (PDF + RDB)."""
    from tiger_etf.graphrag.indexer import build_all

    console.print("[bold]Building GraphRAG index from PDFs + RDB...[/bold]")
    build_all(pdf_limit=pdf_limit, rdb_limit=rdb_limit)
    console.print("[green]Done.[/green]")


@graphrag.command("build-pdf")
@click.option("--limit", type=int, default=None, help="Limit number of PDFs.")
def graphrag_build_pdf(limit: int | None) -> None:
    """Build graph index from PDF documents only."""
    from tiger_etf.graphrag.indexer import build_from_pdfs

    console.print(f"[bold]Building GraphRAG index from PDFs (limit={limit})...[/bold]")
    build_from_pdfs(limit=limit)
    console.print("[green]Done.[/green]")


@graphrag.command("build-rdb")
@click.option("--limit", type=int, default=None, help="Limit number of RDB products.")
def graphrag_build_rdb(limit: int | None) -> None:
    """Build graph index from RDB data only."""
    from tiger_etf.graphrag.indexer import build_from_rdb

    console.print(f"[bold]Building GraphRAG index from RDB (limit={limit})...[/bold]")
    build_from_rdb(limit=limit)
    console.print("[green]Done.[/green]")


@graphrag.command("query")
@click.argument("question")
def graphrag_query(question: str) -> None:
    """Query the graph with a natural language question."""
    from tiger_etf.graphrag.query import query

    console.print(f"[bold]Query:[/bold] {question}\n")
    response = query(question)
    console.print(response)


@graphrag.command("reset")
@click.option("--graph-only", is_flag=True, help="Only reset graph store (Neptune).")
@click.option("--vector-only", is_flag=True, help="Only reset vector store (OpenSearch).")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def graphrag_reset(graph_only: bool, vector_only: bool, yes: bool) -> None:
    """Delete all data from graph and vector stores."""
    from tiger_etf.graphrag.indexer import reset_all, reset_graph, reset_vector

    if not yes:
        if graph_only:
            target = "graph store (Neptune)"
        elif vector_only:
            target = "vector store (OpenSearch)"
        else:
            target = "graph store (Neptune) and vector store (OpenSearch)"
        if not click.confirm(f"This will delete ALL data from {target}. Continue?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    if graph_only:
        console.print("[bold]Resetting graph store...[/bold]")
        count = reset_graph()
        console.print(f"[green]Graph reset complete. {count} nodes deleted.[/green]")
    elif vector_only:
        console.print("[bold]Resetting vector store...[/bold]")
        count = reset_vector()
        console.print(f"[green]Vector reset complete. {count} documents deleted.[/green]")
    else:
        console.print("[bold]Resetting graph and vector stores...[/bold]")
        result = reset_all()
        console.print(f"[green]Reset complete. Graph: {result['graph_nodes_deleted']} nodes, Vector: {result['vector_docs_deleted']} documents deleted.[/green]")


@graphrag.command("status")
def graphrag_status() -> None:
    """Show Neptune graph statistics (node/edge counts)."""
    from tiger_etf.graphrag.query import get_graph_stats

    console.print("[bold]GraphRAG Store Status[/bold]\n")
    try:
        stats = get_graph_stats()

        node_table = Table(title="Nodes")
        node_table.add_column("Label", style="cyan")
        node_table.add_column("Count", justify="right", style="green")
        for label, cnt in sorted(stats["nodes"].items()):
            node_table.add_row(label, str(cnt))
        console.print(node_table)

        edge_table = Table(title="Edges")
        edge_table.add_column("Type", style="cyan")
        edge_table.add_column("Count", justify="right", style="green")
        for etype, cnt in sorted(stats["edges"].items()):
            edge_table.add_row(etype, str(cnt))
        console.print(edge_table)
    except Exception as e:
        console.print(f"[red]Error connecting to Neptune: {e}[/red]")


# --- experiment commands ---


@cli.group()
def experiment() -> None:
    """Experiment framework for comparing GraphRAG configurations."""


@experiment.command("list")
def experiment_list() -> None:
    """List experiment configs and completed results."""
    from tiger_etf.graphrag.experiment import (
        list_configs,
        list_results,
    )

    # Configs
    configs = list_configs()
    table = Table(title="Experiment Configs")
    table.add_column("Config Name", style="cyan")
    for c in configs:
        table.add_row(c)
    console.print(table)

    # Results
    results = list_results()
    if results:
        res_table = Table(title="Completed Experiments")
        res_table.add_column("Name", style="cyan")
        res_table.add_column("LLM", style="yellow")
        res_table.add_column("Embedding", style="yellow")
        res_table.add_column("Nodes", justify="right", style="green")
        res_table.add_column("Edges", justify="right", style="green")
        res_table.add_column("Duration", justify="right")
        for r in results:
            res_table.add_row(
                r["name"],
                r["extraction_llm"].split(".")[-1][:30],
                r["embedding_model"].split(".")[-1][:20],
                f"{r['total_nodes']:,}",
                f"{r['total_edges']:,}",
                f"{r['duration_min']:.1f}m",
            )
        console.print(res_table)


@experiment.command("run")
@click.argument("config_name")
@click.option("--skip-indexing", is_flag=True, help="Skip indexing, only collect metrics.")
@click.option("--no-llm-judge", is_flag=True, help="Skip LLM-as-Judge scoring (keyword metrics only).")
def experiment_run(config_name: str, skip_indexing: bool, no_llm_judge: bool) -> None:
    """Run an experiment: configure -> index -> metrics -> eval."""
    from tiger_etf.graphrag.experiment import run_experiment

    console.print(f"[bold]Running experiment: {config_name}[/bold]")
    result = run_experiment(
        config_name,
        skip_indexing=skip_indexing,
        use_llm_judge=not no_llm_judge,
    )

    console.print(f"\n[green bold]Complete: {result['name']}[/green bold]")
    console.print(f"  Nodes: {result['metrics']['total_nodes']:,}")
    console.print(f"  Edges: {result['metrics']['total_edges']:,}")
    if "duration_minutes" in result:
        console.print(f"  Duration: {result['duration_minutes']:.1f} min")
    console.print(f"  Avg query latency: {result['avg_query_latency_seconds']:.2f}s")

    # Show evaluation scores if available
    if "evaluation" in result:
        ev = result["evaluation"]
        console.print(f"  Overall score: {ev['overall_score']:.3f}")
        console.print(f"  Keyword hit rate: {ev['keyword_hit_rate']:.1%}")
        console.print(f"  Keyword coverage: {ev['keyword_coverage']:.1%}")
        if ev.get("llm_judge", {}).get("avg_correctness", 0) > 0:
            lj = ev["llm_judge"]
            console.print(f"  Correctness: {lj['avg_correctness']:.2f}/5")
            console.print(f"  Faithfulness: {lj['avg_faithfulness']:.2f}/5")
            console.print(f"  Completeness: {lj['avg_completeness']:.2f}/5")


@experiment.command("compare")
@click.argument("names", nargs=-1)
def experiment_compare(names: tuple[str, ...]) -> None:
    """Compare experiment results. Pass names or leave empty for all."""
    import json as _json
    from pathlib import Path as _Path

    results_dir = _Path(__file__).resolve().parents[2] / "experiments" / "results"
    results = []
    for f in sorted(results_dir.glob("*.json")):
        with open(f) as fp:
            data = _json.load(fp)
        if not names or any(n in data.get("name", "") for n in names):
            results.append(data)

    if not results:
        console.print("[red]No matching results found.[/red]")
        return

    table = Table(title="Experiment Comparison")
    table.add_column("Experiment", style="cyan")
    table.add_column("Extraction LLM", style="yellow")
    table.add_column("Embedding", style="yellow")
    table.add_column("Nodes", justify="right", style="green")
    table.add_column("Edges", justify="right", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Score", justify="right", style="bold green")
    table.add_column("KW Hit", justify="right")
    table.add_column("Correct", justify="right")

    for r in results:
        cfg = r.get("config", {})
        m = r.get("metrics", {})
        ev = r.get("evaluation", {})
        lj = ev.get("llm_judge", {})
        table.add_row(
            r.get("name", "?"),
            cfg.get("extraction_llm", "?").split(".")[-1][:35],
            cfg.get("embedding_model", "?").split(".")[-1][:20],
            f"{m.get('total_nodes', 0):,}",
            f"{m.get('total_edges', 0):,}",
            f"{r.get('duration_minutes', 0):.1f}m",
            f"{r.get('avg_query_latency_seconds', 0):.2f}s",
            f"{ev.get('overall_score', 0):.3f}" if ev else "-",
            f"{ev.get('keyword_hit_rate', 0):.0%}" if ev else "-",
            f"{lj.get('avg_correctness', 0):.1f}" if lj else "-",
        )
    console.print(table)


if __name__ == "__main__":
    cli()
