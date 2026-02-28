from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from app.pipelines.music_provider import MusicProvider


class MusicCuratorBot:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        provider: MusicProvider,
        music_dir: str,
        timezone_name: str = "Europe/Kyiv",
        morning_hour: int = 9,
        morning_minute: int = 0,
        batch_size: int = 3,
        timeout_seconds: int = 30,
    ):
        self.bot_token = bot_token
        self.chat_id = str(chat_id).strip()
        self.provider = provider
        self.music_dir = Path(music_dir)
        self.tz = ZoneInfo(timezone_name)
        self.morning_hour = max(0, min(23, morning_hour))
        self.morning_minute = max(0, min(59, morning_minute))
        self.batch_size = max(1, batch_size)
        self.timeout_seconds = timeout_seconds

        self.logger = logging.getLogger(self.__class__.__name__)
        self.music_dir.mkdir(parents=True, exist_ok=True)

        self._offset = 0
        self._last_daily_date = ""
        self._tracks: list[dict] = []
        self._cursor = 0

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def run_forever(self, stop_event) -> None:
        if not self.chat_id:
            self.logger.warning("Music curator enabled but MUSIC_CURATOR_CHAT_ID is empty")
            return

        self.logger.info("Music curator bot started")
        while not stop_event.is_set():
            try:
                self._send_daily_if_due()
                self._poll_updates()
            except Exception:
                self.logger.exception("Music curator loop error")
                time.sleep(3)

    def _send_daily_if_due(self) -> None:
        now = datetime.now(self.tz)
        today = now.strftime("%Y-%m-%d")
        due = now.hour > self.morning_hour or (now.hour == self.morning_hour and now.minute >= self.morning_minute)
        if due and self._last_daily_date != today:
            self._refresh_tracks()
            self._send_next_batch(intro="Morning picks: choose one or request more")
            self._last_daily_date = today

    def _poll_updates(self) -> None:
        response = requests.get(
            f"{self._api_base}/getUpdates",
            params={
                "offset": self._offset,
                "timeout": 25,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return

        for update in data.get("result", []):
            update_id = int(update.get("update_id", 0))
            self._offset = max(self._offset, update_id + 1)
            self._handle_update(update)

    def _handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            self._handle_callback(update["callback_query"])
            return

        message = update.get("message", {})
        if str(message.get("chat", {}).get("id", "")) != self.chat_id:
            return

        text = (message.get("text") or "").strip().lower()
        if text in {"/start", "/music", "music", "tracks"}:
            self._refresh_tracks()
            self._send_next_batch(intro="Manual picks:")
            return
        if text in {"/more", "more", "next"}:
            self._send_next_batch(intro="More options:")
            return

        if message.get("audio") or message.get("document"):
            self._save_uploaded_track(message)

    def _handle_callback(self, callback: dict) -> None:
        message = callback.get("message", {})
        if str(message.get("chat", {}).get("id", "")) != self.chat_id:
            return

        callback_id = callback.get("id")
        data = callback.get("data", "")

        if data == "music_more":
            self._send_next_batch(intro="More options:")
            self._answer_callback(callback_id, "Sending more tracks")
            return

        if data.startswith("music_pick:"):
            track_id = data.split(":", 1)[1]
            track = self._find_track(track_id)
            if not track:
                self._answer_callback(callback_id, "Track not found, refresh list")
                return

            path = self._download_track(track)
            self._set_preferred_track(path)
            self._send_message(f"Selected track: {track.get('name', track_id)}\\nSaved: {path.name}")
            self._answer_callback(callback_id, "Track selected")

    def _refresh_tracks(self) -> None:
        provider_tracks = self.provider.fetch_popular_tracks(limit=100)
        self._tracks = [
            {
                "id": t.track_id,
                "name": t.name,
                "duration": t.duration,
                "url": t.url,
                "source": t.source,
            }
            for t in provider_tracks
            if t.url
        ]
        self._cursor = 0

    def _send_next_batch(self, intro: str = "Top tracks:") -> None:
        if not self._tracks:
            self._refresh_tracks()
        if not self._tracks:
            self._send_message("No tracks available now")
            return

        start = self._cursor
        end = min(len(self._tracks), start + self.batch_size)
        batch = self._tracks[start:end]
        if not batch:
            self._cursor = 0
            start = 0
            end = min(len(self._tracks), self.batch_size)
            batch = self._tracks[start:end]

        self._cursor = end

        lines = [intro]
        keyboard_rows = []
        for idx, track in enumerate(batch, start=1):
            duration = int(track.get("duration", 0) or 0)
            lines.append(f"{idx}. {track['name']} ({duration}s)")
            keyboard_rows.append(
                [
                    {
                        "text": f"Use #{idx}",
                        "callback_data": f"music_pick:{track['id']}",
                    }
                ]
            )

        keyboard_rows.append([{"text": "More options", "callback_data": "music_more"}])

        self._send_message(
            "\\n".join(lines),
            reply_markup={"inline_keyboard": keyboard_rows},
        )

    def _find_track(self, track_id: str) -> dict | None:
        for track in self._tracks:
            if track.get("id") == track_id:
                return track
        return None

    def _download_track(self, track: dict) -> Path:
        url = track["url"]
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix or ".mp3"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", track.get("name", "track"))[:40]
        source = track.get("source", "provider")
        out = self.music_dir / f"curator_{source}_{track['id']}_{safe_name}{ext}"

        if not out.exists():
            with requests.get(url, timeout=self.timeout_seconds, stream=True) as r:
                r.raise_for_status()
                with out.open("wb") as f:
                    for chunk in r.iter_content(128 * 1024):
                        if chunk:
                            f.write(chunk)
        return out

    def _save_uploaded_track(self, message: dict) -> None:
        audio = message.get("audio")
        document = message.get("document")

        file_obj = audio or document
        if not file_obj:
            return

        file_id = file_obj.get("file_id")
        file_name = file_obj.get("file_name") or f"uploaded_{file_id}.mp3"
        if not file_id:
            return

        file_info = requests.get(
            f"{self._api_base}/getFile",
            params={"file_id": file_id},
            timeout=self.timeout_seconds,
        )
        file_info.raise_for_status()
        data = file_info.json()
        if not data.get("ok"):
            return

        file_path = data.get("result", {}).get("file_path", "")
        if not file_path:
            return

        download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", file_name)
        out = self.music_dir / f"manual_{safe_name}"

        with requests.get(download_url, timeout=self.timeout_seconds, stream=True) as r:
            r.raise_for_status()
            with out.open("wb") as f:
                for chunk in r.iter_content(128 * 1024):
                    if chunk:
                        f.write(chunk)

        self._set_preferred_track(out)
        self._send_message(f"Received your track and set as preferred: {out.name}")

    def _set_preferred_track(self, path: Path) -> None:
        marker = self.music_dir / ".preferred_track.txt"
        marker.write_text(path.name, encoding="utf-8")

    def _send_message(self, text: str, reply_markup: dict | None = None) -> None:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=True)

        response = requests.post(f"{self._api_base}/sendMessage", data=payload, timeout=self.timeout_seconds)
        response.raise_for_status()

    def _answer_callback(self, callback_id: str, text: str) -> None:
        if not callback_id:
            return
        requests.post(
            f"{self._api_base}/answerCallbackQuery",
            data={"callback_query_id": callback_id, "text": text},
            timeout=self.timeout_seconds,
        )
