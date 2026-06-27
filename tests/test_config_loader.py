from __future__ import annotations

from pathlib import Path

from src.config_loader import load_config


def test_load_config_parses_sources_and_settings(sample_config_yaml: Path) -> None:
    config = load_config(sample_config_yaml)

    assert config.search_terms == ["online safety"]
    assert len(config.direct_sources) == 1
    assert config.direct_sources[0].name == "Example"
    assert config.direct_sources[0].url == "https://example.com"

    assert len(config.meta_sources) == 1
    assert config.meta_sources[0].type == "link_page"
    assert config.meta_sources[0].url == "https://news.sky.com/topic/internet-safety-6281/1"

    assert config.settings.headless is True
    assert config.settings.page_timeout_ms == 5000
    assert config.settings.max_listing_pages == 2
    assert config.settings.max_articles_per_source == 3
    assert config.settings.storage.mode == "local"


def test_load_config_uses_defaults_for_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    config = load_config(path)

    assert config.search_terms == []
    assert config.direct_sources == []
    assert config.meta_sources == []
    assert config.settings.headless is True
    assert config.settings.max_articles_per_source is None
