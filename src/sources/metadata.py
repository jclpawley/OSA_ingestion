"""Extract article metadata from HTML."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        return title or None
    return None


def extract_published_at(html: str) -> datetime | None:
    patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']publish-date["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                return date_parser.parse(match.group(1))
            except (ValueError, TypeError):
                continue

    json_ld_match = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if json_ld_match:
        try:
            payload: Any = json.loads(json_ld_match.group(1))
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ("datePublished", "dateCreated"):
                    if item.get(key):
                        return date_parser.parse(item[key])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None
