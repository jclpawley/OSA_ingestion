# Playwright base image includes Chromium and system dependencies for headless Linux.
FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/config.docker.yaml ./config/config.docker.yaml
COPY config/config.example.yaml ./config/config.example.yaml

RUN mkdir -p data/s3 data/rds data/browser-profile

USER pwuser

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--config", "config/config.docker.yaml"]
