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
    min_discount_percent: int
    max_posts_per_run: int

    telegram_bot_token: str
    telegram_chat_id: str
    telegram_parse_mode: str
    dry_run: bool

    sqlite_path: str
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
        min_discount_percent=int(os.getenv("MIN_DISCOUNT_PERCENT", "20")),
        max_posts_per_run=int(os.getenv("MAX_POSTS_PER_RUN", "10")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_parse_mode=os.getenv("TELEGRAM_PARSE_MODE", "HTML"),
        dry_run=_to_bool(os.getenv("DRY_RUN", "false"), default=False),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/state.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        curator_blocklist_url=os.getenv("CURATOR_BLOCKLIST_URL", ""),
        curator_blocklist_refresh_seconds=int(os.getenv("CURATOR_BLOCKLIST_REFRESH_SECONDS", "3600")),
        curator_blocklist_max_pages=int(os.getenv("CURATOR_BLOCKLIST_MAX_PAGES", "5")),
        manual_blocklist_appids=_to_int_set(os.getenv("BLOCKLIST_APPIDS", "")),
    )
