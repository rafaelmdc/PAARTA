# Session Log

**Date:** 2026-04-23

## Objective
- Continue the reusable browser TSV download work from the Phase 2 list exports into the stats surfaces.
- Finish the remaining implementation-plan slices needed for the MVP table-download path.
- Leave a dated handoff note for the missing morning log.

## What happened
- Verified the implementation plan and recent commits before resuming work.
- Confirmed the current next step was Phase 4, because Phase 2 was complete and Phase 3 had been explicitly skipped for MVP.
- Implemented Phase 4.1:
  - added `StatsTSVExportMixin`
  - wired stats-side `download=<dataset-key>` dispatch
  - made unknown dataset keys return 404 and valid unavailable datasets return header-only TSV
- Implemented Phase 4.2 for repeat lengths:
  - `summary`
  - `overview_typical`
  - `overview_tail`
  - `inspect`
- Implemented Phase 4.3 for codon composition:
  - `summary`
  - `overview`
  - `browse`
  - `inspect`
- Implemented Phase 4.4 for codon composition by length:
  - `summary`
  - `preference`
  - `dominance`
  - `shift`
  - `similarity`
  - `browse`
  - `inspect`
  - `comparison`
- Implemented Phase 5.1:
  - generalized the shared TSV button include so it can render from a plain URL or a labeled `{href, label}` action object
  - kept existing list-page button behavior unchanged
- Implemented Phase 5.2:
  - added stats section actions to the repeat-length, codon-ratio, and codon-composition-by-length explorer templates
  - hid unavailable mode buttons instead of showing broken or awkward actions
  - used explicit labels for multi-dataset sections such as `Download Preference TSV` and `Download Similarity TSV`
- Implemented Phase 5.3:
  - audited every `templates/browser/*.html` file containing `<table>`
  - documented the MVP exclusions for detail pages and the home-page recent-runs snapshot
  - added an automated audit test so uncovered browser tables fail the suite
- Ran the broader Phase 6.1 automated browser-side test pass and it succeeded.
- Added a follow-up browser-home card for the codon-composition-by-length explorer so the route is reachable from `/browser/` without typing the URL manually.

## Files touched
- `apps/browser/exports.py`
  - added `StatsTSVExportMixin`
  - added shared labeled-action helpers for TSV buttons
- `apps/browser/views/stats/lengths.py`
  - added repeat-length TSV dataset wiring and section download actions
- `apps/browser/views/stats/codon_ratios.py`
  - added codon-composition TSV dataset wiring and section download actions
- `apps/browser/views/stats/codon_composition_lengths.py`
  - added codon-composition-by-length TSV dataset wiring and section download actions
- `templates/browser/repeat_length_explorer.html`
  - added section-level download buttons
- `templates/browser/codon_ratio_explorer.html`
  - added section-level download buttons
- `templates/browser/codon_composition_length_explorer.html`
  - added section-level download buttons for overview, browse, inspect, comparison, and grouped fallback sections
- `templates/browser/includes/download_tsv_button.html`
  - expanded the shared include to support labeled actions as well as the original single URL case
- `docs/implementation/table_downloads/implementation_plan.md`
  - documented the Phase 5.3 browser-table audit result and MVP exclusions
- `apps/browser/views/navigation.py`
  - added the browser-home `Codon*length` card
- `web_tests/test_browser_exports.py`
  - added stats-mixin tests, shared button include tests, and the browser-table audit test
- `web_tests/test_browser_stats.py`
  - added stats export coverage and stats section-action render coverage
- `web_tests/_browser_views.py`
  - added the browser-home assertion for the new `Codon*length` card

## Validation
- `python manage.py test web_tests.test_browser_exports web_tests.test_browser_stats`
- `python manage.py test web_tests.test_browser_exports`
- `python manage.py test web_tests.test_browser_exports web_tests.test_browser_home_runs web_tests.test_browser_accessions web_tests.test_browser_taxa_genomes web_tests.test_browser_sequences web_tests.test_browser_proteins web_tests.test_browser_repeat_calls web_tests.test_browser_operations`
- `python manage.py test web_tests.test_browser_home_runs`
- `python manage.py test web_tests.test_browser_accessions web_tests.test_browser_codon_composition_lengths web_tests.test_browser_codon_ratios web_tests.test_browser_exports web_tests.test_browser_home_runs web_tests.test_browser_lengths web_tests.test_browser_metadata web_tests.test_browser_operations web_tests.test_browser_proteins web_tests.test_browser_repeat_calls web_tests.test_browser_sequences web_tests.test_browser_stats web_tests.test_browser_taxa_genomes`
- Broad browser pass result:
  - `Ran 227 tests in 22.452s`
  - `OK`
- Manual Phase 6.2 checks completed by the user for the new Phase 4+ stats export flow and section-action wiring.

## Current status
- Phase 4 complete.
- Phase 5 complete.
- Phase 6.1 complete.
- Phase 6.2 complete.
- The table-download MVP is complete.

## Open issues
- Detail-page table exports remain intentionally deferred because Phase 3 is skipped for MVP.
- No JavaScript-specific manual check was run in this session beyond server-rendered template and route coverage.

## Next step
- If desired, commit the Phase 4–6 table-download work and the browser-home `Codon*length` entry.

---

## Session continuation — Redis/Celery refactor (Phase 1 + 2)

### Objective
Refine and implement the Redis/Celery infrastructure refactor documented in `docs/implementation/redis_celery_refactor/`.

### Planning work (Phase 0 — docs)
Updated `overview.md` and `implementation_plan.md` to reflect:
- Stats service layer already extracted (no extraction needed)
- Gunicorn required for multi-worker shared Redis cache
- Flower proxied through Django at `/admin/flower/` behind `@staff_member_required` (no exposed port)
- `celery-beat` promoted to required (not optional) for import correctness — worker crash leaves batch stuck in RUNNING; Beat watchdog is the fix
- Redis DB separation: `/0` broker (AOF), `/1` cache (`volatile-lru`)
- `CELERY_WORKER_PREFETCH_MULTIPLIER = 1` and `visibility_timeout: 43200` for long-running import tasks
- `CatalogVersion` singleton model and cache stampede mitigation (Phase 4 target)

Created `docs/implementation/redis_celery_refactor/payload_inventory.md` — full inventory of all graph, download, and import payloads classified as `sync`, `sync+cache`, `async+persisted`, or `defer`.

### Phase 1 — audit + instrumentation
- Created `apps/browser/stats/_cache.py` — single `build_or_get_cached()` helper with hit/miss timing logs
- Refactored all 9 cached bundle builders in `apps/browser/stats/queries.py` to use `build_or_get_cached`
- Refactored `apps/browser/stats/taxonomy_gutter.py` similarly
- Updated `pyproject.toml` dependencies: `celery[redis]`, `django-redis`, `gunicorn`, `httpx`, `whitenoise`

### Phase 2 — Redis + Celery skeleton
- Created `config/celery.py` — Celery app with Django settings namespace
- Updated `config/__init__.py` to expose `celery_app`
- Updated `config/settings.py`:
  - `WhiteNoiseMiddleware` after `SecurityMiddleware`
  - `CACHES` conditional on `REDIS_URL` (locmem fallback for local dev/tests)
  - Full Celery config block: broker `/0`, cache `/1`, prefetch multiplier, visibility timeout, task routes
- Updated `apps/core/views.py` — `flower_proxy` view with `@staff_member_required` and `httpx.ConnectError → 503` handling
- Updated `config/urls.py` — `/admin/flower/` and `/admin/flower/<path>` routes
- Updated `compose.yaml`:
  - Added `redis` service (`redis:7-alpine`, AOF, healthcheck, `redis_data` volume)
  - Switched `web` from `runserver` to `gunicorn --workers 4 --timeout 120`; added `REDIS_URL`, `FLOWER_INTERNAL_URL`
  - Added `celery-import-worker` (queue `imports`, concurrency 2, prefetch 1, healthcheck)
  - Added `celery-payload-worker` (queues `payload_graph,downloads`, concurrency 4, healthcheck)
  - Added `flower` service (port 5555 internal only, `--url_prefix=admin/flower`)
  - Kept `worker` service with deprecation comment (remove in Phase 3)
  - Added `redis_data` to `volumes:`

### Validation
- `python manage.py test web_tests` — 322 tests, OK (skipped=2)

### Current status
- Phase 1 complete.
- Phase 2 complete.
- Phase 3 (import task → Celery) is next — highest-risk phase.

### Next step
- Phase 3: wrap `import_run` management command logic in a `@shared_task(bind=True, max_retries=3)` and wire the Beat watchdog for stuck-RUNNING batches.

---

## Session continuation — Redis/Celery refactor (Phase 3 + 4)

### Objective
- Implement Phase 3 of the Redis/Celery migration: move import execution onto Celery while preserving the synchronous `manage.py import_run` path.
- Implement the full Phase 4 slice: catalog-version cache invalidation for stats payloads, explicit stats payload classification, and service-boundary checks.

### What happened

#### Phase 3 — import execution to Celery
- Confirmed the current enqueue path only created `ImportBatch` rows and did not dispatch Celery work; the old polled worker was still the real executor.
- Added `run_import_batch` and `reset_stale_import_batches` Celery tasks.
- Added a dispatch helper so the imports UI now enqueues Celery work immediately and stores the Celery task id on `ImportBatch`.
- Kept `manage.py import_run` unchanged as the synchronous/manual path.
- Added `celery-beat` to Compose and removed the deprecated DB-polling `worker` service from the normal local stack.
- Made stale-batch recovery conservative for MVP:
  - if the worker dies before raw import commits, the batch is reset to `PENDING` and re-dispatched automatically
  - if the worker dies after the raw import commit boundary, the batch is marked `FAILED` rather than retried unsafely
- Explicitly decided not to implement post-commit automatic resume in Phase 3; that remains future hardening, not MVP scope.

#### Phase 4 — catalog version + cache policy
- Added a singleton `CatalogVersion` model with cached lookup and increment-on-success behavior.
- Updated stats cache key generation so cached stats bundles and taxonomy-gutter payloads now include catalog version.
- Cleared the cached catalog-version lookup on increment so a successful import invalidates stale stats payloads immediately without purging old payload keys.
- Added an explicit stats payload policy module and routed the three stats explorer views through it instead of leaving payload-classification decisions implicit in view code.
- Kept all current stats payload families classified as `sync+cache`; no payloads were promoted to async without timing evidence.
- Added service-boundary coverage to ensure `apps/browser/stats/queries.py` and `payloads.py` do not import the view layer.
- Improved cache instrumentation logs to record cache family as well as full key and elapsed build time.

### Files touched

#### Phase 3
- `apps/imports/models.py`
  - added `ImportBatch.celery_task_id`
- `apps/imports/migrations/0004_importbatch_celery_task_id.py`
  - added schema migration for Celery task tracking
- `apps/imports/services/import_run/api.py`
  - added `dispatch_import_batch()` to enqueue `run_import_batch` and persist the task id
- `apps/imports/services/import_run/state.py`
  - added helper paths for stale-failed and reset-to-pending batch handling used by retry/watchdog recovery
- `apps/imports/services/import_run/__init__.py`
  - exported the new dispatch helper
- `apps/imports/services/__init__.py`
  - exported the new dispatch helper at the public service boundary
- `apps/imports/views.py`
  - changed the imports home form path to dispatch Celery work immediately after queueing the batch
- `apps/imports/tasks.py`
  - added `run_import_batch` and `reset_stale_import_batches`
- `config/settings.py`
  - added Beat schedule for stale import batch recovery
- `compose.yaml`
  - added `celery-beat`
  - removed the deprecated DB-polling `worker` service from the normal stack
- `web_tests/test_import_views.py`
  - added coverage for Celery task id storage from the imports home flow
- `web_tests/test_import_tasks.py`
  - added coverage for task dispatch, retry behavior, stale pre-commit requeue, and stale post-commit failure handling
- `web_tests/test_models.py`
  - extended `ImportBatch` model expectations for `celery_task_id`

#### Phase 4
- `apps/imports/models.py`
  - added singleton `CatalogVersion`
  - added cached version lookup and cache-key constants
- `apps/imports/migrations/0005_catalogversion.py`
  - added schema migration for `CatalogVersion`
- `apps/imports/services/import_run/state.py`
  - incremented catalog version on successful import completion
- `apps/browser/stats/filters.py`
  - included catalog version in `StatsFilterState.cache_key_data()`
- `apps/browser/stats/policy.py`
  - added explicit stats payload classification and inline-build policy helpers
- `apps/browser/stats/__init__.py`
  - exported policy helpers and enums
- `apps/browser/stats/_cache.py`
  - extended cache hit/miss logging to include cache family and timing
- `apps/browser/views/stats/lengths.py`
  - routed stats payload construction through the shared stats payload policy
- `apps/browser/views/stats/codon_ratios.py`
  - routed stats payload construction through the shared stats payload policy
- `apps/browser/views/stats/codon_composition_lengths.py`
  - routed stats payload construction through the shared stats payload policy
- `web_tests/test_models.py`
  - added `CatalogVersion` singleton/cache invalidation tests
- `web_tests/_import_command.py`
  - added coverage that a successful import increments catalog version
- `web_tests/test_browser_stats.py`
  - added cache-version invalidation coverage for stats bundles and taxonomy gutter
- `web_tests/test_browser_stats_policy.py`
  - added policy classification tests and service-boundary tests for `queries.py`/`payloads.py`

### Validation
- Phase 3:
  - `python -m py_compile apps/imports/models.py apps/imports/services/import_run/state.py apps/imports/services/import_run/api.py apps/imports/views.py apps/imports/tasks.py config/settings.py web_tests/test_import_views.py web_tests/test_import_tasks.py web_tests/test_models.py`
  - `python manage.py test web_tests.test_import_views web_tests.test_import_tasks web_tests.test_import_commands web_tests.test_models`
    - `Ran 49 tests`
    - `OK`
  - `python manage.py test web_tests.test_import_process_run`
    - `Ran 15 tests`
    - `OK`
  - `python manage.py makemigrations --check --dry-run`
    - `No changes detected`
- Phase 4:
  - `python -m py_compile apps/imports/models.py apps/imports/services/import_run/state.py apps/browser/stats/filters.py web_tests/test_models.py web_tests/test_browser_stats.py web_tests/_import_command.py`
  - `python manage.py test web_tests.test_models web_tests.test_import_process_run web_tests.test_browser_stats`
    - `Ran 141 tests`
    - `OK`
  - `python -m py_compile apps/browser/stats/policy.py apps/browser/stats/__init__.py apps/browser/stats/_cache.py apps/browser/views/stats/lengths.py apps/browser/views/stats/codon_ratios.py apps/browser/views/stats/codon_composition_lengths.py web_tests/test_browser_stats_policy.py`
  - `python manage.py test web_tests.test_browser_stats_policy web_tests.test_browser_stats web_tests.test_browser_lengths web_tests.test_browser_codon_ratios web_tests.test_browser_codon_composition_lengths web_tests.test_import_process_run web_tests.test_models`
    - `Ran 180 tests`
    - `OK`
  - `python manage.py makemigrations --check --dry-run`
    - `No changes detected`

### Verification guide for Claude
- Start with schema sanity:
  - `python manage.py makemigrations --check --dry-run`
- Re-run the focused test surface:
  - `python manage.py test web_tests.test_import_views web_tests.test_import_tasks web_tests.test_import_commands web_tests.test_import_process_run web_tests.test_models`
  - `python manage.py test web_tests.test_browser_stats_policy web_tests.test_browser_stats web_tests.test_browser_lengths web_tests.test_browser_codon_ratios web_tests.test_browser_codon_composition_lengths`
- Spot-check the key implementation points in code:
  - Phase 3 enqueue path: `apps/imports/views.py`, `apps/imports/services/import_run/api.py`, `apps/imports/tasks.py`
  - Phase 3 stale-batch behavior: `apps/imports/tasks.py`, `apps/imports/services/import_run/state.py`
  - Phase 4 version bump + cache key: `apps/imports/models.py`, `apps/imports/services/import_run/state.py`, `apps/browser/stats/filters.py`
  - Phase 4 explicit policy: `apps/browser/stats/policy.py` and the three stats views
- Optional runtime check in Compose:
  - start `redis`, `postgres`, `migrate`, `web`, `celery-import-worker`, `celery-beat`
  - queue one import from `/imports/`
  - confirm the created `ImportBatch` has a non-empty `celery_task_id`
  - confirm successful import advances `CatalogVersion.version`
  - confirm a stats page miss after import uses a new cache key family/version rather than stale payloads
- Expected MVP behavior:
  - pre-commit worker failure can be retried automatically
  - post-commit worker failure should end `FAILED`, not remain stuck in `RUNNING`
  - all current stats payloads should still classify as `sync+cache`

### Current status
- Phase 3 complete for MVP:
  - imports now dispatch through Celery
  - stale `RUNNING` batches no longer hang forever
  - post-commit crashes fail visibly instead of retrying unsafely
- Phase 4 complete:
  - catalog version is stored and advanced on successful import
  - stats cache keys include catalog version
  - stats payload classification is explicit and testable
  - stats query/payload modules are guarded against view-layer imports

### Open issues
- Post-commit import resume is still intentionally unimplemented; failed batches after the raw import commit boundary require deliberate operator follow-up.
- The Phase 4 payload policy is explicit but still simple: all current stats payloads remain `sync+cache` until timing evidence justifies promotion.
- Phase 5 and beyond of the Redis/Celery refactor are still open.

### Next step
- Phase 5: extract download generation policy from views without changing the existing inline TSV streaming paths.
