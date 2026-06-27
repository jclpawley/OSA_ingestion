import hashlib


def content_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()
