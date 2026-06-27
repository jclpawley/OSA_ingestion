"""Meta source: extract article links from listing pages (e.g. Sky News topics)."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from playwright.sync_api import Page

from src.browser.session import BrowserSession, _is_access_denied
from src.utils.url import normalize_url, resolve_href

logger = logging.getLogger(__name__)


def _is_sky_article(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("news.sky.com"):
        return False
    return "/story/" in parsed.path


def _topic_page_urls(start_url: str, max_pages: int = 5) -> list[str]:
    normalized = normalize_url(start_url)
    match = re.search(r"(/topic/[^/]+/\d+)", normalized)
    if not match:
        return [normalized]

    base = normalized[: match.end()]
    prefix = base.rsplit("/", 1)[0]
    start_page = int(base.rsplit("/", 1)[-1])
    return [f"{prefix}/{page_num}" for page_num in range(start_page, start_page + max_pages)]


def extract_links_from_page(page: Page, listing_url: str) -> set[str]:
    anchors = page.locator("a[href]")
    count = anchors.count()
    links: set[str] = set()

    for index in range(count):
        href = anchors.nth(index).get_attribute("href")
        resolved = resolve_href(listing_url, href or "")
        if resolved and _is_sky_article(resolved):
            links.add(resolved)

    return links


def collect_article_urls(
    session: BrowserSession,
    page: Page,
    start_url: str,
    max_pages: int = 5,
) -> list[str]:
    collected: set[str] = set()

    for listing_url in _topic_page_urls(start_url, max_pages=max_pages):
        session.navigate(page, listing_url)
        page_links = extract_links_from_page(page, listing_url)
        if not page_links and listing_url != normalize_url(start_url):
            break
        collected.update(page_links)
        session.delay()

    return sorted(collected)


def scrape_articles_via_listing(
    session: BrowserSession,
    page: Page,
    start_url: str,
    max_pages: int,
    max_articles: int | None,
    seen_urls: set[str],
) -> list[tuple[str, str]]:
    """Scrape articles by clicking story links on the listing page (same as a human)."""
    scraped: list[tuple[str, str]] = []

    for listing_url in _topic_page_urls(start_url, max_pages=max_pages):
        session.navigate(page, listing_url)
        attempts = 0

        while True:
            if max_articles is not None and len(scraped) >= max_articles:
                return scraped
            if max_articles is not None and attempts >= max_articles:
                break

            article_urls = sorted(extract_links_from_page(page, listing_url))
            next_url = next((url for url in article_urls if url not in seen_urls), None)
            if not next_url:
                break

            attempts += 1

            if not session.click_story_link(page, next_url):
                seen_urls.add(next_url)
                session.return_to_listing(page, listing_url)
                session.delay()
                continue

            if _is_access_denied(page):
                logger.warning("Access denied after click: %s", next_url)
                seen_urls.add(next_url)
                session.return_to_listing(page, listing_url)
                session.delay()
                continue

            final_url = normalize_url(page.url)
            html = page.content()
            scraped.append((final_url, html))
            seen_urls.add(final_url)
            logger.info("Scraped article via click: %s", final_url)

            session.return_to_listing(page, listing_url)
            session.delay()

        session.delay()

    return scraped
