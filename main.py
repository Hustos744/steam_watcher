import logging
import time

from app.config import load_settings
from app.curator_blocklist import SteamCuratorBlocklist
from app.repository import StateRepository
from app.service import DiscountWatcherService
from app.steam import SteamClient
from app.telegram_client import TelegramPublisher


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    if not settings.dry_run and (not settings.telegram_bot_token or not settings.telegram_chat_id):
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required when DRY_RUN=false")

    steam = SteamClient(country=settings.steam_country, language=settings.steam_language)
    repository = StateRepository(sqlite_path=settings.sqlite_path)
    curator_blocklist = SteamCuratorBlocklist(
        curator_url=settings.curator_blocklist_url,
        refresh_seconds=settings.curator_blocklist_refresh_seconds,
        max_pages=settings.curator_blocklist_max_pages,
    )
    telegram = TelegramPublisher(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        parse_mode=settings.telegram_parse_mode,
    )

    service = DiscountWatcherService(
        steam=steam,
        repository=repository,
        telegram=telegram,
        min_discount_percent=settings.min_discount_percent,
        max_posts_per_run=settings.max_posts_per_run,
        curator_blocklist=curator_blocklist,
        manual_blocklist_appids=settings.manual_blocklist_appids,
        dry_run=settings.dry_run,
    )

    logger = logging.getLogger("main")
    logger.info("steam_watcher started. poll_interval=%ss", settings.poll_interval_seconds)

    while True:
        try:
            service.run_once()
        except Exception:
            logger.exception("Run failed")

        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
