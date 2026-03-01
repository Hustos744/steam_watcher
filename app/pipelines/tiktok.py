from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.pipelines.shorts_design import ShortsDesign
from app.steam import Deal


class TikTokPipeline:
    def __init__(
        self,
        output_dir: str,
        telegram_url: str,
        per_game_seconds: int = 4,
        intro_seconds: int = 3,
        outro_seconds: int = 3,
        trailer_fallback_start_seconds: float = 8.0,
        timezone_name: str = "Europe/Kyiv",
        font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        self.output_dir = Path(output_dir)
        self.telegram_url = telegram_url
        self.per_game_seconds = max(per_game_seconds, 2)
        self.intro_seconds = max(intro_seconds, 2)
        self.outro_seconds = max(outro_seconds, 2)
        self.trailer_fallback_start_seconds = max(trailer_fallback_start_seconds, 0.0)
        self.tz = ZoneInfo(timezone_name)
        self.font_path = font_path

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.marker_path = self.output_dir / ".last_daily_video_date"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.design = ShortsDesign()
        self.ffmpeg_segment_timeout_seconds = 60
        self.ffmpeg_concat_timeout_seconds = 90
        self.transition_seconds = 0.35

    def should_generate_today(self) -> bool:
        today = datetime.now(self.tz).strftime("%Y-%m-%d")
        if not self.marker_path.exists():
            return True
        last_date = self.marker_path.read_text(encoding="utf-8").strip()
        return last_date != today

    def _mark_generated_today(self) -> None:
        today = datetime.now(self.tz).strftime("%Y-%m-%d")
        self.marker_path.write_text(today, encoding="utf-8")

    def _build_intro(self, out_path: Path, date_str: str) -> None:
        vf = self.design.intro_filter(
            date_str=date_str,
            font_path=self.font_path,
            segment_duration=self.intro_seconds,
        )
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=1080x1920:d={self.intro_seconds}",
            "-vf",
            vf,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=self.ffmpeg_segment_timeout_seconds)

    def _build_outro(self, out_path: Path) -> None:
        vf = self.design.outro_filter(
            telegram_url=self.telegram_url,
            font_path=self.font_path,
            segment_duration=self.outro_seconds,
        )
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=1080x1920:d={self.outro_seconds}",
            "-vf",
            vf,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=self.ffmpeg_segment_timeout_seconds)

    def _build_overlay_filter(self, deal: Deal) -> str:
        return self.design.game_overlay_filter(
            deal=deal,
            font_path=self.font_path,
            segment_duration=self.per_game_seconds,
        )

    def _build_game_segment_from_trailer(self, trailer_url: str, deal: Deal, out_path: Path) -> None:
        vf = self._build_overlay_filter(deal)
        start_offset = self._compute_trailer_start_offset(trailer_url)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            trailer_url,
            "-ss",
            f"{start_offset:.2f}",
            "-t",
            str(self.per_game_seconds),
            "-vf",
            vf,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=self.ffmpeg_segment_timeout_seconds)
        self._assert_segment_has_video(out_path)

    def _compute_trailer_start_offset(self, trailer_url: str) -> float:
        duration = self._probe_duration_seconds(trailer_url)
        if duration is None or duration <= self.per_game_seconds:
            return self.trailer_fallback_start_seconds
        return max((duration - self.per_game_seconds) / 2.0, 0.0)

    @staticmethod
    def _probe_duration_seconds(media_url: str) -> float | None:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_url,
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
            raw = (result.stdout or "").strip()
            if not raw:
                return None
            value = float(raw)
            if value > 0:
                return value
        except Exception:
            return None
        return None

    @staticmethod
    def _assert_segment_has_video(path: Path, min_seconds: float = 0.5) -> None:
        duration = TikTokPipeline._probe_duration_seconds(str(path))
        if duration is None or duration < min_seconds:
            raise RuntimeError(f"Generated segment is empty or too short: {path} (duration={duration})")

    def _concat_with_transitions(self, segments: list[Path], out_file: Path) -> None:
        if len(segments) == 1:
            shutil.copyfile(segments[0], out_file)
            return

        durations: list[float] = []
        for seg in segments:
            dur = self._probe_duration_seconds(str(seg))
            durations.append(dur if dur and dur > 0 else 0.0)

        min_duration = min(durations) if durations else 0.0
        transition = max(min(self.transition_seconds, min_duration / 3 if min_duration > 0 else 0.25), 0.1)

        command: list[str] = ["ffmpeg", "-y"]
        for seg in segments:
            command.extend(["-i", str(seg)])

        filter_parts: list[str] = []
        current_label = "[0:v]"
        offset = max(durations[0] - transition, 0.0)
        for idx in range(1, len(segments)):
            out_label = f"[v{idx}]"
            filter_parts.append(
                f"{current_label}[{idx}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}{out_label}"
            )
            current_label = out_label
            if idx < len(segments) - 1:
                offset += max(durations[idx] - transition, 0.0)

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                current_label,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-pix_fmt",
                "yuv420p",
                "-an",
                "-movflags",
                "+faststart",
                str(out_file),
            ]
        )
        subprocess.run(command, check=True, capture_output=True, timeout=self.ffmpeg_concat_timeout_seconds)

    def generate_daily_video(self, deals_with_trailers: list[tuple[Deal, list[str]]]) -> Path | None:
        if not deals_with_trailers:
            return None

        date_obj = datetime.now(self.tz)
        date_str = date_obj.strftime("%Y-%m-%d")
        out_file = self.output_dir / f"steam_discounts_{date_str}.mp4"
        temp_dir = self.output_dir / f".tmp_{date_str}_{date_obj.strftime('%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        segments: list[Path] = []
        try:
            intro = temp_dir / "intro.mp4"
            self._build_intro(intro, date_str)
            segments.append(intro)

            built_game_segments = 0
            for idx, (deal, trailer_urls) in enumerate(deals_with_trailers, start=1):
                seg = temp_dir / f"game_{idx:03d}.mp4"
                built = False
                for trailer_url in trailer_urls:
                    self.logger.info("Daily segment build start: appid=%s url=%s", deal.appid, trailer_url)
                    try:
                        self._build_game_segment_from_trailer(trailer_url, deal, seg)
                        built = True
                        self.logger.info("Daily segment build ok: appid=%s", deal.appid)
                        break
                    except subprocess.TimeoutExpired:
                        self.logger.warning(
                            "Trailer segment timeout for appid=%s url=%s",
                            deal.appid,
                            trailer_url,
                        )
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(
                            "Trailer segment failed for appid=%s url=%s code=%s",
                            deal.appid,
                            trailer_url,
                            e.returncode,
                        )
                    except RuntimeError as e:
                        self.logger.warning(
                            "Trailer segment empty for appid=%s url=%s: %s",
                            deal.appid,
                            trailer_url,
                            e,
                        )
                if not built:
                    self.logger.warning("All trailers failed for appid=%s. Skipping game in daily video.", deal.appid)
                    continue
                segments.append(seg)
                built_game_segments += 1

            outro = temp_dir / "outro.mp4"
            self._build_outro(outro)
            segments.append(outro)

            # Intro + outro only (no game segments) is not useful.
            if len(segments) <= 2:
                return None

            self._concat_with_transitions(segments, out_file)
            self.logger.info("Daily video concat done. game_segments=%s output=%s", built_game_segments, out_file)
            self._mark_generated_today()
            return out_file
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
