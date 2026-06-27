from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.storage.base import ArticleRecord
from src.storage.local import LocalStorageBackend


def test_sync_sources_creates_and_updates(tmp_storage_paths: tuple[Path, Path]) -> None:
    s3_path, rds_path = tmp_storage_paths
    storage = LocalStorageBackend(s3_path, rds_path)

    ids = storage.sync_sources(
        [
            {
                "name": "Example",
                "base_url": "https://example.com",
                "enabled": True,
                "scrape_frequency": "daily",
            }
        ]
    )
    assert ids["https://example.com"] == 1

    ids_again = storage.sync_sources(
        [
            {
                "name": "Example Updated",
                "base_url": "https://example.com",
                "enabled": True,
                "scrape_frequency": "hourly",
            }
        ]
    )
    assert ids_again["https://example.com"] == 1

    rows = storage._read_rows("sources")
    assert rows[0]["name"] == "Example Updated"
    assert rows[0]["scrape_frequency"] == "hourly"


def test_save_html_and_article(tmp_storage_paths: tuple[Path, Path]) -> None:
    s3_path, rds_path = tmp_storage_paths
    storage = LocalStorageBackend(s3_path, rds_path)
    storage.sync_sources(
        [{"name": "Example", "base_url": "https://example.com", "enabled": True}]
    )

    html = "<html><title>Test</title></html>"
    content_hash = "abc123" * 8
    path = storage.save_html(1, "https://example.com", html, content_hash)
    assert path.startswith("raw/1/")
    assert (s3_path / path).read_text(encoding="utf-8") == html

    scraped_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    record = storage.save_article(
        ArticleRecord(
            article_id=0,
            source_id=1,
            url="https://example.com",
            title="Test",
            published_at=None,
            scraped_at=scraped_at,
            content_hash=content_hash,
            s3_raw_html_path=path,
        )
    )
    assert record.article_id == 1
    assert storage.url_exists("https://example.com")
    assert "https://example.com" in storage.get_seen_urls()


def test_scrape_run_lifecycle(tmp_storage_paths: tuple[Path, Path]) -> None:
    s3_path, rds_path = tmp_storage_paths
    storage = LocalStorageBackend(s3_path, rds_path)

    run_id = storage.start_run(1)
    storage.finish_run(run_id, "success")

    rows = storage._read_rows("scrape_runs")
    assert len(rows) == 1
    assert rows[0]["run_id"] == "1"
    assert rows[0]["status"] == "success"
    assert rows[0]["finished_at"] != ""
