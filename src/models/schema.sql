CREATE TABLE IF NOT EXISTS sources (
    source_id       SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    base_url        TEXT NOT NULL UNIQUE,
    robots_txt_status TEXT DEFAULT 'unknown',
    scrape_frequency  TEXT DEFAULT 'daily',
    enabled         BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id          SERIAL PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES sources(source_id),
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    article_id      SERIAL PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES sources(source_id),
    url             TEXT NOT NULL UNIQUE,
    title           TEXT,
    published_at    TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL,
    content_hash    TEXT NOT NULL,
    s3_raw_html_path TEXT NOT NULL,
    s3_text_path    TEXT
);

CREATE TABLE IF NOT EXISTS article_classifications (
    article_id      INTEGER NOT NULL REFERENCES articles(article_id),
    topic           TEXT,
    relevance_score REAL,
    summary         TEXT,
    model_name      TEXT,
    classified_at   TIMESTAMPTZ,
    PRIMARY KEY (article_id, topic)
);
