import logging
import threading
import time

from app.config import load_settings
from app.curator_blocklist import SteamCuratorBlocklist
from app.pipelines.music_downloader import MusicAutoDownloader
from app.pipelines.music_curator_bot import MusicCuratorBot
from app.pipelines.music_provider import build_music_provider
from app.pipelines.tiktok import TikTokPipeline
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
    repository = StateRepository(
        database_url=settings.database_url,
        retention_days=settings.retention_days,
    )
    curator_blocklist = SteamCuratorBlocklist(
        curator_url=settings.curator_blocklist_url,
        refresh_seconds=settings.curator_blocklist_refresh_seconds,
        max_pages=settings.curator_blocklist_max_pages,
    )
    telegram = TelegramPublisher(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        parse_mode=settings.telegram_parse_mode,
        usd_to_uah_rate=settings.usd_to_uah_rate,
        include_trailer=settings.telegram_include_trailer,
        extra_images_count=settings.telegram_extra_images_count,
        max_retries=settings.telegram_max_retries,
    )
    shorts_pipeline = TikTokPipeline(
        output_dir=settings.shorts_output_dir,
        music_dir=settings.shorts_music_dir,
        telegram_url=settings.shorts_cta_telegram_url,
        duration_seconds=settings.shorts_duration_seconds,
        font_path=settings.shorts_font_path,
    )
    music_provider = build_music_provider(
        provider=settings.music_provider,
        pixabay_api_key=settings.popular_music_api_key,
        jamendo_client_id=settings.jamendo_client_id,
    )
    music_downloader = MusicAutoDownloader(
        music_dir=settings.shorts_music_dir,
        provider=music_provider,
        enabled=settings.music_autofetch_enabled,
        target_count=settings.popular_music_target_count,
        refresh_hours=settings.popular_music_refresh_hours,
    )
    music_curator_bot = MusicCuratorBot(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.music_curator_chat_id,
        provider=music_provider,
        music_dir=settings.shorts_music_dir,
        timezone_name=settings.music_curator_timezone,
        morning_hour=settings.music_curator_hour,
        morning_minute=settings.music_curator_minute,
        batch_size=settings.music_curator_batch_size,
    )

    service = DiscountWatcherService(
        steam=steam,
        repository=repository,
        telegram=telegram,
        min_discount_percent=settings.min_discount_percent,
        max_posts_per_run=settings.max_posts_per_run,
        post_delay_seconds=settings.post_delay_seconds,
        shorts_pipeline=shorts_pipeline,
        shorts_enabled=settings.shorts_enabled,
        curator_blocklist=curator_blocklist,
        manual_blocklist_appids=settings.manual_blocklist_appids,
        dry_run=settings.dry_run,
    )

    logger = logging.getLogger("main")
    logger.info("steam_watcher started. poll_interval=%ss", settings.poll_interval_seconds)
    stop_event = threading.Event()

    if settings.music_curator_enabled:
        t = threading.Thread(target=music_curator_bot.run_forever, args=(stop_event,), daemon=True)
        t.start()
        logger.info("Music curator bot thread started")

    while True:
        try:
            music_downloader.refresh_if_needed()
            service.run_once()
        except Exception:
            logger.exception("Run failed")

        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
