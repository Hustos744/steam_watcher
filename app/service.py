import logging
from typing import List

from app.curator_blocklist import SteamCuratorBlocklist
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
        curator_blocklist: SteamCuratorBlocklist | None = None,
        manual_blocklist_appids: set[int] | None = None,
        dry_run: bool = False,
    ):
        self.steam = steam
        self.repository = repository
        self.telegram = telegram
        self.min_discount_percent = min_discount_percent
        self.max_posts_per_run = max_posts_per_run
        self.curator_blocklist = curator_blocklist
        self.manual_blocklist_appids = manual_blocklist_appids or set()
        self.dry_run = dry_run
        self.logger = logging.getLogger(self.__class__.__name__)

    def run_once(self) -> int:
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

        posted = 0
        for deal in deals:
            if deal.discount_percent < self.min_discount_percent:
                continue
            if deal.appid in blocked_appids:
                self.logger.info("Skipped blocked game: %s (appid=%s)", deal.name, deal.appid)
                continue
            if self.repository.was_posted(deal.appid, deal.discount_expiration, deal.final_price):
                continue

            caption = self.telegram.compose_caption(deal)
            if self.dry_run:
                self.logger.info("DRY RUN post for appid=%s\n%s", deal.appid, caption)
            else:
                self.telegram.publish_deal(deal)
                self.logger.info("Posted deal: %s (%s%%)", deal.name, deal.discount_percent)

            self.repository.mark_posted(deal.appid, deal.discount_expiration, deal.final_price)
            posted += 1
            if posted >= self.max_posts_per_run:
                break

        self.logger.info("Run completed. Posted: %s", posted)
        return posted
