"""Load PDF files and RDB data into LlamaIndex Documents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from llama_index.core.schema import Document
from llama_index.readers.file import PyMuPDFReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from tiger_etf.config import settings
from tiger_etf.db import get_session
from tiger_etf.models import EtfDistribution, EtfHolding, EtfProduct

logger = logging.getLogger(__name__)


def load_pdfs(limit: Optional[int] = None) -> list[Document]:
    """Load PDF files from data/pdfs/ into LlamaIndex Documents.

    Each PDF is tagged with metadata extracted from its filename:
      {ksd_fund_code}_{doc_type}_{hash}.pdf
    """
    pdf_dir = settings.pdfs_dir
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if limit:
        pdf_files = pdf_files[:limit]

    logger.info("Loading %d PDF files from %s", len(pdf_files), pdf_dir)

    reader = PyMuPDFReader()
    documents: list[Document] = []

    # Build a mapping of ksd_fund_code -> ticker for metadata enrichment
    ticker_map = _build_ticker_map()

    for pdf_path in pdf_files:
        meta = _parse_pdf_filename(pdf_path, ticker_map)
        try:
            docs = reader.load_data(file_path=pdf_path)
            for doc in docs:
                doc.metadata.update(meta)
            documents.extend(docs)
        except Exception:
            logger.warning("Failed to load PDF: %s", pdf_path.name, exc_info=True)

    logger.info("Loaded %d documents from %d PDFs", len(documents), len(pdf_files))
    return documents


def load_rdb(limit: Optional[int] = None) -> list[Document]:
    """Load ETF product data from RDB into LlamaIndex Documents.

    Converts structured RDB rows into natural-language text documents
    so the graph extraction LLM can process them.
    """
    documents: list[Document] = []

    with get_session() as session:
        query = select(EtfProduct).order_by(EtfProduct.id)
        if limit:
            query = query.limit(limit)
        products = session.execute(query).scalars().all()

        for product in products:
            doc = _product_to_document(session, product)
            documents.append(doc)

    logger.info("Loaded %d RDB documents", len(documents))
    return documents


def _build_ticker_map() -> dict[str, str]:
    """Build ksd_fund_code -> ticker mapping from RDB."""
    ticker_map: dict[str, str] = {}
    try:
        with get_session() as session:
            rows = session.execute(
                select(EtfProduct.ksd_fund_code, EtfProduct.ticker)
            ).all()
            for code, ticker in rows:
                ticker_map[code] = ticker
    except Exception:
        logger.warning("Could not build ticker map from RDB", exc_info=True)
    return ticker_map


def _parse_pdf_filename(pdf_path: Path, ticker_map: dict[str, str]) -> dict:
    """Extract metadata from PDF filename pattern: {ksd_fund_code}_{doc_type}_{hash}.pdf"""
    stem = pdf_path.stem
    parts = stem.split("_")
    meta = {"source": str(pdf_path), "file_name": pdf_path.name}

    if len(parts) >= 3:
        ksd_fund_code = parts[0]
        doc_type = "_".join(parts[1:-1])  # handle doc_type with underscores
        meta["ksd_fund_code"] = ksd_fund_code
        meta["doc_type"] = doc_type
        if ksd_fund_code in ticker_map:
            meta["ticker"] = ticker_map[ksd_fund_code]

    return meta


def _product_to_document(session: Session, product: EtfProduct) -> Document:
    """Convert an EtfProduct row (with related data) into a text Document."""
    lines = [
        f"ETF 상품명: {product.name_ko}",
        f"티커: {product.ticker}",
        f"KSD 펀드코드: {product.ksd_fund_code}",
    ]

    if product.benchmark_index:
        lines.append(f"벤치마크 지수: {product.benchmark_index}")
    if product.category_l1:
        lines.append(f"대분류: {product.category_l1}")
    if product.category_l2:
        lines.append(f"소분류: {product.category_l2}")
    if product.total_expense_ratio is not None:
        lines.append(f"총보수: {product.total_expense_ratio}%")
    if product.listing_date:
        lines.append(f"상장일: {product.listing_date}")
    if product.aum is not None:
        lines.append(f"순자산총액(AUM): {product.aum:,.0f} 원")
    if product.nav is not None:
        lines.append(f"기준가(NAV): {product.nav:,.0f} 원")
    if product.currency_hedge is not None:
        lines.append(f"환헤지: {'예' if product.currency_hedge else '아니오'}")

    # Top holdings
    holdings = (
        session.query(EtfHolding)
        .filter(EtfHolding.ksd_fund_code == product.ksd_fund_code)
        .order_by(EtfHolding.as_of_date.desc(), EtfHolding.weight_pct.desc())
        .limit(20)
        .all()
    )
    if holdings:
        lines.append("\n주요 보유종목:")
        for h in holdings:
            weight = f"{h.weight_pct}%" if h.weight_pct is not None else "N/A"
            lines.append(f"  - {h.holding_name} ({weight})")

    # Recent distributions
    dists = (
        session.query(EtfDistribution)
        .filter(EtfDistribution.ksd_fund_code == product.ksd_fund_code)
        .order_by(EtfDistribution.record_date.desc())
        .limit(5)
        .all()
    )
    if dists:
        lines.append("\n최근 분배금:")
        for d in dists:
            amt = f"{d.amount_per_share:,.0f}원" if d.amount_per_share else "N/A"
            lines.append(f"  - {d.record_date}: {amt}")

    text = "\n".join(lines)

    return Document(
        text=text,
        metadata={
            "source": "rdb",
            "ksd_fund_code": product.ksd_fund_code,
            "ticker": product.ticker,
            "name_ko": product.name_ko,
        },
    )
