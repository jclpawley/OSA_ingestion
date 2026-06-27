from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config_loader import AppConfig, DirectSource, Settings, StorageSettings


@pytest.fixture
def tmp_storage_paths(tmp_path: Path) -> tuple[Path, Path]:
    s3_path = tmp_path / "s3"
    rds_path = tmp_path / "rds"
    return s3_path, rds_path


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    config = {
        "search_terms": ["online safety"],
        "direct_sources": [
            {
                "name": "Example",
                "url": "https://example.com",
                "enabled": True,
            }
        ],
        "meta_sources": [
            {
                "name": "Sky News",
                "type": "link_page",
                "url": "https://news.sky.com/topic/internet-safety-6281/1",
                "enabled": True,
            }
        ],
        "settings": {
            "headless": True,
            "page_timeout_ms": 5000,
            "delay_between_requests_ms": 0,
            "max_listing_pages": 2,
            "max_articles_per_source": 3,
            "storage": {
                "mode": "local",
                "local_s3_path": "data/s3",
                "local_rds_path": "data/rds",
            },
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config), encoding="utf-8")
    return path


@pytest.fixture
def minimal_app_config() -> AppConfig:
    return AppConfig(
        search_terms=["online safety"],
        direct_sources=[
            DirectSource(name="Example", url="https://example.com/", enabled=True)
        ],
        meta_sources=[],
        settings=Settings(
            delay_between_requests_ms=0,
            browser_channel=None,
            use_persistent_profile=False,
            storage=StorageSettings(mode="local"),
        ),
    )
