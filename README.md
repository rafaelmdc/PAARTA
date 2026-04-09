# HomoRepeat Web App

Django project area for the HomoRepeat website.

Current app split:
- `apps/core/`: home page, shared site shell, healthcheck, and future graph pages
- `apps/browser/`: run-first data browser
- `apps/imports/`: staff-facing published-run ingestion

Current containerized dev setup:
- image: `containers/web.Dockerfile`
- service: `web` in the local `compose.yaml`
- database: `postgres` in the same Compose stack

From the repo root, the minimal host-side commands are:

```bash
python3 manage.py migrate
python3 manage.py test web_tests
python3 manage.py import_run --publish-root /absolute/path/to/<run>/publish
python3 manage.py runserver 0.0.0.0:8000
```

Local configuration:

```bash
cp .env.example .env
```

With no database env vars set, Django uses the local SQLite dev database under `db.sqlite3`.
Inside Compose, the same project runs against the `postgres` service.
If you want the import UI to auto-detect published runs, set `HOMOREPEAT_RUNS_ROOT` to the directory that contains your run folders. Otherwise import manually with `--publish-root`.

Run the development stack from the repo root with:

```bash
docker compose up web worker postgres
```

The Compose `web` service also mounts the sibling repo `../homorepeat_pipeline`
read-only at `/workspace/homorepeat_pipeline` and defaults
`HOMOREPEAT_RUNS_ROOT` to `/workspace/homorepeat_pipeline/runs`.
That means the import UI can auto-detect runs from the sibling pipeline repo in
the common local checkout layout.

With the Compose stack running, you can:

- use `/imports/` to queue a run from the detected sibling pipeline outputs and let the `worker` service process it automatically
- process the oldest queued batch manually with `docker compose exec web python manage.py import_run --next-pending`
- import one run directly with `docker compose exec web python manage.py import_run --publish-root /workspace/homorepeat_pipeline/runs/<run-id>/publish`

Current endpoints:
- `/`: site home
- `/healthz/`: JSON healthcheck
- `/browser/`: browser placeholder
- `/imports/`: imports placeholder

The data model, import backend, and graph views are implemented in later slices.
