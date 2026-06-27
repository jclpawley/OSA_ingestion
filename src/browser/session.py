"""Playwright browser session management."""

from __future__ import annotations

import logging
import re
import sys
import time
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    sync_playwright,
)

from src.config_loader import Settings

logger = logging.getLogger(__name__)

CONSENT_BUTTON_LABELS = (
    "Accept All",
    "I Accept",
    "Accept",
    "Agree",
    "Reject All",
    "Essential Cookies Only",
)

SURVEY_DISMISS_LABELS = (
    "No thanks",
    "No, thanks",
    "Not now",
    "Close",
    "Dismiss",
)

SURVEY_CLOSE_SELECTORS = (
    '[class*="QSIWebResponsive"] button[aria-label*="Close" i]',
    '[class*="QSIWebResponsive"] [class*="close-btn"]',
    '[class*="QSIWebResponsive"] [class*="_close"]',
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""


class AccessDeniedError(RuntimeError):
    pass


def _is_access_denied(page: Page) -> bool:
    title = (page.title() or "").lower()
    if "access denied" in title:
        return True
    content = page.content().lower()
    return "access denied" in content and len(content) < 2000


def dismiss_cookie_consent(page: Page) -> bool:
    """Dismiss Sourcepoint / common cookie banners that block clicks on Sky News."""
    dismissed = False

    iframe_selectors = (
        'iframe[title*="Consent"]',
        'iframe[id*="sp_message"]',
        'iframe[src*="privacy-mgmt.com"]',
    )
    for selector in iframe_selectors:
        frame = page.frame_locator(selector)
        for label in CONSENT_BUTTON_LABELS:
            button = frame.get_by_role("button", name=label)
            try:
                if button.count() > 0:
                    button.first.click(timeout=3000)
                    page.wait_for_timeout(500)
                    logger.info("Dismissed cookie consent via iframe (%s)", label)
                    return True
            except PlaywrightError:
                continue

    for label in CONSENT_BUTTON_LABELS:
        button = page.get_by_role("button", name=label)
        try:
            if button.count() > 0:
                button.first.click(timeout=2000)
                page.wait_for_timeout(500)
                logger.info("Dismissed cookie consent on page (%s)", label)
                return True
        except PlaywrightError:
            continue

    try:
        removed = page.evaluate(
            """() => {
                let count = 0;
                document.querySelectorAll('[id*="sp_message"], [class*="sp_message"]').forEach(el => {
                    el.remove();
                    count += 1;
                });
                return count;
            }"""
        )
        if removed:
            logger.info("Removed %s consent overlay element(s) via DOM", removed)
            dismissed = True
    except PlaywrightError:
        pass

    return dismissed


def dismiss_survey_overlays(page: Page) -> bool:
    """Dismiss Qualtrics (QSIWebResponsive) survey popups that block listing clicks."""
    dismissed = False

    try:
        survey = page.locator('[class*="QSIWebResponsive"]')
        if survey.count() == 0:
            pass
        else:
            for label in SURVEY_DISMISS_LABELS:
                button = page.get_by_role(
                    "button", name=re.compile(label, re.IGNORECASE)
                )
                try:
                    if button.count() > 0:
                        button.first.click(timeout=2000)
                        page.wait_for_timeout(500)
                        logger.info("Dismissed survey overlay via button (%s)", label)
                        return True
                except PlaywrightError:
                    continue

            for selector in SURVEY_CLOSE_SELECTORS:
                close_button = page.locator(selector)
                try:
                    if close_button.count() > 0:
                        close_button.first.click(timeout=2000)
                        page.wait_for_timeout(500)
                        logger.info("Dismissed survey overlay via close control")
                        return True
                except PlaywrightError:
                    continue
    except PlaywrightError:
        pass

    try:
        removed = page.evaluate(
            """() => {
                let count = 0;
                document.querySelectorAll(
                    '[class*="QSIWebResponsive"], #QSIFeedbackButton, #QSIFeedbackButton-btn'
                ).forEach(el => {
                    el.remove();
                    count += 1;
                });
                return count;
            }"""
        )
        if removed:
            logger.info("Removed %s survey overlay element(s) via DOM", removed)
            dismissed = True
    except PlaywrightError:
        pass

    return dismissed


def dismiss_page_obstructions(page: Page) -> bool:
    """Dismiss cookie banners and survey popups that intercept clicks."""
    cookie = dismiss_cookie_consent(page)
    survey = dismiss_survey_overlays(page)
    return cookie or survey


def normalize_listing_path(url: str) -> str:
    return urlparse(url).path.rstrip("/")


class BrowserSession:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._persistent = False
        self._cdp = False

    def _launch_kwargs(self) -> dict:
        kwargs: dict = {
            "headless": self.settings.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
            "ignore_default_args": ["--enable-automation"],
            "locale": "en-GB",
            "timezone_id": "Europe/London",
            "viewport": {"width": 1280, "height": 720},
        }
        # Playwright disables the sandbox by default (--no-sandbox). On Windows/macOS
        # that triggers Chrome's "unsupported command-line flag" warning.
        if sys.platform != "linux":
            kwargs["chromium_sandbox"] = True
        if self.settings.browser_channel:
            kwargs["channel"] = self.settings.browser_channel
        if self.settings.user_agent:
            kwargs["user_agent"] = self.settings.user_agent
        return kwargs

    def __enter__(self) -> "BrowserSession":
        self._playwright = sync_playwright().start()

        if self.settings.browser_cdp_url:
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.settings.browser_cdp_url
            )
            contexts = self._browser.contexts
            self._context = contexts[0] if contexts else self._browser.new_context()
            self._cdp = True
            logger.info("Connected to Chrome via CDP at %s", self.settings.browser_cdp_url)
            return self

        launch_kwargs = self._launch_kwargs()

        if self.settings.use_persistent_profile:
            profile_dir = self.settings.browser_profile_dir
            from pathlib import Path

            Path(profile_dir).mkdir(parents=True, exist_ok=True)
            self._context = self._playwright.chromium.launch_persistent_context(
                profile_dir,
                **launch_kwargs,
            )
            self._context.add_init_script(STEALTH_INIT_SCRIPT)
            self._persistent = True
            logger.info(
                "Launched persistent browser (channel=%s, profile=%s)",
                self.settings.browser_channel or "chromium",
                profile_dir,
            )
        else:
            self._browser = self._playwright.chromium.launch(
                headless=self.settings.headless,
                channel=self.settings.browser_channel or None,
                args=launch_kwargs["args"],
                ignore_default_args=launch_kwargs["ignore_default_args"],
                chromium_sandbox=launch_kwargs.get("chromium_sandbox"),
            )
            logger.info(
                "Launched browser (channel=%s)",
                self.settings.browser_channel or "chrome",
            )

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._cdp:
            if self._browser:
                self._browser.close()
        else:
            if self._context and self._persistent:
                self._context.close()
            if self._browser:
                self._browser.close()
        if self._playwright:
            self._playwright.stop()

    @contextmanager
    def page(self) -> Generator[Page, None, None]:
        if not self._browser and not self._context:
            raise RuntimeError("BrowserSession must be used as a context manager")

        if self._cdp and self._context:
            page = self._context.pages[0] if self._context.pages else self._context.new_page()
            page.set_default_timeout(self.settings.page_timeout_ms)
            yield page
            return

        if self._persistent and self._context:
            page = self._context.pages[0] if self._context.pages else self._context.new_page()
            page.set_default_timeout(self.settings.page_timeout_ms)
            yield page
            return

        assert self._browser is not None
        context = self._browser.new_context(
            locale="en-GB",
            timezone_id="Europe/London",
            viewport={"width": 1280, "height": 720},
            user_agent=self.settings.user_agent or None,
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(self.settings.page_timeout_ms)
        try:
            yield page
        finally:
            context.close()

    def delay(self) -> None:
        delay_ms = self.settings.delay_between_requests_ms
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    def navigate(self, page: Page, url: str, referer: str | None = None) -> None:
        page.goto(url, wait_until="domcontentloaded", referer=referer)
        page.wait_for_timeout(1500)
        dismiss_page_obstructions(page)
        if _is_access_denied(page):
            raise AccessDeniedError(
                f"Site blocked automated access for {url}. "
                "For Sky News, set browser_cdp_url and connect to a manually started Chrome."
            )

    def click_story_link(self, page: Page, article_url: str) -> bool:
        """Click a story link on the current listing page (mimics human navigation)."""
        dismiss_page_obstructions(page)
        story_path = urlparse(article_url).path
        link = page.locator(f'a[href*="{story_path}"]').first

        for attempt in range(2):
            try:
                link.scroll_into_view_if_needed(timeout=10000)
                page.wait_for_timeout(400)
                if attempt == 0:
                    link.hover(timeout=5000)
                    page.wait_for_timeout(300)
                with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                    link.click(timeout=10000)
                page.wait_for_timeout(2000)
                return True
            except PlaywrightError as exc:
                if attempt == 0:
                    logger.info(
                        "Retrying story click after clearing overlays: %s", article_url
                    )
                    dismiss_page_obstructions(page)
                    continue
                logger.warning("Could not click story link %s: %s", article_url, exc)
                return False

        return False

    def return_to_listing(self, page: Page, listing_url: str) -> None:
        """Go back to the listing page and restore a clickable state."""
        try:
            if normalize_listing_path(page.url) != normalize_listing_path(listing_url):
                page.go_back(wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
        except PlaywrightError:
            try:
                page.goto(listing_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
            except PlaywrightError as exc:
                logger.warning("Could not return to listing %s: %s", listing_url, exc)
                return
        dismiss_page_obstructions(page)
