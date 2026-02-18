"""Scrape ETF holdings data from Excel download endpoint."""

from __future__ import annotations

from datetime import date

import xlrd
from sqlalchemy.dialects.postgresql import insert

from tiger_etf.config import settings
from tiger_etf.db import get_session
from tiger_etf.models import EtfHolding, EtfProduct
from tiger_etf.scrapers.base import BaseScraper
from tiger_etf.scrapers.product_list import _safe_float


class HoldingsScraper(BaseScraper):
    name = "holdings"

    def _download_all_holdings_excel(self) -> bytes:
        """Download the bulk Excel file containing all ETF holdings.

        The English endpoint returns a single XLS file with one sheet per ETF.
        Each sheet is named by ticker code and has columns:
        Code, Name, Share/CU, Weighting.
        """
        resp = self.post(
            "/en/product/search/downloadPdfExcelTotal.do",
            data={},
        )
        return resp.content

    def _parse_excel(self, content: bytes, ticker_to_ksd: dict) -> dict:
        """Parse Excel workbook into holdings per ksd_fund_code.

        Returns dict: ksd_fund_code -> list[dict]
        """
        wb = xlrd.open_workbook(file_contents=content)
        all_holdings = {}

        for sheet in wb.sheets():
            sheet_name = sheet.name.strip()
            ksd = ticker_to_ksd.get(sheet_name)
            if not ksd:
                continue

            holdings = []
            for i in range(1, sheet.nrows):  # skip header row
                row = sheet.row_values(i)
                if len(row) < 4:
                    continue

                code = str(row[0]).strip()
                name = str(row[1]).strip()
                shares_str = str(row[2]).strip()
                weight_str = str(row[3]).strip()

                if not name and not code:
                    continue

                # Parse shares (may have commas)
                shares = _safe_float(shares_str)

                # Parse weight
                weight = _safe_float(weight_str)

                # Determine if code looks like an ISIN or ticker
                holding_isin = None
                holding_ticker = None
                if len(code) == 12 and code[:2].isalpha():
                    holding_isin = code
                elif code and code != "0":
                    holding_ticker = code

                holding_name = name if name else (code if code != "0" else None)
                if not holding_name:
                    continue

                holdings.append({
                    "holding_name": holding_name,
                    "holding_isin": holding_isin,
                    "holding_ticker": holding_ticker,
                    "weight_pct": weight,
                    "shares": shares,
                })

            if holdings:
                all_holdings[ksd] = holdings

        return all_holdings

    def run(self, limit: int | None = None, **kwargs) -> None:
        run_id = self.start_run()
        processed = 0
        failed = 0

        try:
            # Build ticker -> ksd_fund_code mapping
            with get_session() as session:
                query = session.query(EtfProduct).filter(EtfProduct.is_active.is_(True))
                if limit:
                    query = query.limit(limit)
                products = query.all()

            ticker_to_ksd = {p.ticker: p.ksd_fund_code for p in products}
            target_ksds = set(ticker_to_ksd.values()) if limit else None

            self.log.info("Downloading bulk holdings Excel...")
            content = self._download_all_holdings_excel()

            # Save the raw file
            fpath = settings.excel_dir / "AllPDF.xls"
            fpath.write_bytes(content)
            self.log.info(f"Saved Excel ({len(content)} bytes): {fpath}")

            # Parse
            self.log.info("Parsing Excel...")
            all_holdings = self._parse_excel(content, ticker_to_ksd)
            self.log.info(f"Parsed holdings for {len(all_holdings)} ETFs")

            today = date.today()

            # Upsert
            with get_session() as session:
                for ksd, holdings in all_holdings.items():
                    if target_ksds and ksd not in target_ksds:
                        continue
                    try:
                        for h in holdings:
                            values = {
                                "ksd_fund_code": ksd,
                                "as_of_date": today,
                                "holding_name": h["holding_name"],
                                "holding_isin": h.get("holding_isin"),
                                "holding_ticker": h.get("holding_ticker"),
                                "weight_pct": h.get("weight_pct"),
                                "shares": h.get("shares"),
                                "market_value": None,
                            }
                            stmt = insert(EtfHolding).values(**values)
                            stmt = stmt.on_conflict_do_update(
                                constraint="etf_holdings_ksd_fund_code_as_of_date_holding_name_key",
                                set_={
                                    "holding_isin": values["holding_isin"],
                                    "holding_ticker": values["holding_ticker"],
                                    "weight_pct": values["weight_pct"],
                                    "shares": values["shares"],
                                },
                            )
                            session.execute(stmt)
                        processed += 1
                    except Exception as e:
                        self.log.warning(f"Failed holdings for {ksd}: {e}")
                        failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Holdings scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
