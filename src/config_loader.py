"""Configuration loading for OSA ingestion scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StorageSettings:
    mode: str = "local"
    local_s3_path: str = "data/s3"
    local_rds_path: str = "data/rds"


@dataclass
class Settings:
    headless: bool = True
    page_timeout_ms: int = 30000
    delay_between_requests_ms: int = 2000
    max_listing_pages: int = 5
    max_articles_per_source: int | None = None
    browser_channel: str | None = "chrome"
    use_persistent_profile: bool = True
    browser_profile_dir: str = "data/browser-profile"
    browser_cdp_url: str | None = None
    user_agent: str | None = None
    storage: StorageSettings = field(default_factory=StorageSettings)


@dataclass
class DirectSource:
    name: str
    url: str
    enabled: bool = True
    scrape_frequency: str = "daily"


@dataclass
class MetaSource:
    name: str
    type: str
    enabled: bool = True
    url: str | None = None
    search_terms: list[str] = field(default_factory=list)
    scrape_frequency: str = "daily"


@dataclass
class AppConfig:
    search_terms: list[str] = field(default_factory=list)
    direct_sources: list[DirectSource] = field(default_factory=list)
    meta_sources: list[MetaSource] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}

    settings_raw = raw.get("settings") or {}
    storage_raw = settings_raw.get("storage") or {}

    settings = Settings(
        headless=bool(settings_raw.get("headless", True)),
        page_timeout_ms=int(settings_raw.get("page_timeout_ms", 30000)),
        delay_between_requests_ms=int(
            settings_raw.get("delay_between_requests_ms", 2000)
        ),
        max_listing_pages=int(settings_raw.get("max_listing_pages", 5)),
        max_articles_per_source=settings_raw.get("max_articles_per_source"),
        browser_channel=settings_raw.get("browser_channel", "chrome"),
        use_persistent_profile=bool(settings_raw.get("use_persistent_profile", True)),
        browser_profile_dir=str(
            settings_raw.get("browser_profile_dir", "data/browser-profile")
        ),
        browser_cdp_url=settings_raw.get("browser_cdp_url"),
        user_agent=settings_raw.get("user_agent"),
        storage=StorageSettings(
            mode=str(storage_raw.get("mode", "local")),
            local_s3_path=str(storage_raw.get("local_s3_path", "data/s3")),
            local_rds_path=str(storage_raw.get("local_rds_path", "data/rds")),
        ),
    )

    direct_sources = [
        DirectSource(
            name=item["name"],
            url=item["url"],
            enabled=bool(item.get("enabled", True)),
            scrape_frequency=str(item.get("scrape_frequency", "daily")),
        )
        for item in raw.get("direct_sources") or []
    ]

    meta_sources = [
        MetaSource(
            name=item["name"],
            type=item["type"],
            enabled=bool(item.get("enabled", True)),
            url=item.get("url"),
            search_terms=list(item.get("search_terms") or []),
            scrape_frequency=str(item.get("scrape_frequency", "daily")),
        )
        for item in raw.get("meta_sources") or []
    ]

    return AppConfig(
        search_terms=list(raw.get("search_terms") or []),
        direct_sources=direct_sources,
        meta_sources=meta_sources,
        settings=settings,
    )
