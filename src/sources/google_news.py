"""Meta source: Google News search results."""

from __future__ import annotations

from urllib.parse import quote_plus

from playwright.sync_api import Page

from src.browser.session import BrowserSession
from src.utils.url import normalize_url, resolve_href


def build_search_url(search_term: str) -> str:
    query = quote_plus(search_term)
    return (
        f"https://news.google.com/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"
    )


def _unwrap_google_news_href(href: str) -> str:
    if href.startswith("./"):
        href = f"https://news.google.com{href[1:]}"
    return normalize_url(href)


def collect_article_urls(
    session: BrowserSession,
    page: Page,
    search_term: str,
) -> list[str]:
    search_url = build_search_url(search_term)
    session.navigate(page, search_url)

    article_links = page.locator("a[href*='./articles/'], a[href*='/articles/']")
    count = article_links.count()
    collected: set[str] = set()

    for index in range(count):
        href = article_links.nth(index).get_attribute("href")
        if not href:
            continue
        wrapped = _unwrap_google_news_href(href)
        collected.add(wrapped)

    resolved_urls: set[str] = set()
    for wrapped_url in sorted(collected):
        try:
            page.goto(wrapped_url, wait_until="domcontentloaded", timeout=15000)
            final_url = normalize_url(page.url)
            if "google.com" not in final_url:
                resolved_urls.add(final_url)
            session.delay()
        except Exception:
            continue

    return sorted(resolved_urls)
