from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tiger_etf.config import settings
from tiger_etf.db import get_session
from tiger_etf.models import ScrapeRun
from tiger_etf.utils.logging_config import get_logger


class BaseScraper:
    name: str = "base"

    def __init__(self) -> None:
        self.log = get_logger(f"scraper.{self.name}")
        self.client = httpx.Client(
            base_url=settings.base_url,
            timeout=60.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                "Referer": f"{settings.base_url}/ko/product/search/list.do",
            },
            follow_redirects=True,
        )
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < settings.request_delay:
            time.sleep(settings.request_delay - elapsed)
        self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def get(self, url: str, **kwargs) -> httpx.Response:
        self._throttle()
        resp = self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def post(self, url: str, **kwargs) -> httpx.Response:
        self._throttle()
        resp = self.client.post(url, **kwargs)
        resp.raise_for_status()
        return resp

    def start_run(self) -> int:
        with get_session() as session:
            run = ScrapeRun(scraper_name=self.name)
            session.add(run)
            session.flush()
            run_id = run.id
        self.log.info(f"Started scrape run #{run_id}")
        return run_id

    def finish_run(
        self, run_id: int, *, processed: int = 0, failed: int = 0, error: str | None = None
    ) -> None:
        status = "failed" if error else "success"
        with get_session() as session:
            run = session.get(ScrapeRun, run_id)
            if run:
                run.finished_at = datetime.now(timezone.utc)
                run.status = status
                run.items_processed = processed
                run.items_failed = failed
                run.error_message = error
        self.log.info(
            f"Finished scrape run #{run_id}: {status} "
            f"(processed={processed}, failed={failed})"
        )

    def run(self, **kwargs) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.client.close()
