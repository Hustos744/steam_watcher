from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.pipelines.music_provider import MusicProvider


class MusicAutoDownloader:
    def __init__(
        self,
        music_dir: str,
        provider: MusicProvider,
        enabled: bool = False,
        target_count: int = 20,
        refresh_hours: int = 24,
        timeout_seconds: int = 30,
    ):
        self.enabled = enabled
        self.music_dir = Path(music_dir)
        self.provider = provider
        self.target_count = max(target_count, 1)
        self.refresh_hours = max(refresh_hours, 1)
        self.timeout_seconds = timeout_seconds

        self.logger = logging.getLogger(self.__class__.__name__)
        self._last_refresh_monotonic: float | None = None
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def refresh_if_needed(self) -> int:
        if not self.enabled:
            return 0

        now = time.monotonic()
        if self._last_refresh_monotonic is not None:
            elapsed = now - self._last_refresh_monotonic
            if elapsed < self.refresh_hours * 3600:
                return 0

        existing = self._count_music_files()
        need = self.target_count - existing
        if need <= 0:
            self._last_refresh_monotonic = now
            return 0

        downloaded = self._download_popular_tracks(need)
        self._last_refresh_monotonic = now
        if downloaded:
            self.logger.info("Downloaded %s music tracks for shorts", downloaded)
        return downloaded

    def _count_music_files(self) -> int:
        count = 0
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg", "*.flac"):
            count += len(list(self.music_dir.glob(ext)))
        return count

    def _download_popular_tracks(self, max_downloads: int) -> int:
        tracks = self.provider.fetch_popular_tracks(limit=min(200, max(20, max_downloads * 3)))
        downloaded = 0
        for track in tracks:
            if downloaded >= max_downloads:
                break

            audio_url = track.url
            if not audio_url:
                continue

            filename = self._build_filename(track.track_id, track.source, audio_url)
            out_path = self.music_dir / filename
            if out_path.exists():
                continue

            try:
                self._download_file(audio_url, out_path)
                downloaded += 1
            except Exception:
                self.logger.exception("Failed downloading music track: %s", audio_url)

        return downloaded

    @staticmethod
    def _build_filename(item_id: str, source: str, audio_url: str) -> str:
        parsed = urlparse(audio_url)
        ext = Path(parsed.path).suffix or ".mp3"
        return f"{source}_{item_id}{ext}"

    def _download_file(self, url: str, out_path: Path) -> None:
        with requests.get(url, timeout=self.timeout_seconds, stream=True) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)
