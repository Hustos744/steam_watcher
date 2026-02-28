import logging
import time
from typing import List
from urllib.parse import urlsplit, urlunsplit

from app.curator_blocklist import SteamCuratorBlocklist
from app.pipelines.tiktok import TikTokPipeline
from app.repository import StateRepository
from app.steam import Deal, SteamClient
from app.telegram_client import TelegramPublisher


class DiscountWatcherService:
    def __init__(
        self,
        steam: SteamClient,
        repository: StateRepository,
        telegram: TelegramPublisher,
        min_discount_percent: int,
        max_posts_per_run: int,
        post_delay_seconds: float = 0.0,
        shorts_pipeline: TikTokPipeline | None = None,
        shorts_enabled: bool = False,
        curator_blocklist: SteamCuratorBlocklist | None = None,
        manual_blocklist_appids: set[int] | None = None,
        dry_run: bool = False,
    ):
        self.steam = steam
        self.repository = repository
        self.telegram = telegram
        self.min_discount_percent = min_discount_percent
        self.max_posts_per_run = max_posts_per_run
        self.post_delay_seconds = max(post_delay_seconds, 0.0)
        self.shorts_pipeline = shorts_pipeline
        self.shorts_enabled = shorts_enabled
        self.curator_blocklist = curator_blocklist
        self.manual_blocklist_appids = manual_blocklist_appids or set()
        self.dry_run = dry_run
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _normalize_trailer_url(url: str) -> str:
        # Steam often appends short-lived query tokens. Remove query/fragment
        # so ffmpeg can fetch stable HLS/DASH manifest URLs.
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def run_once(self) -> int:
        posted_deleted, blocked_deleted = self.repository.cleanup_expired_records()
        if posted_deleted or blocked_deleted:
            self.logger.info(
                "Retention cleanup deleted posted=%s blocked=%s",
                posted_deleted,
                blocked_deleted,
            )

        blocked_appids = set(self.repository.get_blocked_appids())
        blocked_appids.update(self.manual_blocklist_appids)
        if self.curator_blocklist is not None:
            curator_appids = self.curator_blocklist.get_appids()
            new_items = self.repository.upsert_blocked_appids(curator_appids, source="curator")
            if new_items:
                self.logger.info("Added %s new blocked appids from curator", new_items)
            blocked_appids.update(curator_appids)

        deals: List[Deal] = sorted(
            self.steam.fetch_special_deals(),
            key=lambda d: d.discount_percent,
            reverse=True,
        )

        eligible_deals: list[Deal] = []
        seen_appids: set[int] = set()
        for deal in deals:
            if deal.discount_percent < self.min_discount_percent:
                continue
            if deal.appid in blocked_appids:
                continue
            if deal.appid in seen_appids:
                continue
            seen_appids.add(deal.appid)
            eligible_deals.append(deal)

        posted = 0
        trailer_cache: dict[int, list[str]] = {}
        for deal in eligible_deals:
            if self.repository.was_posted(deal.appid, deal.discount_expiration, deal.final_price):
                continue

            caption = self.telegram.compose_caption(deal)
            if self.dry_run:
                self.logger.info("DRY RUN post for appid=%s\n%s", deal.appid, caption)
            else:
                media = None
                try:
                    media = self.steam.fetch_deal_media(deal.appid)
                    trailer_urls = []
                    if media:
                        trailer_urls = media.trailer_urls or ([] if not media.trailer_url else [media.trailer_url])
                    normalized = [self._normalize_trailer_url(u) for u in trailer_urls if u]
                    if normalized:
                        trailer_cache[deal.appid] = list(dict.fromkeys(normalized))
                except Exception:
                    self.logger.exception("Failed to fetch media for appid=%s", deal.appid)
                try:
                    self.telegram.publish_deal(deal, media=media)
                except Exception:
                    self.logger.exception("Failed to post deal: %s (appid=%s)", deal.name, deal.appid)
                    continue
                self.logger.info("Posted deal: %s (%s%%)", deal.name, deal.discount_percent)

            self.repository.mark_posted(deal.appid, deal.discount_expiration, deal.final_price)
            posted += 1
            if posted >= self.max_posts_per_run:
                break
            if not self.dry_run and self.post_delay_seconds > 0:
                time.sleep(self.post_delay_seconds)

        if not self.dry_run and self.shorts_enabled and self.shorts_pipeline is not None:
            try:
                if self.shorts_pipeline.should_generate_today():
                    daily_entries: list[tuple[Deal, list[str]]] = []
                    for deal in eligible_deals:
                        trailer_urls = trailer_cache.get(deal.appid, [])
                        if not trailer_urls:
                            try:
                                media = self.steam.fetch_deal_media(deal.appid)
                                fetched = []
                                if media:
                                    fetched = media.trailer_urls or ([] if not media.trailer_url else [media.trailer_url])
                                normalized = [self._normalize_trailer_url(u) for u in fetched if u]
                                if normalized:
                                    trailer_urls = list(dict.fromkeys(normalized))
                                    trailer_cache[deal.appid] = trailer_urls
                            except Exception:
                                self.logger.exception("Failed to fetch media for daily video appid=%s", deal.appid)
                        if trailer_urls:
                            daily_entries.append((deal, trailer_urls))
                        else:
                            self.logger.info("No trailers found for daily video appid=%s", deal.appid)

                    output = self.shorts_pipeline.generate_daily_video(daily_entries)
                    if output:
                        self.logger.info("Generated daily short video: %s", output)
                    else:
                        self.logger.info("Daily short skipped: no trailer media available")
            except Exception:
                self.logger.exception("Failed to generate daily short video")

        self.logger.info("Run completed. Posted: %s", posted)
        return posted
