"""Parse ETF product list HTML fragments."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from tiger_etf.scrapers.product_list import _parse_date, _safe_float


def parse_product_cards(html: str) -> list[dict]:
    """Parse product cards from the search list HTML."""
    soup = BeautifulSoup(html, "lxml")
    products = []

    # Product cards in the search result
    for card in soup.select(".product-summary, .etf-item, li[data-ksd-fund]"):
        product = {}

        # KSD fund code
        ksd = card.get("data-ksd-fund") or card.get("data-ksdfund")
        if not ksd:
            link = card.select_one("a[href*='ksdFund']")
            if link:
                match = re.search(r"ksdFund=(\w+)", link.get("href", ""))
                if match:
                    ksd = match.group(1)
        if not ksd:
            continue
        product["ksd_fund_code"] = ksd

        # Name
        name_el = card.select_one(".title, .etf-name, .name")
        if name_el:
            product["name_ko"] = name_el.get_text(strip=True)

        # Ticker
        code_el = card.select_one(".code, .ticker, .jong-code")
        if code_el:
            product["ticker"] = code_el.get_text(strip=True)

        # Category
        cat_el = card.select_one(".category, .cate")
        if cat_el:
            product["category"] = cat_el.get_text(strip=True)

        # Price / NAV
        for cls in [".price", ".nav", ".prc"]:
            el = card.select_one(cls)
            if el:
                val = _safe_float(el.get_text(strip=True))
                if val:
                    product[cls.strip(".")] = val

        products.append(product)

    return products


def parse_closing_price_table(html: str) -> list[dict]:
    """Parse the closing price HTML table (from closing-price/list.ajax)."""
    soup = BeautifulSoup(html, "lxml")
    rows = []

    for tr in soup.select("tr"):
        cells = tr.select("td")
        if len(cells) < 4:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Try to extract: No | Date | Code | Name | Closing Price | ...
        row = {}
        for t in texts:
            if re.match(r"\d{8}", t):
                row["trade_date"] = _parse_date(t)
            elif re.match(r"\d{6}", t) and len(t) == 6:
                row["ticker"] = t
            elif re.match(r"KR\d{10}", t):
                row["ksd_fund_code"] = t

        # Get numeric values for price/volume
        nums = [_safe_float(t) for t in texts]
        nums = [n for n in nums if n is not None]
        if len(nums) >= 1:
            row["market_price"] = nums[0] if nums else None
        if len(nums) >= 2:
            row["volume"] = int(nums[1]) if nums[1] else None

        if row.get("ksd_fund_code") or row.get("ticker"):
            rows.append(row)

    return rows
