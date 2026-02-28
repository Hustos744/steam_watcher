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
    shorts_duration_seconds: int
    shorts_output_dir: str
    shorts_music_dir: str
    music_provider: str
    music_autofetch_enabled: bool
    popular_music_api_key: str
    jamendo_client_id: str
    popular_music_target_count: int
    popular_music_refresh_hours: int
    music_curator_enabled: bool
    music_curator_chat_id: str
    music_curator_hour: int
    music_curator_minute: int
    music_curator_timezone: str
    music_curator_batch_size: int
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
        shorts_duration_seconds=int(os.getenv("SHORTS_DURATION_SECONDS", "15")),
        shorts_output_dir=os.getenv("SHORTS_OUTPUT_DIR", "/app/output/shorts"),
        shorts_music_dir=os.getenv("SHORTS_MUSIC_DIR", "/app/assets/music"),
        music_provider=os.getenv("MUSIC_PROVIDER", "jamendo"),
        music_autofetch_enabled=_to_bool(os.getenv("MUSIC_AUTOFETCH_ENABLED", "false"), default=False),
        popular_music_api_key=os.getenv("POPULAR_MUSIC_API_KEY", ""),
        jamendo_client_id=os.getenv("JAMENDO_CLIENT_ID", ""),
        popular_music_target_count=int(os.getenv("POPULAR_MUSIC_TARGET_COUNT", "20")),
        popular_music_refresh_hours=int(os.getenv("POPULAR_MUSIC_REFRESH_HOURS", "24")),
        music_curator_enabled=_to_bool(os.getenv("MUSIC_CURATOR_ENABLED", "false"), default=False),
        music_curator_chat_id=os.getenv("MUSIC_CURATOR_CHAT_ID", ""),
        music_curator_hour=int(os.getenv("MUSIC_CURATOR_HOUR", "9")),
        music_curator_minute=int(os.getenv("MUSIC_CURATOR_MINUTE", "0")),
        music_curator_timezone=os.getenv("MUSIC_CURATOR_TIMEZONE", "Europe/Kyiv"),
        music_curator_batch_size=int(os.getenv("MUSIC_CURATOR_BATCH_SIZE", "3")),
        shorts_cta_telegram_url=os.getenv("SHORTS_CTA_TELEGRAM_URL", "https://t.me/your_channel"),
        shorts_font_path=os.getenv("SHORTS_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        curator_blocklist_url=os.getenv("CURATOR_BLOCKLIST_URL", ""),
        curator_blocklist_refresh_seconds=int(os.getenv("CURATOR_BLOCKLIST_REFRESH_SECONDS", "3600")),
        curator_blocklist_max_pages=int(os.getenv("CURATOR_BLOCKLIST_MAX_PAGES", "0")),
        manual_blocklist_appids=_to_int_set(os.getenv("BLOCKLIST_APPIDS", "")),
    )
