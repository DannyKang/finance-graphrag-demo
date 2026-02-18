"""Scrape ETF product detail pages to enrich etf_products with additional fields."""

from __future__ import annotations

from bs4 import BeautifulSoup

from tiger_etf.db import get_session
from tiger_etf.models import EtfProduct
from tiger_etf.scrapers.base import BaseScraper
from tiger_etf.scrapers.product_list import _parse_date, _safe_float, _safe_int


class ProductDetailScraper(BaseScraper):
    name = "product_detail"

    def _fetch_detail_page(self, ksd_fund_code: str) -> str:
        resp = self.get(
            "/ko/product/search/detail/index.do",
            params={"ksdFund": ksd_fund_code},
        )
        return resp.text

    def _parse_detail(self, html: str, ksd_fund_code: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {}

        # Extract text by looking for labels and their siblings/next elements
        def find_value(label_text: str) -> str | None:
            for el in soup.find_all(string=lambda t: t and label_text in t):
                parent = el.find_parent(["dt", "th", "span", "div", "li"])
                if parent:
                    sibling = parent.find_next_sibling(["dd", "td", "span", "div"])
                    if sibling:
                        return sibling.get_text(strip=True)
            return None

        # English name
        name_en_el = soup.select_one(".detail-title .en, .product-name .en, .eng-name")
        if name_en_el:
            data["name_en"] = name_en_el.get_text(strip=True)

        # Benchmark index
        bm = find_value("기초지수") or find_value("벤치마크") or find_value("추적지수")
        if bm:
            data["benchmark_index"] = bm

        # Total expense ratio
        ter = find_value("총보수")
        if ter:
            data["total_expense_ratio"] = _safe_float(ter.replace("%", "").strip())

        # Listing date
        ld = find_value("상장일")
        if ld:
            data["listing_date"] = _parse_date(ld)

        # AUM (순자산총액)
        aum_text = find_value("순자산")
        if aum_text:
            data["aum"] = _safe_float(aum_text.replace("억원", "").replace("원", "").strip())

        # Shares outstanding
        shares = find_value("상장좌수") or find_value("설정좌수")
        if shares:
            data["shares_outstanding"] = _safe_int(shares.replace("좌", "").strip())

        # Creation unit
        cu = find_value("CU")
        if cu:
            data["creation_unit"] = _safe_int(cu.replace("좌", "").strip())

        # Currency hedge
        hedge_text = find_value("환헤지")
        if hedge_text:
            data["currency_hedge"] = "환헤지" in hedge_text and "미" not in hedge_text

        # Pension eligibility
        pension_ind = find_value("개인연금")
        if pension_ind:
            data["pension_individual"] = pension_ind.strip()
        pension_ret = find_value("퇴직연금")
        if pension_ret:
            data["pension_retirement"] = pension_ret.strip()

        # Bloomberg ticker
        bb = find_value("Bloomberg") or find_value("블룸버그")
        if bb:
            data["bloomberg_ticker"] = bb.strip()

        return data

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

            self.log.info(f"Fetching details for {len(products)} products")

            for product in products:
                ksd = product.ksd_fund_code
                try:
                    html = self._fetch_detail_page(ksd)
                    detail = self._parse_detail(html, ksd)

                    if detail:
                        with get_session() as session:
                            p = session.query(EtfProduct).filter_by(ksd_fund_code=ksd).first()
                            if p:
                                for key, val in detail.items():
                                    if val is not None:
                                        setattr(p, key, val)
                        processed += 1
                        self.log.debug(f"Updated {ksd}: {list(detail.keys())}")
                    else:
                        processed += 1

                except Exception as e:
                    self.log.warning(f"Failed to scrape detail for {ksd}: {e}")
                    failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Product detail scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
