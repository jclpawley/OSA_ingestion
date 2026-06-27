from __future__ import annotations

from src.utils.hash import content_hash


def test_content_hash_is_stable_sha256() -> None:
    html = "<html><body>hello</body></html>"
    result = content_hash(html)
    assert len(result) == 64
    assert result == content_hash(html)


def test_content_hash_changes_with_content() -> None:
    assert content_hash("a") != content_hash("b")
