"""Direct source: scrape a single URL."""

from __future__ import annotations

from playwright.sync_api import Page

from src.browser.session import BrowserSession


def scrape_page(session: BrowserSession, page: Page, url: str) -> str:
    session.navigate(page, url)
    return page.content()
