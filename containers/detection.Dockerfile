FROM python:3.12-slim-bookworm

ARG DIAMOND_VERSION=2.1.15
ARG DIAMOND_ARCHIVE_URL=https://github.com/bbuchfink/diamond/releases/download/v2.1.15/diamond-linux64.tar.gz

LABEL org.opencontainers.image.title="homorepeat-detection" \
      org.opencontainers.image.description="Pinned detection runtime for the HomoRepeat rebuild" \
      org.opencontainers.image.source="https://github.com/bbuchfink/diamond" \
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
        tar \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "${DIAMOND_ARCHIVE_URL}" -o /tmp/diamond-linux64.tar.gz \
    && tar -xzf /tmp/diamond-linux64.tar.gz -C /tmp \
    && install -m 0755 /tmp/diamond /usr/local/bin/diamond \
    && rm -f /tmp/diamond-linux64.tar.gz /tmp/diamond /tmp/diamond_manual.pdf \
    && python --version \
    && diamond version

RUN mkdir -p /work

WORKDIR /work

ENV HOMOREPEAT_DETECTION_IMAGE=1 \
    DIAMOND_PINNED_VERSION=${DIAMOND_VERSION}
