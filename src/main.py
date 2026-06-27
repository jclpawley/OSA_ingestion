"""CLI entrypoint for OSA ingestion scraper."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config_loader import load_config
from src.orchestrator import ScraperOrchestrator
from src.storage import create_storage


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OSA web scraping ingestion pipeline")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to YAML config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = Path(args.config)
    if not config_path.exists():
        logging.error("Config file not found: %s", config_path)
        logging.error("Copy config/config.example.yaml to config/config.yaml to start.")
        return 1

    config = load_config(config_path)
    storage = create_storage(config.settings.storage)
    orchestrator = ScraperOrchestrator(config, storage)

    try:
        orchestrator.run()
    except Exception:
        logging.exception("Scrape run failed")
        return 1

    logging.info("Scrape run completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
