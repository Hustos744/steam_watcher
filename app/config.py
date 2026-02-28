from dataclasses import dataclass
from datetime import timezone
import os


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int_set(value: str) -> set[int]:
    if not value:
        return set()
    result: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            result.add(int(token))
    return result


@dataclass(frozen=True)
class Settings:
    steam_country: str
    steam_language: str
    poll_interval_seconds: int
    post_delay_seconds: float
    min_discount_percent: int
    max_posts_per_run: int

    telegram_bot_token: str
    telegram_chat_id: str
    telegram_parse_mode: str
    usd_to_uah_rate: float
    telegram_include_trailer: bool
    telegram_extra_images_count: int
    telegram_max_retries: int
    dry_run: bool

    database_url: str
    retention_days: int
    shorts_enabled: bool
    shorts_per_game_seconds: int
    shorts_intro_seconds: int
    shorts_outro_seconds: int
    shorts_trailer_fallback_start_seconds: float
    shorts_output_dir: str
    shorts_timezone: str
    shorts_cta_telegram_url: str
    shorts_font_path: str
    log_level: str
    curator_blocklist_url: str
    curator_blocklist_refresh_seconds: int
    curator_blocklist_max_pages: int
    manual_blocklist_appids: set[int]


    @property
    def tzinfo(self):
        return timezone.utc



def load_settings() -> Settings:
    return Settings(
        steam_country=os.getenv("STEAM_COUNTRY", "us"),
        steam_language=os.getenv("STEAM_LANGUAGE", "en"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "900")),
        post_delay_seconds=float(os.getenv("POST_DELAY_SECONDS", "1.5")),
        min_discount_percent=int(os.getenv("MIN_DISCOUNT_PERCENT", "20")),
        max_posts_per_run=int(os.getenv("MAX_POSTS_PER_RUN", "10")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_parse_mode=os.getenv("TELEGRAM_PARSE_MODE", "HTML"),
        usd_to_uah_rate=float(os.getenv("USD_TO_UAH_RATE", "41.0")),
        telegram_include_trailer=_to_bool(os.getenv("TELEGRAM_INCLUDE_TRAILER", "true"), default=True),
        telegram_extra_images_count=int(os.getenv("TELEGRAM_EXTRA_IMAGES_COUNT", "3")),
        telegram_max_retries=int(os.getenv("TELEGRAM_MAX_RETRIES", "3")),
        dry_run=_to_bool(os.getenv("DRY_RUN", "false"), default=False),
        database_url=os.getenv("DATABASE_URL", "postgresql://steam:steam@postgres:5432/steam_watcher"),
        retention_days=int(os.getenv("RETENTION_DAYS", "30")),
        shorts_enabled=_to_bool(os.getenv("SHORTS_ENABLED", "false"), default=False),
        shorts_per_game_seconds=int(os.getenv("SHORTS_PER_GAME_SECONDS", "4")),
        shorts_intro_seconds=int(os.getenv("SHORTS_INTRO_SECONDS", "3")),
        shorts_outro_seconds=int(os.getenv("SHORTS_OUTRO_SECONDS", "3")),
        shorts_trailer_fallback_start_seconds=float(os.getenv("SHORTS_TRAILER_FALLBACK_START_SECONDS", "8.0")),
        shorts_output_dir=os.getenv("SHORTS_OUTPUT_DIR", "/app/output/shorts"),
        shorts_timezone=os.getenv("SHORTS_TIMEZONE", "Europe/Kyiv"),
        shorts_cta_telegram_url=os.getenv("SHORTS_CTA_TELEGRAM_URL", "https://t.me/your_channel"),
        shorts_font_path=os.getenv("SHORTS_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        curator_blocklist_url=os.getenv("CURATOR_BLOCKLIST_URL", ""),
        curator_blocklist_refresh_seconds=int(os.getenv("CURATOR_BLOCKLIST_REFRESH_SECONDS", "3600")),
        curator_blocklist_max_pages=int(os.getenv("CURATOR_BLOCKLIST_MAX_PAGES", "0")),
        manual_blocklist_appids=_to_int_set(os.getenv("BLOCKLIST_APPIDS", "")),
    )
