# Session Log

**Date:** 2026-04-24

## Objective
Complete the Redis/Celery refactor (Phases 5–8) documented in `docs/implementation/redis_celery_refactor/implementation_plan.md`.

---

## Phase 5 — Download generation policy extracted from views

### What happened
- Created a `DownloadBuild` model for durable async download artifact tracking with status lifecycle `PENDING → BUILDING → READY / FAILED / EXPIRED`.
- Created `apps/browser/downloads.py` as the single service boundary for download classification and build management:
  - `DownloadBuildType` enum covering all 21 download types
  - `DownloadClassification` enum (`SYNC`, `ASYNC_ARTIFACT`)
  - `classify_download()` — all types currently classified `SYNC`; `_ASYNC_ARTIFACT_TYPES` is an empty frozenset ready to gate future async promotion
  - `get_or_create_download_build()` — idempotent build lookup; reuses PENDING/BUILDING/READY builds, creates fresh PENDING for FAILED/EXPIRED
- Created `apps/browser/views/downloads.py` — `DownloadBuildStatusView` serving `GET /browser/downloads/<pk>/status/` as a JSON endpoint
- Added migration `0023_download_build.py`
- Wired `DownloadBuild` into `apps/browser/models/__init__.py`, the URL config, and the views `__init__.py`
- Added 18 tests in `web_tests/test_browser_downloads.py` covering classification, model lifecycle, `get_or_create` reuse logic, the status endpoint, and service-boundary isolation

### Files touched
- `apps/browser/models/downloads.py` (new)
- `apps/browser/migrations/0023_download_build.py` (new)
- `apps/browser/downloads.py` (new)
- `apps/browser/views/downloads.py` (new)
- `web_tests/test_browser_downloads.py` (new)
- `apps/browser/models/__init__.py` — added `DownloadBuild`
- `apps/browser/views/__init__.py` — added `DownloadBuildStatusView`
- `apps/browser/urls.py` — added `downloads/<int:pk>/status/`

---

## Phase 6 — Payload queues introduced selectively

### What happened
- Created a `PayloadBuild` model for durable async stats bundle builds with status lifecycle `PENDING → BUILDING → READY / FAILED`, a `UniqueConstraint` on `(build_type, scope_key, catalog_version)`, and an atomic claim pattern (`PENDING → BUILDING` via `.update()`) to prevent double-execution.
- Created `apps/browser/stats/warmup.py`:
  - `WARMUP_BUILD_TYPES` — the four bundle types to pre-warm after each import
  - `default_warmup_scope_params()` — global unfiltered scope params dict
  - `compute_scope_key()` — SHA1 hash of scope params
  - `get_bundle_builders()` — lazy-imported builder registry keyed by build type string
- Created `apps/browser/tasks.py` with three tasks:
  - `run_post_import_warmup` — fan-out: creates one `PayloadBuild` per `WARMUP_BUILD_TYPES` via `get_or_create`, dispatches `warm_stats_bundle` only for freshly created rows (idempotent)
  - `warm_stats_bundle` — atomically claims a `PayloadBuild`, reconstructs filter state from `scope_params`, calls the bundle builder, marks `READY`; retries up to 3 times resetting to `PENDING` each attempt, marks `FAILED` after all retries exhausted
  - `generate_download_artifact` — stub raising `NotImplementedError`; activated by adding a type to `_ASYNC_ARTIFACT_TYPES`
- Created `apps/browser/views/payloads.py` — `PayloadBuildStatusView` serving `GET /browser/payload-builds/<pk>/status/`
- Extracted `_resolve_branch_scope_from_params(branch, branch_q)` from the view-layer `_resolve_branch_scope(request)` in `apps/browser/views/filters.py` so filter state can be reconstructed without an HTTP request
- Added `build_stats_filter_state_from_params(params: dict)` to `apps/browser/stats/filters.py` for use by Celery tasks
- Wired post-import warmup dispatch into `apps/imports/services/import_run/state.py` via `celery_app.send_task()` by string name to avoid a circular import; swallows all exceptions with a warning log so import failures never cascade from warmup dispatch
- Added migration `0024_payload_build.py`
- Added 33 tests in `web_tests/test_browser_payload_builds.py` covering the model, warmup helpers, filter-state reconstruction, fan-out idempotency, atomic claim, retry-to-FAILED progression, the status endpoint, and dispatch error-swallowing

### Files touched
- `apps/browser/models/payloads.py` (new)
- `apps/browser/migrations/0024_payload_build.py` (new)
- `apps/browser/stats/warmup.py` (new)
- `apps/browser/tasks.py` (new)
- `apps/browser/views/payloads.py` (new)
- `web_tests/test_browser_payload_builds.py` (new)
- `apps/browser/models/__init__.py` — added `PayloadBuild`
- `apps/browser/views/filters.py` — extracted `_resolve_branch_scope_from_params`
- `apps/browser/stats/filters.py` — added `build_stats_filter_state_from_params`
- `apps/browser/stats/__init__.py` — exported `build_stats_filter_state_from_params`
- `apps/browser/views/__init__.py` — added `PayloadBuildStatusView`
- `apps/browser/urls.py` — added `payload-builds/<int:pk>/status/`
- `apps/imports/services/import_run/state.py` — dispatch warmup after successful catalog version increment

---

## Phase 7 — Worker pools split and concurrency tuned

### What happened
- Updated `CELERY_TASK_ROUTES` in `config/settings.py` to add an explicit route for `generate_download_artifact` to the `downloads` queue before the `apps.browser.tasks.*` wildcard (which routes everything else to `payload_graph`). Celery evaluates routes in insertion order so the specific name wins.
- Replaced `celery-payload-worker` in `compose.yaml` (which served both `payload_graph` and `downloads` from one pool at `-c 4`) with two independent services:
  - `celery-graph-worker` — queue `payload_graph`, `--autoscale 4,1` (idles at 1 worker, scales to 4 during post-import fan-out)
  - `celery-download-worker` — queue `downloads`, `-c 2 --prefetch-multiplier 1` (low concurrency, no prefetch so large artifact jobs do not block the pool)
- The three queue pools (`imports`, `payload_graph`, `downloads`) are now fully independent and cannot starve each other.

### Files touched
- `config/settings.py` — added `generate_download_artifact` explicit route to `downloads`
- `compose.yaml` — replaced `celery-payload-worker` with `celery-graph-worker` + `celery-download-worker`

---

## Phase 8 — Cleanup, invalidation, and operational hardening

### What happened

#### Remove DB-polled worker path
- Deleted `apps/imports/management/commands/import_worker.py` — the DB-sleep-poll loop is fully replaced by `celery-import-worker` and the Beat watchdog
- Removed its four associated tests from `web_tests/_import_command.py` and `web_tests/test_import_commands.py`

#### Remove obsolete view-coupled payload scaffolding
- Removed `build_stats_payload()` from `apps/browser/stats/policy.py` — it was always `return build_fn()` with no routing behavior; the caching is already done by the bundle builders via `build_or_get_cached`
- Also removed unused `Callable` and `TypeVar` imports from `policy.py`
- Removed `build_stats_payload` from `stats/__init__.py` exports
- Updated `_build_payload()` in all three stats explorer views to call `build_fn()` directly instead of delegating through the removed function
- Removed `build_stats_payload` from the view-layer imports in all three files
- Updated `web_tests/test_browser_stats_policy.py` to remove the two tests that specifically exercised the removed function

The `StatsPayloadType` enum and `classify_stats_payload()` are intentionally kept — they are the classification infrastructure that will be needed when async routing is eventually wired up. Only the routing execution function was removed.

#### Artifact cleanup for expired download builds
- Added `expire_stale_download_builds` task to `apps/browser/tasks.py`:
  - PENDING/BUILDING rows older than 1 hour → `EXPIRED` (stuck jobs)
  - READY rows older than 7 days → `EXPIRED` (artifact retention window)
- Routed it explicitly to the `downloads` queue in `CELERY_TASK_ROUTES`
- Added it to `CELERY_BEAT_SCHEDULE` running every 6 hours
- Added 6 tests in `web_tests/test_browser_downloads.py` covering stuck-pending, stuck-building, aged-ready, recent-pending, recent-ready, and zero-work cases

#### Catalog-version invalidation (already complete from Phase 6)
- `StatsFilterState.cache_key()` already includes `CatalogVersion.cached_current()`
- `CatalogVersion.increment()` already deletes the cached version entry on every successful import
- No further code changes needed; this path was confirmed correct

### Files touched
- `apps/imports/management/commands/import_worker.py` (deleted)
- `apps/browser/stats/policy.py` — removed `build_stats_payload`, removed unused imports
- `apps/browser/stats/__init__.py` — removed `build_stats_payload` from exports
- `apps/browser/views/stats/lengths.py` — removed `build_stats_payload` import, simplified `_build_payload`
- `apps/browser/views/stats/codon_ratios.py` — same
- `apps/browser/views/stats/codon_composition_lengths.py` — same
- `apps/browser/tasks.py` — added `expire_stale_download_builds`
- `config/settings.py` — added `expire_stale_download_builds` to beat schedule and task routes
- `web_tests/_import_command.py` — removed four `import_worker` test methods
- `web_tests/test_import_commands.py` — removed four `import_worker` test names
- `web_tests/test_browser_stats_policy.py` — removed two tests for `build_stats_payload`
- `web_tests/test_browser_downloads.py` — added 6 expiry task tests

---

## Validation

Final full-suite run after all Phase 8 changes:

```
python manage.py test web_tests
Ran 386 tests in 27.550s
OK (skipped=2)
```

---

## Current status
- Phase 5 complete — download policy extracted, `DownloadBuild` model in place
- Phase 6 complete — `PayloadBuild` model, warmup tasks, post-import fan-out
- Phase 7 complete — three independent worker pools with tuned concurrency
- Phase 8 complete — DB-polling worker removed, dead scaffolding cleaned, expiry task operational
- **Redis/Celery refactor is complete**

---

## Open items (deferred by design)
- `_ASYNC_ARTIFACT_TYPES` is empty — all downloads remain inline/SYNC. Promote a type to `ASYNC_ARTIFACT` and implement `generate_download_artifact` when a download is large enough to warrant async generation.
- `classify_stats_payload` always returns `SYNC_CACHE`. Promote a payload type to `ASYNC_PERSISTED` and wire the `PayloadBuildStatusView` frontend polling path when timing evidence justifies it.
- Post-commit import resume is still intentionally unimplemented. Failed batches after the raw import commit boundary require deliberate operator follow-up.

## Next step
- Commit the Phase 5–8 work on the `redis-celery-refactor` branch and open a PR against `main`.
