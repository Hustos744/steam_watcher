from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import requests

STEAM_FEATURED_CATEGORIES_URL = "https://store.steampowered.com/api/featuredcategories"
STEAM_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


@dataclass(frozen=True)
class Deal:
    appid: int
    name: str
    header_image: str
    original_price: int
    final_price: int
    currency: str
    discount_percent: int
    discount_expiration: int

    @property
    def expires_at_utc(self) -> datetime:
        return datetime.fromtimestamp(self.discount_expiration, tz=timezone.utc)

    @property
    def store_url(self) -> str:
        return f"https://store.steampowered.com/app/{self.appid}/"


@dataclass(frozen=True)
class DealMedia:
    trailer_url: str | None
    image_urls: list[str]


class SteamClient:
    def __init__(self, country: str, language: str, timeout_seconds: int = 15):
        self.country = country
        self.language = language
        self.timeout_seconds = timeout_seconds

    def fetch_special_deals(self) -> Iterable[Deal]:
        response = requests.get(
            STEAM_FEATURED_CATEGORIES_URL,
            params={"cc": self.country, "l": self.language},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        items = payload.get("specials", {}).get("items", [])
        for item in items:
            discount = int(item.get("discount_percent", 0) or 0)
            if discount <= 0:
                continue
            expiration = int(item.get("discount_expiration", 0) or 0)
            if expiration <= 0:
                continue

            yield Deal(
                appid=int(item["id"]),
                name=item.get("name", "Unknown"),
                header_image=item.get("header_image", ""),
                original_price=int(item.get("original_price", 0) or 0),
                final_price=int(item.get("final_price", 0) or 0),
                currency=item.get("currency", "USD"),
                discount_percent=discount,
                discount_expiration=expiration,
            )

    def fetch_deal_media(self, appid: int, max_images: int = 4) -> DealMedia:
        response = requests.get(
            STEAM_APP_DETAILS_URL,
            params={"appids": appid, "cc": self.country, "l": self.language},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        app_data = payload.get(str(appid), {})
        data = app_data.get("data", {}) if app_data.get("success") else {}

        trailer_url: str | None = None
        movies = data.get("movies", []) or []
        for movie in movies:
            mp4 = movie.get("mp4", {}) or {}
            trailer_url = mp4.get("max") or mp4.get("480")
            if trailer_url:
                break

        image_urls: list[str] = []
        screenshots = data.get("screenshots", []) or []
        for shot in screenshots:
            url = shot.get("path_full") or shot.get("path_thumbnail")
            if url and url not in image_urls:
                image_urls.append(url)
            if len(image_urls) >= max_images:
                break

        return DealMedia(trailer_url=trailer_url, image_urls=image_urls)
