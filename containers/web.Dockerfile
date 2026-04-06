FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="homorepeat-web" \
      org.opencontainers.image.description="Django development runtime for the HomoRepeat web app" \
      org.opencontainers.image.source="https://github.com/rafaelmdc/homorepeat" \
      org.opencontainers.image.vendor="HomoRepeat" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /opt/homorepeat/
COPY src /opt/homorepeat/src
COPY apps/web /opt/homorepeat/apps/web

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install /opt/homorepeat "Django>=5,<6" "psycopg[binary]>=3.1,<4"

WORKDIR /app/apps/web

ENV DJANGO_SETTINGS_MODULE=config.settings
