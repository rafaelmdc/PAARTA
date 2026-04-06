# HomoRepeat Web App

Django project area for the HomoRepeat website.

Current app split:
- `apps/core/`: home page, shared site shell, healthcheck, and future graph pages
- `apps/browser/`: run-first data browser
- `apps/imports/`: staff-facing published-run ingestion

Current containerized dev setup:
- image: `containers/web.Dockerfile`
- service: `web` in the repo-root `compose.yaml`
- database: `postgres` in the same Compose stack

Run the development stack from the repo root with:

```bash
docker compose up web postgres
```

Current endpoints:
- `/`: site home
- `/healthz/`: JSON healthcheck
- `/browser/`: browser placeholder
- `/imports/`: imports placeholder

The data model, import backend, and graph views are implemented in later slices.
