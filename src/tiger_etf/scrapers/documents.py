"""Download ETF PDF documents (prospectus, factsheets, etc.)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert

from tiger_etf.config import settings
from tiger_etf.db import get_session
from tiger_etf.models import EtfDocument, EtfProduct
from tiger_etf.scrapers.base import BaseScraper


# Map Korean doc type labels to normalized type codes
DOC_TYPE_MAP = {
    "간이투자설명서": "simple_prospectus",
    "투자설명서": "prospectus",
    "집합투자규약": "rules",
    "자산운용보고서": "monthly_report",
    "월간운용보고서": "monthly_report",
    "팩트시트": "factsheet",
    "Factsheet": "factsheet",
    "FactSheet": "factsheet",
    "Prospectus": "prospectus",
}


class DocumentsScraper(BaseScraper):
    name = "documents"

    def _fetch_reference_list(self) -> str:
        """Fetch the reference page that lists all ETFs with doc links."""
        resp = self.get("/ko/reference/list.ajax")
        return resp.text

    def _fetch_detail_page(self, ksd_fund_code: str) -> str:
        """Fetch detail page to find document links."""
        resp = self.get(
            "/ko/product/search/detail/index.do",
            params={"ksdFund": ksd_fund_code},
        )
        return resp.text

    def _extract_pdf_links(self, html: str, ksd_fund_code: str) -> list[dict]:
        """Extract PDF links from a detail page or reference list."""
        soup = BeautifulSoup(html, "lxml")
        docs = []

        # Find all PDF links
        for a in soup.select("a[href*='.pdf'], a[onclick*='.pdf']"):
            href = a.get("href", "")
            onclick = a.get("onclick", "")
            label = a.get_text(strip=True)

            url = None
            if ".pdf" in href:
                url = href
            elif ".pdf" in onclick:
                match = re.search(r"['\"]([^'\"]*\.pdf[^'\"]*)['\"]", onclick)
                if match:
                    url = match.group(1)

            if not url:
                continue

            # Strip jsessionid from URL
            url = re.sub(r";jsessionid=[^?#]*", "", url)

            # Normalize URL
            if url.startswith("/"):
                # Use domain root, not base_url (which includes /tigeretf)
                domain = settings.base_url.split("/tigeretf")[0]
                url = f"{domain}{url}"
            elif not url.startswith("http"):
                url = f"{settings.base_url}/{url}"

            # Determine doc type from label
            doc_type = "other"
            for label_text, dtype in DOC_TYPE_MAP.items():
                if label_text in label:
                    doc_type = dtype
                    break

            docs.append({
                "ksd_fund_code": ksd_fund_code,
                "doc_type": doc_type,
                "source_url": url,
                "label": label,
            })

        # Also look for download buttons with data attributes
        for el in soup.select("[data-file-url], [data-pdf-url]"):
            url = el.get("data-file-url") or el.get("data-pdf-url")
            if url and ".pdf" in url:
                url = re.sub(r";jsessionid=[^?#]*", "", url)
                if url.startswith("/"):
                    domain = settings.base_url.split("/tigeretf")[0]
                    url = f"{domain}{url}"
                label = el.get_text(strip=True)
                doc_type = "other"
                for label_text, dtype in DOC_TYPE_MAP.items():
                    if label_text in label:
                        doc_type = dtype
                        break
                docs.append({
                    "ksd_fund_code": ksd_fund_code,
                    "doc_type": doc_type,
                    "source_url": url,
                    "label": label,
                })

        return docs

    def _download_pdf(self, url: str, ksd_fund_code: str, doc_type: str) -> dict | None:
        """Download a PDF and return file metadata."""
        try:
            resp = self.get(url)
            content = resp.content

            if len(content) < 1000:
                self.log.debug(f"Skipping tiny response ({len(content)}b) for {url}")
                return None

            file_hash = hashlib.sha256(content).hexdigest()
            # Create a safe filename
            fname = f"{ksd_fund_code}_{doc_type}_{file_hash[:8]}.pdf"
            fpath = settings.pdfs_dir / fname
            fpath.write_bytes(content)

            return {
                "local_path": str(fpath),
                "file_hash": file_hash,
                "file_size_bytes": len(content),
                "downloaded_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            self.log.warning(f"PDF download failed: {url} - {e}")
            return None

    def run(self, limit: int | None = None, download: bool = True, **kwargs) -> None:
        run_id = self.start_run()
        processed = 0
        failed = 0

        try:
            with get_session() as session:
                query = session.query(EtfProduct).filter(EtfProduct.is_active.is_(True))
                if limit:
                    query = query.limit(limit)
                products = query.all()

            self.log.info(f"Scanning documents for {len(products)} products")

            for product in products:
                ksd = product.ksd_fund_code
                try:
                    html = self._fetch_detail_page(ksd)
                    pdf_links = self._extract_pdf_links(html, ksd)

                    if pdf_links:
                        for doc in pdf_links:
                            meta = {}
                            if download:
                                dl_result = self._download_pdf(
                                    doc["source_url"], ksd, doc["doc_type"]
                                )
                                if dl_result:
                                    meta = dl_result

                            with get_session() as session:
                                values = {
                                    "ksd_fund_code": ksd,
                                    "doc_type": doc["doc_type"],
                                    "source_url": doc["source_url"],
                                    **meta,
                                }
                                stmt = insert(EtfDocument).values(**values)
                                stmt = stmt.on_conflict_do_update(
                                    constraint="etf_documents_ksd_fund_code_doc_type_source_url_key",
                                    set_={
                                        k: v
                                        for k, v in meta.items()
                                        if v is not None
                                    } if meta else {"doc_type": doc["doc_type"]},
                                )
                                session.execute(stmt)

                        self.log.debug(f"{ksd}: {len(pdf_links)} documents found")

                    processed += 1

                except Exception as e:
                    self.log.warning(f"Failed docs for {ksd}: {e}")
                    failed += 1

            self.finish_run(run_id, processed=processed, failed=failed)

        except Exception as e:
            self.log.error(f"Documents scrape failed: {e}")
            self.finish_run(run_id, processed=processed, failed=failed, error=str(e))
            raise
