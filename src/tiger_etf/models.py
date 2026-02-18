from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EtfProduct(Base):
    __tablename__ = "etf_products"
    __table_args__ = {"schema": "tiger_etf"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name_ko: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(200))
    benchmark_index: Mapped[Optional[str]] = mapped_column(String(200))
    category_l1: Mapped[Optional[str]] = mapped_column(String(100))
    category_l2: Mapped[Optional[str]] = mapped_column(String(100))
    total_expense_ratio: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    listing_date: Mapped[Optional[date]] = mapped_column(Date)
    currency_hedge: Mapped[Optional[bool]] = mapped_column(Boolean)
    creation_unit: Mapped[Optional[int]] = mapped_column(Integer)
    aum: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    nav: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    market_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    shares_outstanding: Mapped[Optional[int]] = mapped_column(BigInteger)
    pension_individual: Mapped[Optional[str]] = mapped_column(String(10))
    pension_retirement: Mapped[Optional[str]] = mapped_column(String(10))
    bloomberg_ticker: Mapped[Optional[str]] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    daily_prices: Mapped[List["EtfDailyPrice"]] = relationship(back_populates="product")
    holdings: Mapped[List["EtfHolding"]] = relationship(back_populates="product")
    distributions: Mapped[List["EtfDistribution"]] = relationship(back_populates="product")
    documents: Mapped[List["EtfDocument"]] = relationship(back_populates="product")
    performance: Mapped[List["EtfPerformance"]] = relationship(back_populates="product")


class EtfDailyPrice(Base):
    __tablename__ = "etf_daily_prices"
    __table_args__ = (
        UniqueConstraint("ksd_fund_code", "trade_date"),
        Index("idx_daily_prices_date", "trade_date"),
        {"schema": "tiger_etf"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("tiger_etf.etf_products.ksd_fund_code"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    market_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)

    product: Mapped["EtfProduct"] = relationship(back_populates="daily_prices")


class EtfHolding(Base):
    __tablename__ = "etf_holdings"
    __table_args__ = (
        UniqueConstraint("ksd_fund_code", "as_of_date", "holding_name"),
        Index("idx_holdings_date", "as_of_date"),
        {"schema": "tiger_etf"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("tiger_etf.etf_products.ksd_fund_code"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    holding_name: Mapped[Optional[str]] = mapped_column(String(300))
    holding_isin: Mapped[Optional[str]] = mapped_column(String(20))
    holding_ticker: Mapped[Optional[str]] = mapped_column(String(20))
    weight_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    shares: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    market_value: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))

    product: Mapped["EtfProduct"] = relationship(back_populates="holdings")


class EtfDistribution(Base):
    __tablename__ = "etf_distributions"
    __table_args__ = (
        UniqueConstraint("ksd_fund_code", "record_date"),
        {"schema": "tiger_etf"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("tiger_etf.etf_products.ksd_fund_code"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_date: Mapped[Optional[date]] = mapped_column(Date)
    amount_per_share: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    distribution_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))

    product: Mapped["EtfProduct"] = relationship(back_populates="distributions")


class EtfDocument(Base):
    __tablename__ = "etf_documents"
    __table_args__ = (
        UniqueConstraint("ksd_fund_code", "doc_type", "source_url"),
        Index("idx_documents_type", "doc_type"),
        {"schema": "tiger_etf"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("tiger_etf.etf_products.ksd_fund_code"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(Text)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    published_date: Mapped[Optional[date]] = mapped_column(Date)
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    product: Mapped["EtfProduct"] = relationship(back_populates="documents")


class EtfPerformance(Base):
    __tablename__ = "etf_performance"
    __table_args__ = (
        UniqueConstraint("ksd_fund_code", "as_of_date"),
        {"schema": "tiger_etf"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ksd_fund_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("tiger_etf.etf_products.ksd_fund_code"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_1w: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_1m: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_3m: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_6m: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_1y: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_3y: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    return_ytd: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))

    product: Mapped["EtfProduct"] = relationship(back_populates="performance")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    __table_args__ = {"schema": "tiger_etf"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scraper_name: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
