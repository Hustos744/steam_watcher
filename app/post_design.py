from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.steam import Deal


def _amount(cents: int) -> float:
    return max(cents, 0) / 100.0


def _to_usd(cents: int, currency: str, usd_to_uah_rate: float) -> float:
    amount = _amount(cents)
    code = (currency or "").upper()
    if code == "USD":
        return amount
    if code == "UAH":
        return amount / usd_to_uah_rate if usd_to_uah_rate > 0 else amount
    return amount


def _to_uah(cents: int, currency: str, usd_to_uah_rate: float) -> float:
    amount = _amount(cents)
    code = (currency or "").upper()
    if code == "UAH":
        return amount
    if code == "USD":
        return amount * usd_to_uah_rate
    return amount * usd_to_uah_rate


def _fmt_usd(cents: int, currency: str, usd_to_uah_rate: float) -> str:
    if cents <= 0:
        return "Free"
    return f"${_to_usd(cents, currency, usd_to_uah_rate):,.2f}"


def _fmt_uah(cents: int, currency: str, usd_to_uah_rate: float) -> str:
    if cents <= 0:
        return "Free"
    return f"{_to_uah(cents, currency, usd_to_uah_rate):,.0f} ₴"


def _format_time_left(expires_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    if delta.total_seconds() <= 0:
        return "закінчується зараз"

    total_minutes = int(delta.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rem_minutes, 60)

    if days:
        return f"{days}д {hours}г"
    if hours:
        return f"{hours}г {minutes}хв"
    return f"{minutes}хв"


def _badge(discount_percent: int) -> str:
    if discount_percent >= 90:
        return "🧨 МЕГА"
    if discount_percent >= 80:
        return "🔥 HOT"
    if discount_percent >= 60:
        return "⚡ ТОП"
    if discount_percent >= 40:
        return "💎 ВАРТО"
    return "💸 SALE"


def _hype_emoji(discount_percent: int) -> str:
    if discount_percent >= 90:
        return "💥"
    if discount_percent >= 80:
        return "🔥"
    if discount_percent >= 60:
        return "⚡"
    if discount_percent >= 40:
        return "💎"
    return "🛒"


class DealPostFormatter:
    def __init__(self, usd_to_uah_rate: float = 41.0):
        self.usd_to_uah_rate = usd_to_uah_rate

    def build_caption(self, deal: Deal) -> str:
        raw_title = (deal.name or "").strip()
        title = escape(raw_title)

        expires_at = datetime.fromtimestamp(deal.discount_expiration, tz=timezone.utc)
        ends_at = expires_at.strftime("%d.%m.%Y %H:%M UTC")
        left = _format_time_left(expires_at)

        old_usd = _fmt_usd(deal.original_price, deal.currency, self.usd_to_uah_rate)
        new_usd = _fmt_usd(deal.final_price, deal.currency, self.usd_to_uah_rate)
        old_uah = _fmt_uah(deal.original_price, deal.currency, self.usd_to_uah_rate)
        new_uah = _fmt_uah(deal.final_price, deal.currency, self.usd_to_uah_rate)

        saved_cents = max(deal.original_price - deal.final_price, 0)
        saved_usd = _fmt_usd(saved_cents, deal.currency, self.usd_to_uah_rate)
        saved_uah = _fmt_uah(saved_cents, deal.currency, self.usd_to_uah_rate)

        badge = _badge(deal.discount_percent)
        hype = _hype_emoji(deal.discount_percent)

        # Супер-акцент: “НОВА ЦІНА” окремим жирним рядком
        if deal.original_price > 0 and deal.discount_percent > 0:
            header_price = f"{hype} <b>НОВА ЦІНА: {new_usd} • {new_uah}</b>"
            was_line = f"Було: <s>{old_usd} • {old_uah}</s>"
            save_line = f"Ти економиш: <b>{saved_usd} • {saved_uah}</b>"
        else:
            header_price = f"{hype} <b>ЦІНА: {new_usd} • {new_uah}</b>"
            was_line = ""
            save_line = "Ти економиш: —"

        # Невеликий CTA без спаму
        cta = "🕹️ Забирай, поки діє знижка 👇"

        return (
            f"{badge} <b>-{deal.discount_percent}%</b>\n"
            f"🎮 <b>{escape(raw_title.upper())}</b>\n"
            "\n"
            f"{header_price}\n"
            + (f"{was_line}\n" if was_line else "")
            + f"{save_line}\n"
            "\n"
            f"⏳ <b>ЗАЛИШИЛОСЬ:</b> <b>{left}</b>\n"
            f"🕒 <b>ДО:</b> <b>{ends_at}</b>\n"
            "\n"
            f"{cta}"
        )

    @staticmethod
    def links_line(deal: Deal) -> str:
        steam = deal.store_url
        steamdb = f"https://steamdb.info/app/{deal.appid}/"
        return f'<a href="{steam}">Open in Steam</a> | <a href="{steamdb}">Open in SteamDB</a>'
