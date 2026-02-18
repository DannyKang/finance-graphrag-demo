"""Scrape ETF performance data using JSON profit-list API."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert

from tiger_etf.db import get_session
from tiger_etf.models import EtfPerformance, EtfProduct
from tiger_etf.scrapers.base import BaseScraper
from tiger_etf.scrapers.product_list import _safe_float


class PerformanceScraper(BaseScraper):
    name = "performance"

    def _fetch_performance(self, ksd_fund_code: str) -> list[dict]:
        """Fetch profit time series for one ETF."""
        resp = self.post(
            "/ko/product/chart/prdct-profit-list.ajax",
            data={"ksdFund": ksd_fund_code},
        )
        data = resp.json()
        return data.get("rtnData", [])

    def _fetch_period_returns(self, ksd_fund_code: str) -> dict | None:
        """Fetch period returns (1W, 1M, 3M, etc.) from the product list data."""
        # We use the getEtfTypeData which already has period returns
        # This is called per-product from the stored raw_data
        return None

    def run(self, limit: int | None = None, **kwargs) -> None:
        run_id = self.start_run()
        processed = 0
        failed = 0

        try:
            with get_session() as session:
                query = session.query(EtfProduct).filter(EtfProduct.is_active.is_(True))
                if limit:
                    query = query.limit(limit)
                products = query.all()

            self.log.info(f"Fetching performance for {len(products)} products")

            today = date.today()

            with get_session() as session:
                for product in products:
                    ksd = product.ksd_fund_code
                    try:
                        # Extract period returns from raw_data (already fetched by product_list)
                        raw = product.raw_data or {}
                        returns = {
                            "return_1w": _safe_float(raw.get("week01")),
                            "return_1m": _safe_float(raw.get("month01")),
                            "return_3m": _safe_float(raw.get("month03")),
                            "return_6m": _safe_float(raw.get("month06")),
                            "return_1y": _safe_float(raw.get("year01")),
                            "return_3y": _safe_float(raw.get("year03")),
                            "return_ytd": _safe_float(raw.get("thisyear")),
                        }

                        # Only insert if we have at least one return value
                        if any(v is not None for v in returns.values()):
                            values = {
                                "ksd_fund_code": ksd,
                                "as_of_date": today,
                                **returns,
                            }

                            stmt = insert(EtfPerformance).values(**values)
                            stmt = stmt.on_conflict_do_update(
                                constraint="etf_performance_ksd_fund_code_as_of_date_key",
                                set_=returns,
                            )
                            session.execute(stmt)
                            processed += 1
                        else:
                            processed += 1

                    except Exception as e:
                        self.log.warning(f"Failed perf for {ksd}: {e}")
                        failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Performance scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
