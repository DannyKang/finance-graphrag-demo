"""Scrape ETF product list using getEtfTypeData.ajax JSON endpoint."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert

from tiger_etf.db import get_session
from tiger_etf.models import EtfProduct
from tiger_etf.scrapers.base import BaseScraper


def _safe_float(val) -> float | None:
    if val is None or val == "" or val == "-":
        return None
    try:
        v = float(str(val).replace(",", ""))
        if v == -1000:
            return None
        return v
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    if val is None or val == "" or val == "-":
        return None
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    val = val.strip().replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


class ProductListScraper(BaseScraper):
    name = "product_list"

    def _fetch_category_tree(self) -> list[dict]:
        """Get the full category hierarchy (leaf nodes only)."""
        resp = self.post(
            "/getEtfTypeDataAll.ajax",
            data={"seq": "ETF_TYPE", "lang": "ko"},
        )
        data = resp.json()
        code_list = data.get("cdDtlList", {}).get("codeList", [])

        # Build parent name lookup (seq can be str or int)
        parent_names = {}
        for item in code_list:
            parent_names[str(item.get("seq"))] = item.get("cdNm", "")

        codes = []
        for item in code_list:
            # Only leaf categories (dpth=3) that have products
            if item.get("prdctcnt", 0) > 0:
                parent_name = parent_names.get(str(item.get("parntSeq")), "")
                codes.append({
                    "code": item.get("cd"),
                    "name": item.get("cdNm"),
                    "parent_name": parent_name,
                })
        return codes

    def _fetch_products_by_category(self, category_code: str) -> list[dict]:
        """Fetch products for a specific leaf category."""
        resp = self.post(
            "/getEtfTypeData.ajax",
            data={"etfTemaType": category_code, "lang": "ko"},
        )
        data = resp.json()
        # Products are under cdDtlList.temaPrdctList
        return data.get("cdDtlList", {}).get("temaPrdctList", [])

    def run(self, **kwargs) -> None:
        run_id = self.start_run()
        processed = 0
        failed = 0

        try:
            # Fetch category tree
            categories = self._fetch_category_tree()
            self.log.info(f"Found {len(categories)} categories")

            # Collect all products (deduplicate by ksdFund)
            all_products: dict[str, dict] = {}
            category_map: dict[str, str] = {}

            for cat in categories:
                code = cat["code"]
                cat_name = cat["name"]
                parent_name = cat.get("parent_name", "")
                try:
                    products = self._fetch_products_by_category(code)
                    self.log.info(f"Category '{cat_name}' ({code}): {len(products)} products")
                    for p in products:
                        ksd = p.get("ksdFund")
                        if ksd and ksd not in all_products:
                            all_products[ksd] = p
                            category_map[ksd] = {"name": cat_name, "parent": parent_name}
                except Exception as e:
                    self.log.warning(f"Failed to fetch category {code}: {e}")

            self.log.info(f"Total unique products: {len(all_products)}")

            # Upsert into DB
            with get_session() as session:
                for ksd_fund, raw in all_products.items():
                    try:
                        ticker = raw.get("jongCode", "")
                        name_ko = raw.get("jongName", "")
                        if not ticker or not name_ko:
                            continue

                        cat_info = category_map.get(ksd_fund, {})
                        category_l1 = cat_info.get("parent") if isinstance(cat_info, dict) else None
                        category_l2 = cat_info.get("name") if isinstance(cat_info, dict) else None

                        # Parse commission: e.g. "연 0.29&" -> 0.29
                        commission_raw = raw.get("commission", "")
                        commission = _safe_float(
                            str(commission_raw)
                            .replace("연", "")
                            .replace("&", "")
                            .replace("#", "")
                            .replace("%", "")
                            .strip()
                        ) if commission_raw else None

                        # Unescape HTML entities in name
                        name_ko = name_ko.replace("&amp;", "&")

                        values = {
                            "ksd_fund_code": ksd_fund,
                            "ticker": ticker,
                            "name_ko": name_ko,
                            "benchmark_index": raw.get("bmNm"),
                            "category_l1": category_l1,
                            "category_l2": category_l2,
                            "total_expense_ratio": commission,
                            "listing_date": _parse_date(raw.get("publicDate")),
                            # netamt is in raw KRW, convert to 억원
                            "aum": round(_safe_float(raw.get("netamt")) / 1_0000_0000, 2)
                            if _safe_float(raw.get("netamt")) is not None
                            else None,
                            "nav": _safe_float(raw.get("nav")),
                            "market_price": _safe_float(raw.get("price") or raw.get("prc")),
                            "is_active": True,
                            "raw_data": raw,
                        }

                        stmt = insert(EtfProduct).values(**values)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["ksd_fund_code"],
                            set_={
                                k: v
                                for k, v in values.items()
                                if k != "ksd_fund_code"
                            },
                        )
                        session.execute(stmt)
                        processed += 1
                    except Exception as e:
                        self.log.warning(f"Failed to upsert {ksd_fund}: {e}")
                        failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Product list scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
