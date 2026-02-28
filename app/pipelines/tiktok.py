from __future__ import annotations

import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.steam import Deal, DealMedia


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return safe[:80] if safe else "game"


def _escape_drawtext(text: str) -> str:
    # ffmpeg drawtext escaping
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def _format_price(cents: int, currency: str) -> str:
    if cents <= 0:
        return "Free"
    return f"{cents / 100:.2f} {currency}"


class TikTokPipeline:
    def __init__(
        self,
        output_dir: str,
        music_dir: str,
        telegram_url: str,
        duration_seconds: int = 15,
        font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        self.output_dir = Path(output_dir)
        self.music_dir = Path(music_dir)
        self.telegram_url = telegram_url
        self.duration_seconds = max(10, duration_seconds)
        self.font_path = font_path

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _pick_music_file(self) -> Path | None:
        preferred_marker = self.music_dir / ".preferred_track.txt"
        if preferred_marker.exists():
            preferred_name = preferred_marker.read_text(encoding="utf-8").strip()
            if preferred_name:
                preferred_path = self.music_dir / preferred_name
                if preferred_path.exists() and preferred_path.is_file():
                    return preferred_path

        if not self.music_dir.exists():
            return None
        candidates = []
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.flac", "*.ogg"):
            candidates.extend(self.music_dir.glob(ext))
        if not candidates:
            return None
        return random.choice(candidates)

    def _build_filter_complex(self, deal: Deal) -> str:
        title = _escape_drawtext(deal.name)
        discount = _escape_drawtext(f"-{deal.discount_percent}% OFF")
        old_price = _escape_drawtext(_format_price(deal.original_price, deal.currency))
        new_price = _escape_drawtext(_format_price(deal.final_price, deal.currency))
        tg_line = _escape_drawtext("Like + Follow + Telegram")

        # 1080x1920 vertical video with overlay text + CTA in last 3 seconds.
        return (
            "[0:v]"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "fps=30,"
            "format=yuv420p,"
            f"trim=duration={self.duration_seconds},"
            "setpts=PTS-STARTPTS[base];"
            "[base]"
            "drawbox=x=40:y=80:w=1000:h=360:color=black@0.45:t=fill,"
            f"drawtext=fontfile={self.font_path}:text='{title}':x=70:y=120:fontsize=58:fontcolor=white,"
            f"drawtext=fontfile={self.font_path}:text='{discount}':x=70:y=200:fontsize=76:fontcolor=yellow,"
            f"drawtext=fontfile={self.font_path}:text='Old\\: {old_price}':x=70:y=290:fontsize=42:fontcolor=white,"
            f"drawtext=fontfile={self.font_path}:text='Now\\: {new_price}':x=70:y=340:fontsize=52:fontcolor=lime,"
            f"drawbox=enable='gte(t,{self.duration_seconds - 3})':x=0:y=1480:w=1080:h=440:color=black@0.70:t=fill,"
            f"drawtext=enable='gte(t,{self.duration_seconds - 2.8})':fontfile={self.font_path}:"
            "text='LIKE + FOLLOW':x=(w-text_w)/2:y=1560:fontsize=72:fontcolor=white,"
            f"drawtext=enable='gte(t,{self.duration_seconds - 2.0})':fontfile={self.font_path}:"
            f"text='{tg_line}':x=(w-text_w)/2:y=1650:fontsize=44:fontcolor=yellow,"
            f"drawtext=enable='gte(t,{self.duration_seconds - 1.2})':fontfile={self.font_path}:"
            f"text='{_escape_drawtext(self.telegram_url)}':x=(w-text_w)/2:y=1710:fontsize=36:fontcolor=cyan[vout];"
            "[1:a]"
            f"atrim=duration={self.duration_seconds},"
            "afade=t=in:st=0:d=0.6,"
            f"afade=t=out:st={self.duration_seconds - 1.0}:d=1.0,"
            "volume=1.0[aout]"
        )

    def generate_for_deal(self, deal: Deal, media: DealMedia | None) -> Path | None:
        if not media or not media.trailer_url:
            return None

        music_file = self._pick_music_file()
        if not music_file:
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"{deal.appid}_{_sanitize_filename(deal.name)}_{timestamp}.mp4"

        filter_complex = self._build_filter_complex(deal)
        command = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            media.trailer_url,
            "-stream_loop",
            "-1",
            "-i",
            str(music_file),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_file),
        ]

        subprocess.run(command, check=True, capture_output=True)
        return output_file
