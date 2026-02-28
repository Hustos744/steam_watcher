from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class MusicTrack:
    track_id: str
    name: str
    duration: int
    url: str
    source: str


class MusicProvider:
    def fetch_popular_tracks(self, limit: int) -> list[MusicTrack]:
        raise NotImplementedError


class PixabayMusicProvider(MusicProvider):
    def __init__(self, api_key: str, timeout_seconds: int = 30):
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    def fetch_popular_tracks(self, limit: int) -> list[MusicTrack]:
        if not self.api_key:
            return []

        response = requests.get(
            "https://pixabay.com/api/audio/",
            params={
                "key": self.api_key,
                "order": "popular",
                "per_page": min(200, max(20, limit)),
                "safesearch": "true",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        tracks: list[MusicTrack] = []
        for item in payload.get("hits", []) or []:
            url = self._extract_audio_url(item)
            if not url:
                continue
            tracks.append(
                MusicTrack(
                    track_id=str(item.get("id", "")),
                    name=item.get("tags") or item.get("user") or f"pixabay_{item.get('id', '')}",
                    duration=int(item.get("duration", 0) or 0),
                    url=url,
                    source="pixabay",
                )
            )
            if len(tracks) >= limit:
                break
        return tracks

    @staticmethod
    def _extract_audio_url(item: dict) -> str:
        candidates = [item.get("url"), item.get("audio"), item.get("audio_url")]
        audio_map = item.get("audio_file") or item.get("audio_files") or item.get("audio")
        if isinstance(audio_map, dict):
            for key in ("high", "medium", "low", "url"):
                val = audio_map.get(key)
                if isinstance(val, str):
                    candidates.append(val)
                elif isinstance(val, dict):
                    url = val.get("url")
                    if isinstance(url, str):
                        candidates.append(url)

        for c in candidates:
            if isinstance(c, str) and c.startswith("http"):
                return c
        return ""


class JamendoMusicProvider(MusicProvider):
    def __init__(self, client_id: str, timeout_seconds: int = 30):
        self.client_id = client_id.strip()
        self.timeout_seconds = timeout_seconds

    def fetch_popular_tracks(self, limit: int) -> list[MusicTrack]:
        if not self.client_id:
            return []

        response = requests.get(
            "https://api.jamendo.com/v3.0/tracks/",
            params={
                "client_id": self.client_id,
                "format": "json",
                "limit": min(200, max(20, limit)),
                "order": "popularity_total",
                "audioformat": "mp32",
                "include": "musicinfo",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        tracks: list[MusicTrack] = []
        for item in payload.get("results", []) or []:
            url = item.get("audio")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            tracks.append(
                MusicTrack(
                    track_id=str(item.get("id", "")),
                    name=item.get("name") or f"jamendo_{item.get('id', '')}",
                    duration=int(item.get("duration", 0) or 0),
                    url=url,
                    source="jamendo",
                )
            )
            if len(tracks) >= limit:
                break
        return tracks


def build_music_provider(provider: str, pixabay_api_key: str, jamendo_client_id: str, timeout_seconds: int = 30) -> MusicProvider:
    normalized = (provider or "").strip().lower()
    if normalized == "jamendo":
        return JamendoMusicProvider(client_id=jamendo_client_id, timeout_seconds=timeout_seconds)
    return PixabayMusicProvider(api_key=pixabay_api_key, timeout_seconds=timeout_seconds)
