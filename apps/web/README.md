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

From the repo root, the minimal host-side commands are:

```bash
python3 apps/web/manage.py migrate
python3 apps/web/manage.py test web_tests
python3 apps/web/manage.py runserver 0.0.0.0:8000
```

With no database env vars set, Django uses the local SQLite dev database under `apps/web/db.sqlite3`.
Inside Compose, the same project runs against the `postgres` service.

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
