import logging
import re
import time
from typing import Optional

import requests

APP_PATH_RE = re.compile(r"/app/(\d+)")
APP_DATA_RE = re.compile(r'data-ds-appid="(\d+)"')
PAGE_RE = re.compile(r'[?&]p=(\d+)')


class SteamCuratorBlocklist:
    def __init__(self, curator_url: str, refresh_seconds: int = 3600, max_pages: int = 5, timeout_seconds: int = 15):
        self.curator_url = curator_url.strip()
        self.refresh_seconds = refresh_seconds
        self.max_pages = max_pages
        self.timeout_seconds = timeout_seconds

        self.logger = logging.getLogger(self.__class__.__name__)
        self._cached_appids: set[int] = set()
        self._last_refresh_monotonic: Optional[float] = None

    def get_appids(self) -> set[int]:
        if not self.curator_url:
            return set()

        now = time.monotonic()
        if self._last_refresh_monotonic is None or now - self._last_refresh_monotonic >= self.refresh_seconds:
            self._cached_appids = self._refresh()
            self._last_refresh_monotonic = now
        return set(self._cached_appids)

    def _refresh(self) -> set[int]:
        visited: set[str] = set()
        pending: list[str] = [self.curator_url]
        appids: set[int] = set()

        while pending and len(visited) < self.max_pages:
            url = pending.pop(0)
            if url in visited:
                continue

            visited.add(url)
            html = self._fetch_page(url)
            if not html:
                continue

            appids.update(self._extract_appids(html))

            for next_url in self._extract_pagination_links(html, url):
                if next_url not in visited and next_url not in pending:
                    pending.append(next_url)

        self.logger.info("Curator blocklist refreshed: %s appids from %s pages", len(appids), len(visited))
        return appids

    def _fetch_page(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.text
        except Exception:
            self.logger.exception("Failed to fetch curator page: %s", url)
            return ""

    @staticmethod
    def _extract_appids(html: str) -> set[int]:
        appids: set[int] = set()
        for raw in APP_PATH_RE.findall(html):
            appids.add(int(raw))
        for raw in APP_DATA_RE.findall(html):
            appids.add(int(raw))
        return appids

    @staticmethod
    def _extract_pagination_links(html: str, current_url: str) -> list[str]:
        base = current_url.split("?", 1)[0]
        pages = sorted({int(page) for page in PAGE_RE.findall(html) if page.isdigit()})
        links = []
        for page in pages:
            if page <= 1:
                continue
            links.append(f"{base}?p={page}")
        return links
