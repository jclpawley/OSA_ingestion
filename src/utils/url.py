"""URL normalization and filtering helpers."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return normalized


def is_same_domain(url: str, domain: str) -> bool:
    return urlparse(url).netloc.lower().endswith(domain.lower())


def resolve_href(base_url: str, href: str) -> str | None:
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return None
    return normalize_url(urljoin(base_url, href))
