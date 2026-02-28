from __future__ import annotations

import logging
import json
import time

import requests

from app.post_design import DealPostFormatter
from app.steam import Deal, DealMedia


class TelegramPublisher:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        parse_mode: str = "HTML",
        timeout_seconds: int = 15,
        usd_to_uah_rate: float = 41.0,
        include_trailer: bool = True,
        extra_images_count: int = 3,
        max_retries: int = 3,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.timeout_seconds = timeout_seconds
        self.include_trailer = include_trailer
        self.extra_images_count = max(extra_images_count, 0)
        self.max_retries = max(max_retries, 0)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.post_formatter = DealPostFormatter(usd_to_uah_rate=usd_to_uah_rate)

    @property
    def _send_photo_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    @property
    def _send_media_group_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"

    def compose_caption(self, deal: Deal) -> str:
        try:
            return self.post_formatter.build_caption(deal)
        except Exception:
            self.logger.exception("Post formatter failed for appid=%s", deal.appid)
            return f"<b>{deal.name}</b>\nDiscount: -{deal.discount_percent}%\n{deal.store_url}"

    def _post(self, url: str, payload: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            response = requests.post(url, data=payload, timeout=self.timeout_seconds)

            # Telegram flood control: honor retry_after and retry request.
            if response.status_code == 429:
                retry_after = 0
                try:
                    data = response.json()
                    retry_after = int(data.get("parameters", {}).get("retry_after", 0) or 0)
                except Exception:
                    retry_after = 0

                if attempt < self.max_retries:
                    sleep_seconds = retry_after if retry_after > 0 else 2
                    self.logger.warning(
                        "Telegram rate limit hit. Retrying in %ss (attempt %s/%s)",
                        sleep_seconds,
                        attempt + 1,
                        self.max_retries,
                    )
                    time.sleep(sleep_seconds)
                    continue

            try:
                response.raise_for_status()
                data = response.json()
                if not data.get("ok", False):
                    raise RuntimeError(f"Telegram API error: {data}")
                return data
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2)
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Telegram API request failed")

    def _build_media_group(self, deal: Deal, media: DealMedia | None, caption: str) -> list[dict]:
        group: list[dict] = []
        cover_photo = deal.header_image or ((media.image_urls[0] if media and media.image_urls else ""))
        if not cover_photo:
            raise RuntimeError(f"No cover image for appid={deal.appid}")

        group.append(
            {
                "type": "photo",
                "media": cover_photo,
                "caption": caption,
                "parse_mode": self.parse_mode,
            }
        )

        if self.include_trailer and media and media.trailer_url:
            group.append(
                {
                    "type": "video",
                    "media": media.trailer_url,
                    "supports_streaming": True,
                }
            )

        if media and media.image_urls and self.extra_images_count > 0:
            extras: list[str] = []
            for url in media.image_urls:
                if url and url != cover_photo and url not in extras:
                    extras.append(url)
                if len(extras) >= self.extra_images_count:
                    break
            for url in extras:
                group.append({"type": "photo", "media": url})

        return group

    def publish_deal(self, deal: Deal, media: DealMedia | None = None) -> None:
        caption = f"{self.compose_caption(deal)}\n{self.post_formatter.links_line(deal)}"
        media_group = self._build_media_group(deal, media, caption)
        payload = {
            "chat_id": self.chat_id,
            "media": json.dumps(media_group, ensure_ascii=True),
        }
        try:
            self._post(self._send_media_group_url, payload)
        except Exception:
            self.logger.exception("sendMediaGroup failed for appid=%s, fallback to sendPhoto", deal.appid)
            fallback_payload = {
                "chat_id": self.chat_id,
                "photo": deal.header_image,
                "caption": caption,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": True,
            }
            self._post(self._send_photo_url, fallback_payload)
