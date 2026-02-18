"""Parse ETF product detail HTML pages."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from tiger_etf.scrapers.product_list import _parse_date, _safe_float, _safe_int


def parse_detail_page(html: str) -> dict:
    """Extract structured data from an ETF detail page."""
    soup = BeautifulSoup(html, "lxml")
    data = {}

    def find_value_by_label(label: str) -> str | None:
        """Find value text next to a label element."""
        for el in soup.find_all(string=lambda t: t and label in t):
            parent = el.find_parent(["dt", "th", "span", "div", "label", "li"])
            if parent:
                sibling = parent.find_next_sibling(["dd", "td", "span", "div"])
                if sibling:
                    return sibling.get_text(strip=True)
        return None

    # Product name (Korean)
    title_el = soup.select_one(
        ".detail-title .ko, .product-name .ko, h2.title, .etf-detail-name"
    )
    if title_el:
        data["name_ko"] = title_el.get_text(strip=True)

    # Product name (English)
    en_el = soup.select_one(".detail-title .en, .product-name .en, .eng-name")
    if en_el:
        data["name_en"] = en_el.get_text(strip=True)

    # Key fields
    field_map = {
        "기초지수": "benchmark_index",
        "추적지수": "benchmark_index",
        "벤치마크": "benchmark_index",
        "총보수": "total_expense_ratio",
        "상장일": "listing_date",
        "순자산": "aum",
        "순자산총액": "aum",
        "상장좌수": "shares_outstanding",
        "설정좌수": "shares_outstanding",
        "CU": "creation_unit",
        "환헤지": "currency_hedge",
        "개인연금": "pension_individual",
        "퇴직연금": "pension_retirement",
        "Bloomberg": "bloomberg_ticker",
        "블룸버그": "bloomberg_ticker",
    }

    for label, key in field_map.items():
        val = find_value_by_label(label)
        if val is None:
            continue

        if key == "total_expense_ratio":
            data[key] = _safe_float(val.replace("%", "").strip())
        elif key == "listing_date":
            data[key] = _parse_date(val)
        elif key == "aum":
            data[key] = _safe_float(
                val.replace("억원", "").replace("원", "").replace("백만원", "").strip()
            )
        elif key in ("shares_outstanding", "creation_unit"):
            data[key] = _safe_int(val.replace("좌", "").replace("주", "").strip())
        elif key == "currency_hedge":
            data[key] = "환헤지" in val and "미" not in val
        elif key in ("pension_individual", "pension_retirement"):
            data[key] = val.strip()
        else:
            data[key] = val.strip()

    # Extract KSD fund code from page content
    ksd_match = re.search(r"KR\d{10}", html)
    if ksd_match:
        data["ksd_fund_code"] = ksd_match.group(0)

    return data
