# OSA Ingestion

Web scraping pipeline for online safety content. Scrapes configured direct sources and meta sources (listing pages and Google News), stores raw HTML locally (or S3 in AWS mode), and records article metadata in CSV files (or RDS Postgres in AWS mode).

## Setup

```powershell
cd OSA_ingestion
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy config\config.example.yaml config\config.yaml
```

## Run locally

```powershell
python -m src.main --config config/config.yaml
```

Optional verbose logging:

```powershell
python -m src.main --config config/config.yaml --verbose
```

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Tests use mocks and temp directories — no live scraping or network calls.

## Outputs

- Raw HTML: `data/s3/raw/{source_id}/{date}/{hash}.html`
- Metadata CSVs: `data/rds/sources.csv`, `scrape_runs.csv`, `articles.csv`

## Config

Edit `config/config.yaml`:

- **direct_sources** — URLs scraped directly every run
- **meta_sources** — listing pages or Google News searches; article links are extracted then scraped individually
- **search_terms** — default terms for Google News meta sources

### Source types

| Type | Description |
|------|-------------|
| `direct` (in direct_sources) | Scrape the URL directly |
| `link_page` | Visit a listing page, extract article links, scrape each |
| `google_news` | Search Google News, resolve article URLs, scrape each |

## Architecture (planned AWS)

```
EventBridge schedule → EC2 (Playwright) → S3 (raw HTML) + RDS Postgres (metadata)
```

Phase 1 uses local folders and CSV files for testing without AWS credentials.

## Sky News bot protection

Sky News uses Akamai, which blocks Playwright even when clicking links in Chrome. Cookies are not the issue.

**Recommended: CDP mode** — connect to a normal Chrome you start yourself:

1. Close all Chrome windows, then start Chrome with remote debugging:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:LOCALAPPDATA\ChromeScrapeProfile"
```

2. In `config/config.yaml`, add:

```yaml
settings:
  browser_cdp_url: "http://127.0.0.1:9222"
  headless: false
```

3. Run the scraper — it attaches to your Chrome instead of launching an automated one.

Without CDP mode, the topic listing page usually works but individual story pages return "Access denied".

## Database schema

See `src/models/schema.sql` for the production RDS schema. Local mode writes the same columns to CSV files under `data/rds/`.
