"""Local storage: folder for HTML, CSV files for metadata."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.storage.base import ArticleRecord


TABLE_COLUMNS = {
    "sources": [
        "source_id",
        "name",
        "base_url",
        "robots_txt_status",
        "scrape_frequency",
        "enabled",
    ],
    "scrape_runs": [
        "run_id",
        "source_id",
        "started_at",
        "finished_at",
        "status",
        "error_message",
    ],
    "articles": [
        "article_id",
        "source_id",
        "url",
        "title",
        "published_at",
        "scraped_at",
        "content_hash",
        "s3_raw_html_path",
        "s3_text_path",
    ],
    "article_classifications": [
        "article_id",
        "topic",
        "relevance_score",
        "summary",
        "model_name",
        "classified_at",
    ],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class LocalStorageBackend:
    def __init__(self, s3_path: str | Path, rds_path: str | Path) -> None:
        self.s3_root = Path(s3_path)
        self.rds_root = Path(rds_path)
        self.s3_root.mkdir(parents=True, exist_ok=True)
        self.rds_root.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _csv_path(self, table: str) -> Path:
        return self.rds_root / f"{table}.csv"

    def _ensure_tables(self) -> None:
        for table, columns in TABLE_COLUMNS.items():
            path = self._csv_path(table)
            if not path.exists():
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()

    def _read_rows(self, table: str) -> list[dict[str, str]]:
        path = self._csv_path(table)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _append_row(self, table: str, row: dict[str, str]) -> None:
        path = self._csv_path(table)
        columns = TABLE_COLUMNS[table]
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writerow({col: row.get(col, "") for col in columns})

    def _update_row(self, table: str, id_field: str, id_value: str, updates: dict) -> None:
        rows = self._read_rows(table)
        path = self._csv_path(table)
        columns = TABLE_COLUMNS[table]
        for row in rows:
            if row[id_field] == id_value:
                row.update({k: str(v) if v is not None else "" for k, v in updates.items()})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _next_id(self, table: str, id_field: str) -> int:
        rows = self._read_rows(table)
        if not rows:
            return 1
        return max(int(row[id_field]) for row in rows if row[id_field]) + 1

    def sync_sources(self, sources: list[dict]) -> dict[str, int]:
        existing = {row["base_url"]: int(row["source_id"]) for row in self._read_rows("sources")}
        url_to_id: dict[str, int] = {}

        for source in sources:
            base_url = source["base_url"]
            if base_url in existing:
                source_id = existing[base_url]
                self._update_row(
                    "sources",
                    "source_id",
                    str(source_id),
                    {
                        "name": source["name"],
                        "scrape_frequency": source.get("scrape_frequency", "daily"),
                        "enabled": str(source.get("enabled", True)).lower(),
                    },
                )
            else:
                source_id = self._next_id("sources", "source_id")
                self._append_row(
                    "sources",
                    {
                        "source_id": str(source_id),
                        "name": source["name"],
                        "base_url": base_url,
                        "robots_txt_status": "unknown",
                        "scrape_frequency": source.get("scrape_frequency", "daily"),
                        "enabled": str(source.get("enabled", True)).lower(),
                    },
                )
                existing[base_url] = source_id
            url_to_id[base_url] = source_id

        return url_to_id

    def start_run(self, source_id: int) -> int:
        run_id = self._next_id("scrape_runs", "run_id")
        self._append_row(
            "scrape_runs",
            {
                "run_id": str(run_id),
                "source_id": str(source_id),
                "started_at": _iso(_utc_now()),
                "finished_at": "",
                "status": "running",
                "error_message": "",
            },
        )
        return run_id

    def finish_run(
        self, run_id: int, status: str, error_message: str | None = None
    ) -> None:
        self._update_row(
            "scrape_runs",
            "run_id",
            str(run_id),
            {
                "finished_at": _iso(_utc_now()),
                "status": status,
                "error_message": error_message or "",
            },
        )

    def url_exists(self, url: str) -> bool:
        return url in self.get_seen_urls()

    def get_seen_urls(self) -> set[str]:
        return {row["url"] for row in self._read_rows("articles") if row.get("url")}

    def save_html(
        self, source_id: int, url: str, html: str, content_hash: str
    ) -> str:
        date_prefix = _utc_now().strftime("%Y-%m-%d")
        relative = Path("raw") / str(source_id) / date_prefix / f"{content_hash}.html"
        target = self.s3_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return str(relative).replace("\\", "/")

    def save_article(self, article: ArticleRecord) -> ArticleRecord:
        article_id = self._next_id("articles", "article_id")
        record = ArticleRecord(
            article_id=article_id,
            source_id=article.source_id,
            url=article.url,
            title=article.title,
            published_at=article.published_at,
            scraped_at=article.scraped_at,
            content_hash=article.content_hash,
            s3_raw_html_path=article.s3_raw_html_path,
            s3_text_path=article.s3_text_path,
        )
        self._append_row(
            "articles",
            {
                "article_id": str(record.article_id),
                "source_id": str(record.source_id),
                "url": record.url,
                "title": record.title or "",
                "published_at": _iso(record.published_at),
                "scraped_at": _iso(record.scraped_at),
                "content_hash": record.content_hash,
                "s3_raw_html_path": record.s3_raw_html_path,
                "s3_text_path": record.s3_text_path or "",
            },
        )
        return record
