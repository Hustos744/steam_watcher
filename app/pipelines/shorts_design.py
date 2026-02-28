from __future__ import annotations

from dataclasses import dataclass

from app.steam import Deal


def escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "%%")
        .replace(",", "\\,")
    )


def format_price(cents: int, currency: str) -> str:
    if cents <= 0:
        return "Free"
    return f"{cents / 100:.2f} {currency}"


@dataclass(frozen=True)
class ShortsDesign:
    intro_title_template: str = "Steam Discounts - {date}"
    intro_subtitle: str = "Daily deals summary"
    outro_title: str = "Like - Follow - Telegram"
    overlay_box_y: int = 65
    overlay_box_h: int = 350
    overlay_title_y: int = 95
    overlay_discount_y: int = 180
    overlay_old_price_y: int = 280
    overlay_new_price_y: int = 330

    # Text animation tuning (seconds)
    text_fade_in_seconds: float = 0.35
    text_fade_out_seconds: float = 0.35
    title_delay_seconds: float = 0.00
    discount_delay_seconds: float = 0.10
    old_price_delay_seconds: float = 0.20
    new_price_delay_seconds: float = 0.30

    # Segment transition tuning (fade to black at segment edges)
    segment_fade_in_seconds: float = 0.25
    segment_fade_out_seconds: float = 0.25

    def _alpha_expr(self, total_duration: float, delay: float = 0.0) -> str:
        fade_in = max(self.text_fade_in_seconds, 0.01)
        fade_out = max(self.text_fade_out_seconds, 0.01)
        out_start = max(total_duration - fade_out, delay + fade_in)
        # ffmpeg expression:
        # 0 before delay -> fade in -> stay 1 -> fade out at end
        return (
            f"if(lt(t\\,{delay})\\,0\\,"
            f"if(lt(t\\,{delay + fade_in})\\,(t-{delay})/{fade_in}\\,"
            f"if(lt(t\\,{out_start})\\,1\\,max(0\\,({total_duration}-t)/{fade_out}))))"
        )

    def intro_filter(self, date_str: str, font_path: str, segment_duration: float) -> str:
        line1 = escape_drawtext(self.intro_title_template.format(date=date_str))
        line2 = escape_drawtext(self.intro_subtitle)
        return (
            f"drawtext=fontfile={font_path}:text='{line1}':x=(w-text_w)/2:y=760:fontsize=62:fontcolor=white:"
            f"alpha='{self._alpha_expr(segment_duration, delay=0.0)}',"
            f"drawtext=fontfile={font_path}:text='{line2}':x=(w-text_w)/2:y=860:fontsize=46:fontcolor=yellow:"
            f"alpha='{self._alpha_expr(segment_duration, delay=0.2)}'"
        )

    def outro_filter(self, telegram_url: str, font_path: str, segment_duration: float) -> str:
        line1 = escape_drawtext(self.outro_title)
        line2 = escape_drawtext(telegram_url)
        return (
            f"drawtext=fontfile={font_path}:text='{line1}':x=(w-text_w)/2:y=790:fontsize=60:fontcolor=white:"
            f"alpha='{self._alpha_expr(segment_duration, delay=0.0)}',"
            f"drawtext=fontfile={font_path}:text='{line2}':x=(w-text_w)/2:y=900:fontsize=42:fontcolor=cyan:"
            f"alpha='{self._alpha_expr(segment_duration, delay=0.25)}'"
        )

    def game_overlay_filter(self, deal: Deal, font_path: str, segment_duration: float) -> str:
        title = escape_drawtext(deal.name[:60])
        discount = escape_drawtext(f"-{deal.discount_percent}%")
        old_price = escape_drawtext(format_price(deal.original_price, deal.currency))
        new_price = escape_drawtext(format_price(deal.final_price, deal.currency))
        return (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "fps=30,"
            "setpts=PTS-STARTPTS,"
            "format=yuv420p,"
            f"drawbox=x=35:y={self.overlay_box_y}:w=1010:h={self.overlay_box_h}:color=black@0.45:t=fill,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{title}':x=60:y={self.overlay_title_y}:fontsize=50:fontcolor=white,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{discount}':x=60:y={self.overlay_discount_y}:fontsize=78:fontcolor=yellow,"
            f"drawtext=fontfile={font_path}:expansion=none:text='Old\\: {old_price}':x=60:y={self.overlay_old_price_y}:fontsize=40:fontcolor=white,"
            f"drawtext=fontfile={font_path}:expansion=none:text='Now\\: {new_price}':x=60:y={self.overlay_new_price_y}:fontsize=48:fontcolor=lime"
        )
