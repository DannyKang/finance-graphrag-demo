-- Tiger ETF RDB Schema (reference DDL)
-- Tables are created via SQLAlchemy ORM / Alembic in production.

CREATE SCHEMA IF NOT EXISTS tiger_etf;

CREATE TABLE tiger_etf.etf_products (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) UNIQUE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    name_ko VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    benchmark_index VARCHAR(200),
    category_l1 VARCHAR(100),
    category_l2 VARCHAR(100),
    total_expense_ratio NUMERIC(8,4),
    listing_date DATE,
    currency_hedge BOOLEAN,
    creation_unit INTEGER,
    aum NUMERIC(20,2),
    nav NUMERIC(14,2),
    market_price NUMERIC(14,2),
    shares_outstanding BIGINT,
    pension_individual VARCHAR(10),
    pension_retirement VARCHAR(10),
    bloomberg_ticker VARCHAR(30),
    is_active BOOLEAN DEFAULT TRUE,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tiger_etf.etf_daily_prices (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) NOT NULL REFERENCES tiger_etf.etf_products(ksd_fund_code),
    trade_date DATE NOT NULL,
    nav NUMERIC(14,2),
    market_price NUMERIC(14,2),
    volume BIGINT,
    UNIQUE(ksd_fund_code, trade_date)
);

CREATE TABLE tiger_etf.etf_holdings (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) NOT NULL REFERENCES tiger_etf.etf_products(ksd_fund_code),
    as_of_date DATE NOT NULL,
    holding_name VARCHAR(300),
    holding_isin VARCHAR(20),
    holding_ticker VARCHAR(20),
    weight_pct NUMERIC(8,4),
    shares NUMERIC(20,4),
    market_value NUMERIC(20,2),
    UNIQUE(ksd_fund_code, as_of_date, holding_name)
);

CREATE TABLE tiger_etf.etf_distributions (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) NOT NULL REFERENCES tiger_etf.etf_products(ksd_fund_code),
    record_date DATE NOT NULL,
    payment_date DATE,
    amount_per_share NUMERIC(12,2),
    distribution_rate NUMERIC(8,4),
    UNIQUE(ksd_fund_code, record_date)
);

CREATE TABLE tiger_etf.etf_documents (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) NOT NULL REFERENCES tiger_etf.etf_products(ksd_fund_code),
    doc_type VARCHAR(50) NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT,
    file_hash VARCHAR(64),
    file_size_bytes INTEGER,
    published_date DATE,
    downloaded_at TIMESTAMPTZ,
    UNIQUE(ksd_fund_code, doc_type, source_url)
);

CREATE TABLE tiger_etf.etf_performance (
    id SERIAL PRIMARY KEY,
    ksd_fund_code VARCHAR(20) NOT NULL REFERENCES tiger_etf.etf_products(ksd_fund_code),
    as_of_date DATE NOT NULL,
    return_1w NUMERIC(8,4),
    return_1m NUMERIC(8,4),
    return_3m NUMERIC(8,4),
    return_6m NUMERIC(8,4),
    return_1y NUMERIC(8,4),
    return_3y NUMERIC(8,4),
    return_ytd NUMERIC(8,4),
    UNIQUE(ksd_fund_code, as_of_date)
);

CREATE TABLE tiger_etf.scrape_runs (
    id SERIAL PRIMARY KEY,
    scraper_name VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running',
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX idx_daily_prices_date ON tiger_etf.etf_daily_prices(trade_date);
CREATE INDEX idx_holdings_date ON tiger_etf.etf_holdings(as_of_date);
CREATE INDEX idx_documents_type ON tiger_etf.etf_documents(doc_type);
