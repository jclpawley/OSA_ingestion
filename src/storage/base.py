"""Storage backend abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class SourceRecord:
    source_id: int
    name: str
    base_url: str
    robots_txt_status: str
    scrape_frequency: str
    enabled: bool


@dataclass
class ArticleRecord:
    article_id: int
    source_id: int
    url: str
    title: str | None
    published_at: datetime | None
    scraped_at: datetime
    content_hash: str
    s3_raw_html_path: str
    s3_text_path: str | None = None


class StorageBackend(Protocol):
    def sync_sources(self, sources: list[dict]) -> dict[str, int]: ...

    def start_run(self, source_id: int) -> int: ...

    def finish_run(
        self, run_id: int, status: str, error_message: str | None = None
    ) -> None: ...

    def url_exists(self, url: str) -> bool: ...

    def save_html(self, source_id: int, url: str, html: str, content_hash: str) -> str: ...

    def save_article(self, article: ArticleRecord) -> ArticleRecord: ...

    def get_seen_urls(self) -> set[str]: ...
