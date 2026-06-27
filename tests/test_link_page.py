from __future__ import annotations

from unittest.mock import MagicMock

from src.sources import link_page


def test_topic_page_urls_paginates_sky_topic() -> None:
    urls = link_page._topic_page_urls(
        "https://news.sky.com/topic/internet-safety-6281/1",
        max_pages=3,
    )
    assert urls == [
        "https://news.sky.com/topic/internet-safety-6281/1",
        "https://news.sky.com/topic/internet-safety-6281/2",
        "https://news.sky.com/topic/internet-safety-6281/3",
    ]


def test_topic_page_urls_returns_single_url_when_no_page_pattern() -> None:
    urls = link_page._topic_page_urls("https://example.com/news", max_pages=5)
    assert urls == ["https://example.com/news"]


def test_is_sky_article() -> None:
    assert link_page._is_sky_article(
        "https://news.sky.com/story/online-safety-bill-123"
    )
    assert not link_page._is_sky_article("https://news.sky.com/topic/foo/1")
    assert not link_page._is_sky_article("https://bbc.co.uk/news/story")


def test_extract_links_from_page_filters_story_links() -> None:
    page = MagicMock()
    locator = MagicMock()
    page.locator.return_value = locator
    locator.count.return_value = 4
    locator.nth.side_effect = lambda i: MagicMock(
        get_attribute=MagicMock(
            side_effect=lambda _name, idx=i: [
                "/story/article-one",
                "/topic/internet-safety-6281/2",
                "javascript:void(0)",
                "https://news.sky.com/story/article-two",
            ][idx]
        )
    )

    links = link_page.extract_links_from_page(
        page, "https://news.sky.com/topic/internet-safety-6281/1"
    )

    assert links == {
        "https://news.sky.com/story/article-one",
        "https://news.sky.com/story/article-two",
    }
