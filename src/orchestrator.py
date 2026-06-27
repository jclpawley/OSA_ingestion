"""Main scrape orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from src.browser.session import BrowserSession
from src.config_loader import AppConfig, MetaSource
from src.sources import direct as direct_source
from src.sources import google_news, link_page
from src.sources.metadata import extract_published_at, extract_title
from src.storage.base import ArticleRecord, StorageBackend
from src.utils.hash import content_hash
from src.utils.url import normalize_url

logger = logging.getLogger(__name__)


@dataclass
class ScrapeJob:
    url: str
    source_id: int
    allow_rescrape: bool


class ScraperOrchestrator:
    def __init__(self, config: AppConfig, storage: StorageBackend) -> None:
        self.config = config
        self.storage = storage

    def run(self) -> None:
        source_map = self._sync_sources()
        seen_urls = self.storage.get_seen_urls()
        direct_urls = {
            normalize_url(source.url)
            for source in self.config.direct_sources
            if source.enabled
        }

        with BrowserSession(self.config.settings) as session:
            with session.page() as page:
                for source in self.config.direct_sources:
                    if not source.enabled:
                        continue
                    self._run_source(
                        session=session,
                        page=page,
                        source_id=source_map[normalize_url(source.url)],
                        jobs=[
                            ScrapeJob(
                                url=normalize_url(source.url),
                                source_id=source_map[normalize_url(source.url)],
                                allow_rescrape=True,
                            )
                        ],
                        seen_urls=seen_urls,
                        direct_urls=direct_urls,
                    )

                for source in self.config.meta_sources:
                    if not source.enabled:
                        continue
                    base_url = self._meta_base_url(source)
                    source_id = source_map[base_url]

                    if source.type == "link_page":
                        self._run_link_page_meta_source(
                            session=session,
                            page=page,
                            source=source,
                            source_id=source_id,
                            seen_urls=seen_urls,
                        )
                        continue

                    article_urls = self._expand_meta_source(session, page, source)
                    jobs = [
                        ScrapeJob(url=url, source_id=source_id, allow_rescrape=False)
                        for url in article_urls
                    ]
                    jobs = self._limit_jobs(jobs)
                    self._run_source(
                        session=session,
                        page=page,
                        source_id=source_id,
                        jobs=jobs,
                        seen_urls=seen_urls,
                        direct_urls=direct_urls,
                    )

    def _sync_sources(self) -> dict[str, int]:
        entries: list[dict] = []
        for source in self.config.direct_sources:
            entries.append(
                {
                    "name": source.name,
                    "base_url": normalize_url(source.url),
                    "scrape_frequency": source.scrape_frequency,
                    "enabled": source.enabled,
                }
            )
        for source in self.config.meta_sources:
            entries.append(
                {
                    "name": source.name,
                    "base_url": self._meta_base_url(source),
                    "scrape_frequency": source.scrape_frequency,
                    "enabled": source.enabled,
                }
            )
        return self.storage.sync_sources(entries)

    def _meta_base_url(self, source: MetaSource) -> str:
        if source.type == "google_news":
            terms = source.search_terms or self.config.search_terms
            term = terms[0] if terms else "online safety"
            return normalize_url(google_news.build_search_url(term))
        if source.url:
            return normalize_url(source.url)
        raise ValueError(f"Meta source '{source.name}' requires a url")

    def _expand_meta_source(
        self,
        session: BrowserSession,
        page,
        source: MetaSource,
    ) -> list[str]:
        logger.info("Expanding meta source: %s (%s)", source.name, source.type)
        if source.type == "link_page":
            if not source.url:
                raise ValueError(f"Meta source '{source.name}' requires a url")
            return link_page.collect_article_urls(
                session, page, source.url, max_pages=self.config.settings.max_listing_pages
            )
        if source.type == "google_news":
            terms = source.search_terms or self.config.search_terms
            if not terms:
                raise ValueError(f"Meta source '{source.name}' requires search terms")
            urls: list[str] = []
            for term in terms:
                urls.extend(google_news.collect_article_urls(session, page, term))
            return sorted(set(urls))
        raise ValueError(f"Unsupported meta source type: {source.type}")

    def _limit_jobs(self, jobs: list[ScrapeJob]) -> list[ScrapeJob]:
        limit = self.config.settings.max_articles_per_source
        if limit is None or limit <= 0:
            return jobs
        return jobs[:limit]

    def _run_link_page_meta_source(
        self,
        session: BrowserSession,
        page,
        source: MetaSource,
        source_id: int,
        seen_urls: set[str],
    ) -> None:
        if not source.url:
            raise ValueError(f"Meta source '{source.name}' requires a url")

        logger.info("Scraping meta source via listing clicks: %s", source.name)
        run_id = self.storage.start_run(source_id)
        errors: list[str] = []
        scraped_count = 0

        try:
            articles = link_page.scrape_articles_via_listing(
                session=session,
                page=page,
                start_url=source.url,
                max_pages=self.config.settings.max_listing_pages,
                max_articles=self.config.settings.max_articles_per_source,
                seen_urls=seen_urls,
            )

            for article_url, html in articles:
                try:
                    html_hash = content_hash(html)
                    scraped_at = datetime.now(timezone.utc)
                    html_path = self.storage.save_html(
                        source_id=source_id,
                        url=article_url,
                        html=html,
                        content_hash=html_hash,
                    )
                    article = self.storage.save_article(
                        ArticleRecord(
                            article_id=0,
                            source_id=source_id,
                            url=article_url,
                            title=extract_title(html),
                            published_at=extract_published_at(html),
                            scraped_at=scraped_at,
                            content_hash=html_hash,
                            s3_raw_html_path=html_path,
                        )
                    )
                    scraped_count += 1
                    logger.info(
                        "Saved article %s -> %s",
                        article_url,
                        article.s3_raw_html_path,
                    )
                except Exception as exc:
                    message = f"{article_url}: {exc}"
                    logger.exception("Failed to save %s", article_url)
                    errors.append(message)

            status = "success" if not errors else ("partial" if scraped_count else "failed")
            self.storage.finish_run(run_id, status, "; ".join(errors) if errors else None)
        except Exception as exc:
            self.storage.finish_run(run_id, "failed", str(exc))
            logger.exception("Link page scrape failed for %s", source.name)

    def _run_source(
        self,
        session: BrowserSession,
        page,
        source_id: int,
        jobs: list[ScrapeJob],
        seen_urls: set[str],
        direct_urls: set[str],
    ) -> None:
        run_id = self.storage.start_run(source_id)
        errors: list[str] = []
        scraped_count = 0

        try:
            for job in jobs:
                if not job.allow_rescrape and job.url in seen_urls:
                    logger.info("Skipping already seen URL: %s", job.url)
                    continue
                if (
                    not job.allow_rescrape
                    and job.url not in direct_urls
                    and self.storage.url_exists(job.url)
                ):
                    logger.info("Skipping URL already in storage: %s", job.url)
                    seen_urls.add(job.url)
                    continue

                try:
                    html = direct_source.scrape_page(session, page, job.url)
                    html_hash = content_hash(html)
                    scraped_at = datetime.now(timezone.utc)
                    html_path = self.storage.save_html(
                        source_id=job.source_id,
                        url=job.url,
                        html=html,
                        content_hash=html_hash,
                    )
                    article = self.storage.save_article(
                        ArticleRecord(
                            article_id=0,
                            source_id=job.source_id,
                            url=job.url,
                            title=extract_title(html),
                            published_at=extract_published_at(html),
                            scraped_at=scraped_at,
                            content_hash=html_hash,
                            s3_raw_html_path=html_path,
                        )
                    )
                    seen_urls.add(job.url)
                    scraped_count += 1
                    logger.info(
                        "Scraped article %s -> %s",
                        job.url,
                        article.s3_raw_html_path,
                    )
                except Exception as exc:
                    message = f"{job.url}: {exc}"
                    logger.exception("Failed to scrape %s", job.url)
                    errors.append(message)

                session.delay()

            status = "success" if not errors else ("partial" if scraped_count else "failed")
            error_message = "; ".join(errors) if errors else None
            self.storage.finish_run(run_id, status, error_message)
        except Exception as exc:
            self.storage.finish_run(run_id, "failed", str(exc))
            raise
