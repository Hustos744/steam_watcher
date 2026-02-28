import json
import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

APP_PATH_RE = re.compile(r"/app/(\d+)")
APP_DATA_RE = re.compile(r'data-ds-appid="(\d+)"')
CURATOR_ID_RE = re.compile(r"/curator/(\d+)")
RSS_NEXT_RE = re.compile(r'<atom:link[^>]*rel="next"[^>]*href="([^"]+)"', re.IGNORECASE)


class SteamCuratorBlocklist:
    def __init__(self, curator_url: str, refresh_seconds: int = 3600, max_pages: int = 0, timeout_seconds: int = 15):
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
        appids: set[int] = set()

        curator_id = self._extract_curator_id(self.curator_url)
        if curator_id:
            ajax_appids = self._fetch_via_ajax(curator_id)
            appids.update(ajax_appids)
            self.logger.info("Curator ajax sync: %s appids", len(ajax_appids))

        rss_appids = self._fetch_via_rss(self.curator_url)
        appids.update(rss_appids)
        if rss_appids:
            self.logger.info("Curator rss sync: %s appids", len(rss_appids))

        html_appids = self._fetch_via_html(self._to_recommended_url(self.curator_url))
        appids.update(html_appids)
        if html_appids:
            self.logger.info("Curator html sync: %s appids", len(html_appids))

        self.logger.info("Curator blocklist refreshed: %s appids total", len(appids))
        return appids

    def _fetch_via_ajax(self, curator_id: str) -> set[int]:
        endpoints = [
            f"https://store.steampowered.com/curator/{curator_id}/admin/ajaxgetrecommendations/",
            f"https://store.steampowered.com/curator/{curator_id}/ajaxgetrecommendations/",
            f"https://store.steampowered.com/curator/{curator_id}/ajaxgetfilteredrecommendations/",
        ]

        max_steps = self.max_pages if self.max_pages > 0 else 200
        count = 100

        for endpoint in endpoints:
            appids: set[int] = set()
            start = 0
            success_steps = 0

            for _ in range(max_steps):
                payload = self._fetch_json(endpoint, params={"query": "", "start": start, "count": count})
                if payload is None:
                    break

                blob = self._extract_json_blob(payload)
                page_appids = self._extract_appids(blob)
                if not page_appids:
                    break

                new_on_page = page_appids - appids
                appids.update(page_appids)
                success_steps += 1

                if len(page_appids) < count:
                    break
                if not new_on_page and start > 0:
                    break

                start += count

            if appids:
                self.logger.info("Curator ajax endpoint worked: %s (pages=%s)", endpoint, success_steps)
                return appids

        return set()

    def _fetch_via_rss(self, url: str) -> set[int]:
        rss_url = self._to_rss_url(url)
        if not rss_url:
            return set()

        appids: set[int] = set()
        visited: set[str] = set()
        pending: list[str] = [rss_url]
        max_steps = self.max_pages if self.max_pages > 0 else 200

        while pending and len(visited) < max_steps:
            current = pending.pop(0)
            if current in visited:
                continue
            visited.add(current)

            xml = self._fetch_text(current)
            if not xml:
                continue

            appids.update(self._extract_appids(xml))

            next_url = self._extract_rss_next_link(xml)
            if next_url and next_url not in visited:
                pending.append(next_url)

        return appids

    def _fetch_via_html(self, url: str) -> set[int]:
        if not url:
            return set()

        appids: set[int] = set()
        max_steps = self.max_pages if self.max_pages > 0 else 200
        consecutive_no_new = 0

        for page in range(1, max_steps + 1):
            html = self._fetch_text(self._with_page(url, page))
            if not html:
                consecutive_no_new += 1
                if page > 1 and consecutive_no_new >= 3:
                    break
                continue

            page_appids = self._extract_appids(html)
            new_count = len(page_appids - appids)
            appids.update(page_appids)

            if page > 1 and new_count == 0:
                consecutive_no_new += 1
            else:
                consecutive_no_new = 0

            if page > 1 and consecutive_no_new >= 3:
                break

        return appids

    def _fetch_text(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.text
        except Exception:
            self.logger.exception("Failed to fetch curator text url: %s", url)
            return ""

    def _fetch_json(self, url: str, params: dict) -> Optional[dict]:
        try:
            response = requests.get(url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except Exception:
            self.logger.debug("Curator json endpoint failed: %s", url, exc_info=True)
            return None

    @staticmethod
    def _extract_json_blob(payload: dict) -> str:
        candidates = [
            payload.get("recommendations", ""),
            payload.get("results_html", ""),
            payload.get("html", ""),
        ]
        candidates.append(json.dumps(payload, ensure_ascii=True))
        return "\n".join([str(item) for item in candidates if item])

    @staticmethod
    def _extract_appids(text: str) -> set[int]:
        appids: set[int] = set()
        for raw in APP_PATH_RE.findall(text):
            appids.add(int(raw))
        for raw in APP_DATA_RE.findall(text):
            appids.add(int(raw))
        return appids

    @staticmethod
    def _extract_curator_id(url: str) -> str:
        match = CURATOR_ID_RE.search(url)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_rss_next_link(xml_text: str) -> str:
        match = RSS_NEXT_RE.search(xml_text)
        return match.group(1) if match else ""

    @staticmethod
    def _to_rss_url(url: str) -> str:
        if not url:
            return ""
        if "/rss" in url:
            return url
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path:
            return ""
        return urlunparse(parsed._replace(path=f"{path}/rss", query=""))

    @staticmethod
    def _to_recommended_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        path = re.sub(r"/rss$", "", path)
        if path.endswith("/recommended"):
            recommended_path = path
        else:
            recommended_path = f"{path}/recommended"
        return urlunparse(parsed._replace(path=f"{recommended_path}/", query=""))

    @staticmethod
    def _with_page(url: str, page: int) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["p"] = [str(page)]
        normalized_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=normalized_query))
