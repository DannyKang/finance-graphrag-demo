"""Scrape ETF distribution (dividend) data."""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert

from tiger_etf.db import get_session
from tiger_etf.models import EtfDistribution
from tiger_etf.scrapers.base import BaseScraper
from tiger_etf.scrapers.product_list import _safe_float


class DistributionScraper(BaseScraper):
    name = "distribution"

    def _fetch_annual_list(self) -> str:
        """Fetch the annual distribution list (HTML table with all ETFs)."""
        resp = self.get("/ko/distribution/annual/list.ajax")
        return resp.text

    def _fetch_detail_distributions(self, ksd_fund_code: str) -> str:
        """Fetch per-ETF distribution detail."""
        resp = self.post(
            "/ko/product/search/detail/refDivAjax.ajax",
            data={"ksdFund": ksd_fund_code},
        )
        return resp.text

    def _parse_annual_list(self, html: str) -> list[dict]:
        """Parse the annual distribution HTML table."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        rows = soup.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            texts = [c.get_text(strip=True) for c in cells]

            # Try to find the row pattern: No | Name(ticker) | ksdFund | year columns...
            # The ksdFund is sometimes in a hidden element or data attribute
            ksd_fund = None
            a_tag = row.select_one("a[href*='ksdFund'], a[onclick*='ksdFund']")
            if a_tag:
                href = a_tag.get("href", "") + a_tag.get("onclick", "")
                match = re.search(r"ksdFund[=:]\s*['\"]?(KR\w+)", href)
                if match:
                    ksd_fund = match.group(1)

            # Also check data attributes
            if not ksd_fund:
                for el in row.select("[data-ksd-fund], [data-ksdfund]"):
                    ksd_fund = el.get("data-ksd-fund") or el.get("data-ksdfund")
                    if ksd_fund:
                        break

            # Try to find ISIN-like code in cell text
            if not ksd_fund:
                for t in texts:
                    if re.match(r"KR\d{10}", t):
                        ksd_fund = t
                        break

            if not ksd_fund:
                continue

            # Parse year-based distribution amounts from remaining cells
            # The table has columns for each year's distribution amount
            for i, text in enumerate(texts):
                amount = _safe_float(text)
                if amount is not None and amount > 0:
                    results.append({
                        "ksd_fund_code": ksd_fund,
                        "amount": amount,
                        "cell_index": i,
                    })

        return results

    def _parse_detail_distributions(self, html: str, ksd_fund_code: str) -> list[dict]:
        """Parse per-ETF distribution detail HTML."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        rows = soup.select("table tbody tr, tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue

            texts = [c.get_text(strip=True) for c in cells]

            record_date = None
            payment_date = None
            amount = None
            rate = None

            for t in texts:
                # Try to parse dates
                t_clean = t.replace(".", "-").replace("/", "-")
                for fmt in ("%Y-%m-%d", "%Y%m%d"):
                    try:
                        d = datetime.strptime(t_clean[:10], fmt).date()
                        if record_date is None:
                            record_date = d
                        elif payment_date is None:
                            payment_date = d
                        break
                    except ValueError:
                        continue

                # Try to parse amounts
                v = _safe_float(t)
                if v is not None and v > 0:
                    if amount is None:
                        amount = v
                    elif rate is None and v < 100:
                        rate = v

            if record_date and amount:
                results.append({
                    "ksd_fund_code": ksd_fund_code,
                    "record_date": record_date,
                    "payment_date": payment_date,
                    "amount_per_share": amount,
                    "distribution_rate": rate,
                })

        return results

    def run(self, limit: int | None = None, **kwargs) -> None:
        run_id = self.start_run()
        processed = 0
        failed = 0

        try:
            # Fetch per-ETF distribution details
            from tiger_etf.models import EtfProduct

            with get_session() as session:
                query = session.query(EtfProduct).filter(EtfProduct.is_active.is_(True))
                if limit:
                    query = query.limit(limit)
                products = query.all()

            self.log.info(f"Fetching distributions for {len(products)} products")

            for product in products:
                ksd = product.ksd_fund_code
                try:
                    html = self._fetch_detail_distributions(ksd)
                    dists = self._parse_detail_distributions(html, ksd)

                    if dists:
                        with get_session() as session:
                            for d in dists:
                                values = {
                                    "ksd_fund_code": d["ksd_fund_code"],
                                    "record_date": d["record_date"],
                                    "payment_date": d.get("payment_date"),
                                    "amount_per_share": d.get("amount_per_share"),
                                    "distribution_rate": d.get("distribution_rate"),
                                }
                                stmt = insert(EtfDistribution).values(**values)
                                stmt = stmt.on_conflict_do_update(
                                    constraint="etf_distributions_ksd_fund_code_record_date_key",
                                    set_={
                                        "payment_date": values["payment_date"],
                                        "amount_per_share": values["amount_per_share"],
                                        "distribution_rate": values["distribution_rate"],
                                    },
                                )
                                session.execute(stmt)

                        self.log.debug(f"{ksd}: {len(dists)} distributions")

                    processed += 1
                except Exception as e:
                    self.log.warning(f"Failed dist for {ksd}: {e}")
                    failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Distribution scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
