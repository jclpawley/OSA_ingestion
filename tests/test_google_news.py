from __future__ import annotations

from src.sources import google_news


def test_build_search_url_encodes_query() -> None:
    url = google_news.build_search_url("online safety")
    assert "q=online+safety" in url
    assert url.startswith("https://news.google.com/search?")


def test_unwrap_google_news_href() -> None:
    assert (
        google_news._unwrap_google_news_href("./articles/abc")
        == "https://news.google.com/articles/abc"
    )
    assert (
        google_news._unwrap_google_news_href("https://news.google.com/articles/xyz")
        == "https://news.google.com/articles/xyz"
    )
