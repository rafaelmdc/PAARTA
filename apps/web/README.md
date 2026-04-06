# HomoRepeat Web App

Reserved Django application area for the future HomoRepeat frontend.

Planned responsibilities:
- browse published pipeline runs
- ingest published TSV/SQLite/Postgres artifacts
- support later run-launch orchestration without coupling to Nextflow internals

Current containerized dev setup:
- image: `containers/web.Dockerfile`
- service: `web` in the repo-root `compose.yaml`
- database: `postgres` in the same Compose stack

Run the development stack from the repo root with:

```bash
docker compose up web postgres
```

Verified on April 6, 2026:
- `docker compose up web postgres` started successfully
- the root URL returned `{"status": "ok", "app": "homorepeat-web"}`

This scaffold is intentionally minimal until the data model and ingestion layer are implemented.
