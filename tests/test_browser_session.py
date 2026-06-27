from __future__ import annotations

from unittest.mock import MagicMock

from playwright.sync_api import Error as PlaywrightError

from src.browser.session import (
    AccessDeniedError,
    BrowserSession,
    _is_access_denied,
    dismiss_cookie_consent,
    dismiss_survey_overlays,
)
from src.config_loader import Settings


def test_is_access_denied_detects_short_block_page() -> None:
    page = MagicMock()
    page.title.return_value = "Access Denied"
    page.content.return_value = "<html><title>Access Denied</title></html>"
    assert _is_access_denied(page) is True


def test_is_access_denied_allows_normal_page() -> None:
    page = MagicMock()
    page.title.return_value = "Example Domain"
    page.content.return_value = "<html>" + ("x" * 3000) + "</html>"
    assert _is_access_denied(page) is False


def _consent_mocks(page: MagicMock) -> None:
    frame = MagicMock()
    page.frame_locator.return_value = frame
    button = MagicMock()
    button.count.return_value = 0
    frame.get_by_role.return_value = button
    page.get_by_role.return_value = button
    page.evaluate.return_value = 0


def _obstruction_mocks(page: MagicMock, link: MagicMock | None = None) -> None:
    _consent_mocks(page)
    survey = MagicMock()
    survey.count.return_value = 0

    def locator_side_effect(selector: str) -> MagicMock:
        if "QSIWebResponsive" in selector:
            return survey
        if link is not None and 'a[href*=' in selector:
            return link
        fallback = MagicMock()
        fallback.count.return_value = 0
        fallback.first = fallback
        return fallback

    page.locator.side_effect = locator_side_effect


def test_navigate_raises_on_access_denied() -> None:
    settings = Settings(delay_between_requests_ms=0)
    session = BrowserSession(settings)
    page = MagicMock()
    page.title.return_value = "Access Denied"
    page.content.return_value = "<html>Access Denied</html>"
    _obstruction_mocks(page)

    try:
        session.navigate(page, "https://news.sky.com/story/test")
        raised = False
    except AccessDeniedError:
        raised = True

    assert raised is True


def test_dismiss_cookie_consent_clicks_iframe_button() -> None:
    page = MagicMock()
    frame = MagicMock()
    page.frame_locator.return_value = frame
    button = MagicMock()
    button.count.return_value = 1
    frame.get_by_role.return_value = button

    assert dismiss_cookie_consent(page) is True
    button.first.click.assert_called_once()


def test_dismiss_survey_overlays_removes_dom() -> None:
    page = MagicMock()
    survey = MagicMock()
    survey.count.return_value = 1
    survey.first.click.side_effect = PlaywrightError("blocked")
    page.locator.return_value = survey
    page.get_by_role.return_value = MagicMock(count=MagicMock(return_value=0))
    page.evaluate.return_value = 2

    assert dismiss_survey_overlays(page) is True
    page.evaluate.assert_called_once()


def test_click_story_link_uses_navigation_expectation() -> None:
    settings = Settings(delay_between_requests_ms=0, use_persistent_profile=False)
    session = BrowserSession(settings)
    page = MagicMock()
    link = MagicMock()
    link.first = link
    nav_context = MagicMock()
    nav_context.__enter__ = MagicMock(return_value=None)
    nav_context.__exit__ = MagicMock(return_value=False)
    page.expect_navigation.return_value = nav_context
    _obstruction_mocks(page, link)

    assert session.click_story_link(
        page, "https://news.sky.com/story/example-article-123"
    )
    link.scroll_into_view_if_needed.assert_called_once()
    link.hover.assert_called_once()
    link.click.assert_called_once()
