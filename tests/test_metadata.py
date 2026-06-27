from __future__ import annotations

from src.sources.metadata import extract_published_at, extract_title


def test_extract_title_from_html() -> None:
    html = "<html><head><title>  Online Safety   News </title></head></html>"
    assert extract_title(html) == "Online Safety News"


def test_extract_title_returns_none_when_missing() -> None:
    assert extract_title("<html><body>no title</body></html>") is None


def test_extract_published_at_from_meta_tag() -> None:
    html = """
    <html><head>
    <meta property="article:published_time" content="2024-03-15T10:30:00+00:00" />
    </head></html>
    """
    published = extract_published_at(html)
    assert published is not None
    assert published.year == 2024
    assert published.month == 3
    assert published.day == 15


def test_extract_published_at_from_json_ld() -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "NewsArticle", "datePublished": "2023-01-02T08:00:00Z"}
    </script>
    </head></html>
    """
    published = extract_published_at(html)
    assert published is not None
    assert published.year == 2023
