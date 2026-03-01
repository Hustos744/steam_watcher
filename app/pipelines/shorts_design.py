from __future__ import annotations

from dataclasses import dataclass

from app.steam import Deal


def escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def format_price(cents: int, currency: str) -> str:
    if cents <= 0:
        return "Free"
    return f"{cents / 100:.2f} {currency}"


def ellipsize(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: max(0, n - 3)].rstrip() + "..."


@dataclass(frozen=True)
class ShortsDesign:
    # Canvas (Shorts)
    w: int = 1080
    h: int = 1920
    fps: int = 30

    # Safe area + layout
    safe_x: int = 60
    safe_top: int = 80
    safe_bottom: int = 90

    # --- Intro/Outro copy ---
    intro_kicker: str = "STEAM DEALS"
    intro_title_template: str = "Top discounts • {date}"
    intro_subtitle: str = "Swipe-friendly picks. Updated daily."
    outro_title: str = "More deals in Telegram"
    outro_subtitle: str = "Save + share to not miss drops"

    # --- Colors (feel free to tweak) ---
    bg1: str = "#0B1022"
    bg2: str = "#050816"
    neon_a: str = "#7C3AED"  # purple
    neon_b: str = "#06B6D4"  # cyan
    neon_c: str = "#22C55E"  # green
    white: str = "white"

    # Lower-third glass card geometry
    card_x: int = 60
    card_y: int = 1080
    card_w: int = 960
    card_h: int = 560

    # Inner padding
    pad_x: int = 44
    pad_y: int = 36

    # Typography
    title_fs: int = 52
    meta_fs: int = 34
    discount_fs: int = 56
    price_fs: int = 44

    # Animation
    text_fade_in: float = 0.25
    text_fade_out: float = 0.25

    # Stagger
    t_title: float = 0.00
    t_discount: float = 0.08
    t_prices: float = 0.16

    # Segment fades (to hide cuts)
    seg_fade_in: float = 0.18
    seg_fade_out: float = 0.22

    def _alpha_expr(self, total: float, delay: float = 0.0) -> str:
        fi = max(self.text_fade_in, 0.01)
        fo = max(self.text_fade_out, 0.01)
        out_start = max(total - fo, delay + fi)
        return (
            f"if(lt(t\\,{delay})\\,0\\,"
            f"if(lt(t\\,{delay + fi})\\,(t-{delay})/{fi}\\,"
            f"if(lt(t\\,{out_start})\\,1\\,max(0\\,({total}-t)/{fo}))))"
        )

    def _slide_y(self, base_y: int, total: float, delay: float, dist: int = 18) -> str:
        # starts slightly lower, slides up while fading in
        fi = max(self.text_fade_in, 0.01)
        # y = base + dist*(1 - progress)
        # progress = clamp((t-delay)/fi, 0..1)
        return (
            f"({base_y}+{dist}*(1-"
            f"if(lt(t\\,{delay})\\,0\\,"
            f"if(lt(t\\,{delay + fi})\\,(t-{delay})/{fi}\\,1)"
            f")))"
        )

    # ---------- INTRO / OUTRO ----------
    def intro_filter(self, date_str: str, font_path: str, segment_duration: float) -> str:
        kicker = escape_drawtext(self.intro_kicker)
        title = escape_drawtext(self.intro_title_template.format(date=date_str))
        sub = escape_drawtext(self.intro_subtitle)

        # Clean neon gradient vibes: top-left purple haze + bottom-right cyan haze
        # (No real gradients in drawbox, so we layer translucent boxes)
        return (
            f"fps={self.fps},setpts=PTS-STARTPTS,format=yuv420p,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color={self.bg1}@1.0:t=fill,"
            f"drawbox=x=-200:y=-200:w=900:h=900:color={self.neon_a}@0.20:t=fill,"
            f"drawbox=x=500:y=1100:w=900:h=900:color={self.neon_b}@0.18:t=fill,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.15:t=fill,"  # vignette-ish
            # Glass slab behind text
            f"drawbox=x={self.safe_x}:y=680:w={self.w-2*self.safe_x}:h=420:color=black@0.30:t=fill,"
            f"drawbox=x={self.safe_x}:y=680:w={self.w-2*self.safe_x}:h=4:color={self.neon_b}@0.85:t=fill,"
            f"drawbox=x={self.safe_x}:y=1096:w={self.w-2*self.safe_x}:h=4:color={self.neon_a}@0.85:t=fill,"
            # Kicker capsule
            f"drawbox=x={self.safe_x}:y=610:w=360:h=56:color=black@0.35:t=fill,"
            f"drawbox=x={self.safe_x}:y=610:w=6:h=56:color={self.neon_b}@0.90:t=fill,"
            f"drawtext=fontfile={font_path}:text='{kicker}':"
            f"x={self.safe_x+18}:y=620:"
            f"fontsize=30:fontcolor={self.white},"
            # Title
            f"drawtext=fontfile={font_path}:text='{title}':"
            f"x=(w-text_w)/2:y=760:"
            f"fontsize=64:fontcolor={self.white},"
            # Subtitle
            f"drawtext=fontfile={font_path}:text='{sub}':"
            f"x=(w-text_w)/2:y=850:"
            f"fontsize=38:fontcolor=#E5E7EB"
        )

    def outro_filter(self, telegram_url: str, font_path: str, segment_duration: float) -> str:
        title = escape_drawtext(self.outro_title)
        sub = escape_drawtext(self.outro_subtitle)
        url = escape_drawtext(telegram_url)

        return (
            f"fps={self.fps},setpts=PTS-STARTPTS,format=yuv420p,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color={self.bg2}@1.0:t=fill,"
            f"drawbox=x=-220:y=980:w=980:h=980:color={self.neon_b}@0.18:t=fill,"
            f"drawbox=x=420:y=-260:w=980:h=980:color={self.neon_a}@0.18:t=fill,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.18:t=fill,"
            # Center card
            f"drawbox=x={self.safe_x}:y=680:w={self.w-2*self.safe_x}:h=560:color=black@0.32:t=fill,"
            f"drawbox=x={self.safe_x}:y=680:w=6:h=560:color={self.neon_b}@0.95:t=fill,"
            f"drawtext=fontfile={font_path}:text='{title}':"
            f"x=(w-text_w)/2:y=760:"
            f"fontsize=62:fontcolor={self.white},"
            f"drawtext=fontfile={font_path}:text='{sub}':"
            f"x=(w-text_w)/2:y=845:"
            f"fontsize=36:fontcolor=#E5E7EB,"
            # URL as pill button
            f"drawbox=x={(self.w-820)//2}:y=940:w=820:h=84:color=black@0.40:t=fill,"
            f"drawbox=x={(self.w-820)//2}:y=940:w=820:h=4:color={self.neon_c}@0.90:t=fill,"
            f"drawtext=fontfile={font_path}:text='{url}':"
            f"x=(w-text_w)/2:y=960:"
            f"fontsize=40:fontcolor={self.neon_b}"
        )

    # ---------- GAME OVERLAY ----------
    def game_overlay_filter(self, deal: Deal, font_path: str, segment_duration: float) -> str:
        title = escape_drawtext(ellipsize(deal.name, 56))
        discount_txt = escape_drawtext(f"-{deal.discount_percent} OFF")
        old_price = escape_drawtext(format_price(deal.original_price, deal.currency))
        new_price = escape_drawtext(format_price(deal.final_price, deal.currency))

        cx = self.card_x
        cy = self.card_y
        cw = self.card_w
        ch = self.card_h

        # positions inside card
        x0 = cx + self.pad_x
        y_title = cy + self.pad_y + 8
        y_discount = y_title + 92
        y_prices = y_discount + 110

        # Top ribbon (always visible area)
        top_x = 50
        top_y = 84
        top_w = 980
        top_h = 220

        # Discount pill geometry
        pill_w = 220
        pill_h = 76
        pill_x = x0
        pill_y = y_discount - 10

        # Prices
        was_y = y_prices
        now_y = y_prices + 74

        # old price strike line (approx)
        strike_x1 = x0 + 150
        strike_x2 = x0 + 520
        strike_y = was_y + 26

        return (
            # Background = blurred fill, Foreground = center crop
            "split=2[bg][fg],"
            f"[bg]scale={self.w}:{self.h}:force_original_aspect_ratio=increase,"
            f"crop={self.w}:{self.h},boxblur=22:2,eq=contrast=1.06:saturation=1.10:brightness=-0.01[bgv],"
            "[fg]crop=iw*0.90:ih:iw*0.05:0,"
            f"scale={self.w}:-2,eq=contrast=1.07:saturation=1.12:brightness=0.02[fgv],"
            "[bgv][fgv]overlay=(W-w)/2:(H-h)/2,"
            f"fps={self.fps},setpts=PTS-STARTPTS,format=yuv420p,"
            # subtle top scrim (improves readability)
            f"drawbox=x=0:y=0:w=iw:h=280:color=black@0.20:t=fill,"
            # Top headline ribbon for guaranteed visibility
            f"drawbox=x={top_x}:y={top_y}:w={top_w}:h={top_h}:color=black@0.45:t=fill,"
            f"drawbox=x={top_x}:y={top_y}:w=8:h={top_h}:color={self.neon_b}@0.95:t=fill,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{title}':"
            f"x={top_x+24}:y={top_y+26}:fontsize=44:fontcolor={self.white},"
            f"drawtext=fontfile={font_path}:expansion=none:text='{discount_txt}':"
            f"x={top_x+24}:y={top_y+110}:fontsize=58:fontcolor=#FDE047,"
            # Glass card: base + highlight + neon edge
            f"drawbox=x={cx}:y={cy}:w={cw}:h={ch}:color=black@0.38:t=fill,"
            f"drawbox=x={cx}:y={cy}:w={cw}:h=3:color={self.neon_b}@0.88:t=fill,"
            f"drawbox=x={cx}:y={cy+ch-3}:w={cw}:h=3:color={self.neon_a}@0.82:t=fill,"
            f"drawbox=x={cx}:y={cy}:w=10:h={ch}:color={self.neon_b}@0.55:t=fill,"
            # Title
            f"drawtext=fontfile={font_path}:expansion=none:text='{title}':"
            f"x={x0}:y={y_title}:"
            f"fontsize={self.title_fs}:fontcolor={self.white},"
            # Discount pill (capsule feel via 2 layers)
            f"drawbox=x={pill_x}:y={pill_y}:w={pill_w}:h={pill_h}:color=black@0.45:t=fill,"
            f"drawbox=x={pill_x}:y={pill_y}:w=8:h={pill_h}:color={self.neon_c}@0.95:t=fill,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{discount_txt}':"
            f"x={pill_x+18}:y={pill_y+14}:"
            f"fontsize={self.discount_fs}:fontcolor=#E5E7EB,"
            # WAS row
            f"drawtext=fontfile={font_path}:expansion=none:text='WAS':"
            f"x={x0}:y={was_y}:"
            f"fontsize={self.meta_fs}:fontcolor=#9CA3AF,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{old_price}':"
            f"x={x0+140}:y={was_y-8}:"
            f"fontsize={self.price_fs}:fontcolor=#D1D5DB,"
            # Strike-through for old price
            f"drawbox=x={strike_x1}:y={strike_y}:w={strike_x2-strike_x1}:h=4:color=#D1D5DB@0.65:t=fill,"
            # NOW row
            f"drawtext=fontfile={font_path}:expansion=none:text='NOW':"
            f"x={x0}:y={now_y}:"
            f"fontsize={self.meta_fs}:fontcolor=#86EFAC,"
            f"drawtext=fontfile={font_path}:expansion=none:text='{new_price}':"
            f"x={x0+140}:y={now_y-8}:"
            f"fontsize={self.price_fs+6}:fontcolor={self.neon_c}"
        )


# Backward compatibility for any older imports.
ShortsDesignV2 = ShortsDesign
