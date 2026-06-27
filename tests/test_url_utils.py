from __future__ import annotations

from src.utils.url import is_same_domain, normalize_url, resolve_href


def test_normalize_url_strips_trailing_slash_and_lowercases_host() -> None:
    assert normalize_url("https://Example.COM/path/") == "https://example.com/path"


def test_normalize_url_preserves_query_when_present() -> None:
    assert (
        normalize_url("https://example.com/search?q=test")
        == "https://example.com/search?q=test"
    )


def test_resolve_href_skips_invalid_schemes() -> None:
    assert resolve_href("https://example.com", "#section") is None
    assert resolve_href("https://example.com", "javascript:void(0)") is None
    assert resolve_href("https://example.com", "mailto:a@b.com") is None


def test_resolve_href_resolves_relative_paths() -> None:
    assert (
        resolve_href("https://news.sky.com/topic/foo/1", "/story/article-1")
        == "https://news.sky.com/story/article-1"
    )


def test_is_same_domain() -> None:
    assert is_same_domain("https://news.sky.com/story/x", "news.sky.com")
    assert not is_same_domain("https://bbc.co.uk/news", "news.sky.com")
