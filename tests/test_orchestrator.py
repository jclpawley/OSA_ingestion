from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config_loader import AppConfig, MetaSource, Settings, StorageSettings
from src.orchestrator import ScrapeJob, ScraperOrchestrator


@pytest.fixture
def orchestrator_with_storage(tmp_storage_paths, minimal_app_config):
    from src.storage.local import LocalStorageBackend

    s3_path, rds_path = tmp_storage_paths
    storage = LocalStorageBackend(s3_path, rds_path)
    return ScraperOrchestrator(minimal_app_config, storage), storage


def test_limit_jobs_respects_max(orchestrator_with_storage) -> None:
    orchestrator, _ = orchestrator_with_storage
    orchestrator.config.settings.max_articles_per_source = 2

    jobs = [
        ScrapeJob(url=f"https://example.com/{i}", source_id=1, allow_rescrape=False)
        for i in range(5)
    ]
    limited = orchestrator._limit_jobs(jobs)
    assert len(limited) == 2


def test_limit_jobs_returns_all_when_unset(orchestrator_with_storage) -> None:
    orchestrator, _ = orchestrator_with_storage
    orchestrator.config.settings.max_articles_per_source = None

    jobs = [
        ScrapeJob(url="https://example.com/a", source_id=1, allow_rescrape=False),
        ScrapeJob(url="https://example.com/b", source_id=1, allow_rescrape=False),
    ]
    assert orchestrator._limit_jobs(jobs) == jobs


def test_meta_base_url_for_google_news() -> None:
    config = AppConfig(
        search_terms=["online safety"],
        meta_sources=[
            MetaSource(name="GN", type="google_news", search_terms=["custom term"])
        ],
        settings=Settings(storage=StorageSettings()),
    )
    orchestrator = ScraperOrchestrator(config, MagicMock())
    base = orchestrator._meta_base_url(config.meta_sources[0])
    assert "news.google.com/search" in base
    assert "custom+term" in base


def test_run_source_skips_seen_urls(orchestrator_with_storage) -> None:
    orchestrator, storage = orchestrator_with_storage
    storage.sync_sources(
        [{"name": "Example", "base_url": "https://example.com/", "enabled": True}]
    )
    storage.save_article(
        __import__("src.storage.base", fromlist=["ArticleRecord"]).ArticleRecord(
            article_id=0,
            source_id=1,
            url="https://example.com/seen",
            title="Old",
            published_at=None,
            scraped_at=datetime.now(timezone.utc),
            content_hash="hash",
            s3_raw_html_path="raw/1/x.html",
        )
    )

    session = MagicMock()
    page = MagicMock()
    seen = storage.get_seen_urls()

    orchestrator._run_source(
        session=session,
        page=page,
        source_id=1,
        jobs=[
            ScrapeJob(
                url="https://example.com/seen",
                source_id=1,
                allow_rescrape=False,
            )
        ],
        seen_urls=seen,
        direct_urls=set(),
    )

    session.navigate.assert_not_called()


@patch("src.orchestrator.BrowserSession")
def test_run_scrapes_direct_source(mock_browser_session, orchestrator_with_storage) -> None:
    orchestrator, storage = orchestrator_with_storage

    page = MagicMock()
    session = MagicMock()
    session.page.return_value.__enter__.return_value = page
    mock_browser_session.return_value.__enter__.return_value = session

    page.content.return_value = "<html><title>Example</title></html>"

    with patch("src.sources.direct.scrape_page", return_value="<html><title>Example</title></html>"):
        orchestrator.run()

    articles = storage._read_rows("articles")
    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/"
    assert articles[0]["title"] == "Example"
