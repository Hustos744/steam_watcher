from datetime import datetime, timedelta, timezone
from html import escape

import requests

from app.steam import Deal


def _format_price(cents: int, currency: str) -> str:
    if cents <= 0:
        return "Free"
    return f"{cents / 100:.2f} {currency}"


def _format_time_left(expires_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    if delta.total_seconds() <= 0:
        return "ending now"

    total_minutes = int(delta.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rem_minutes, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes and not days:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "<1m"


class TelegramPublisher:
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "HTML", timeout_seconds: int = 15):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.timeout_seconds = timeout_seconds

    @property
    def _send_photo_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    def compose_caption(self, deal: Deal) -> str:
        expires_at = datetime.fromtimestamp(deal.discount_expiration, tz=timezone.utc)
        expires = expires_at.strftime("%Y-%m-%d %H:%M UTC")
        time_left = _format_time_left(expires_at)

        old_price = _format_price(deal.original_price, deal.currency)
        new_price = _format_price(deal.final_price, deal.currency)
        saved_cents = max(deal.original_price - deal.final_price, 0)
        saved = _format_price(saved_cents, deal.currency)

        if deal.original_price > 0:
            price_line = f"<s>{old_price}</s> -> <b>{new_price}</b>"
            save_line = f"<b>You save:</b> {saved}"
        else:
            price_line = f"<b>{new_price}</b>"
            save_line = "<b>You save:</b> -"

        return (
            f"<b>{escape(deal.name)}</b>\n"
            f"<b>Discount:</b> {deal.discount_percent}% OFF\n"
            f"<b>Price:</b> {price_line}\n"
            f"{save_line}\n"
            f"<b>Ends:</b> {expires} ({time_left} left)\n"
            f"<a href=\"{deal.store_url}\">Open in Steam</a>"
        )

    def publish_deal(self, deal: Deal) -> None:
        payload = {
            "chat_id": self.chat_id,
            "photo": deal.header_image,
            "caption": self.compose_caption(deal),
            "parse_mode": self.parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(self._send_photo_url, data=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(f"Telegram API error: {data}")
