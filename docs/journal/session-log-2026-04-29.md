# Session Log

**Date:** 2026-04-29

## Objective

- Implement the planned local `no_admin` mode.
- Clarify the pipeline-output import UX problem for biologist users.
- Capture a website-first GUI import plan for zipped pipeline runs.

## What happened

- Read the latest session log in `docs/journal/` and the no-admin plan in
  `docs/immpelementation/`.
- Implemented the `no_admin` setting and request-time authorization bypass:
  - lowercase `no_admin` env variable parsed into `settings.NO_ADMIN`
  - always-installed middleware after Django `AuthenticationMiddleware`
  - synthetic trusted request user with staff, superuser, and permission checks
    enabled
- Added an admin logging patch so Django admin add/change/delete actions do not
  require a persisted user when no-admin mode is active.
- Added focused no-admin tests covering imports, import history, admin index,
  and an admin add write path.
- Updated `.env.example`, `compose.yaml`, and configuration docs for
  `no_admin`.
- Corrected the Compose placement so `no_admin` is passed to the `web` service,
  where request authorization actually runs.
- Discussed why large pipeline output should not rely on a naive browser upload
  or runtime Docker mounts from the website.
- Established the intended product direction:
  - keep mounted run-folder import support for large uncompressed outputs
  - add GUI zip upload for smaller zipped outputs, expected around 5 GB max
  - store uploaded runs in app-managed persistent storage
  - extract, validate, and import through Celery without restarting the site
- Added a new implementation-planning folder for GUI pipeline run imports.

## Files touched

- `config/settings.py`
- `apps/core/no_admin.py`
- `apps/core/apps.py`
- `.env.example`
- `compose.yaml`
- `docs/configuration.md`
- `web_tests/test_no_admin.py`
- `web_tests/test_smoke.py`
- `docs/immpelementation/gui-run-imports/overview.md`
- `docs/immpelementation/gui-run-imports/implementation-details.md`

## Validation

Successful checks run:

```text
python3 -m py_compile config/settings.py apps/core/apps.py apps/core/no_admin.py web_tests/test_no_admin.py
python3 -m py_compile web_tests/test_smoke.py
git diff --check
docker compose run --rm web python manage.py test web_tests.test_smoke web_tests.test_import_views web_tests.test_no_admin
```

The focused Docker test run passed 13 tests.

Full-suite check run:

```text
docker compose run --rm web python manage.py test web_tests
```

That run reached the full test suite but failed in existing browser/import/export
areas unrelated to the no-admin tests:

- FASTA header expectation drift in `test_homorepeat_list_aa_fasta_export_streams_filtered_sequences`
- canonical catalog repeat-call count expectation mismatch
- import progress assertion mismatch
- shared download action now includes an extra `value`
- duplicate sequence import test surfaced a PostgreSQL unique-constraint error

## Current Status

- The no-admin implementation is complete at the code/test level.
- The GUI pipeline-run import design is documented but not implemented.
- The recommended next implementation work is the GUI upload/import plan in
  `docs/immpelementation/gui-run-imports/`.

## Notes

- Browser upload should be resumable/chunked for zipped runs.
- Web-triggered arbitrary Docker mounts should be avoided; that would require
  unsafe host/Docker privileges.
- Adding new runs should not require restarting the site. The planned approach
  is a persistent app-managed import library plus optional mounted run roots.

---

# Session Log

**Date:** 2026-04-29

## Objective

- Implement the GUI pipeline run import plan in small slices.
- Add a website-first upload path for zipped pipeline runs without breaking
  the existing mounted/manual publish-root import flow.

## What happened

- Reviewed the new GUI run import design notes and turned them into a staged
  implementation roadmap with commit names per slice.
- Implemented the early safety and discovery work:
  - manual publish-root validation now checks the manifest and runs
    `inspect_published_run()`
  - detected-run discovery now has a root-specific helper
- Added the storage and model foundation:
  - new import storage settings in `config/settings.py` and `.env.example`
  - persistent `homorepeat_imports` Compose volume mounted into `web` and
    `celery-import-worker`
  - new `UploadedRun` model, admin registration, and migration
- Built the upload API and front-end plumbing:
  - staff-only `upload-start`, `upload-chunk`, and `upload-complete` endpoints
  - resumable chunk storage with temp-file writes and atomic rename
  - CSRF-aware upload JavaScript scaffold
  - upload form and recent uploaded-run status table on `/imports/`
- Implemented the extraction pipeline:
  - `extract_uploaded_run` Celery task
  - assembly of `source.zip` from chunk files
  - safe zip extraction with traversal, symlink, file-count, and extracted-size
    checks
  - extracted publish-root validation with `inspect_published_run()`
  - atomic move/copy into `/data/imports/library/<run-id>/publish`
  - ready-state tracking for valid uploaded runs
- Updated the imports page to merge mounted runs and ready library runs.
- Kept the existing manual path import flow working while the upload path was
  being added.

## Files touched

- `config/settings.py`
- `.env.example`
- `compose.yaml`
- `apps/imports/forms.py`
- `apps/imports/views.py`
- `apps/imports/urls.py`
- `apps/imports/models.py`
- `apps/imports/admin.py`
- `apps/imports/migrations/0006_uploadedrun.py`
- `apps/imports/services/uploads.py`
- `apps/imports/tasks.py`
- `templates/imports/home.html`
- `static/js/import_uploads.js`
- `web_tests/test_import_views.py`
- `web_tests/test_import_uploads.py`
- `web_tests/test_import_tasks.py`
- `docs/immpelementation/gui-run-imports/implementation-details.md`
- `docs/immpelementation/gui-run-imports/implementation_roadmap.md`

## Validation

Successful checks run during the session included:

```text
docker compose config
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test web_tests.test_import_views
docker compose run --rm web python manage.py test web_tests.test_import_uploads
docker compose run --rm web python manage.py test web_tests.test_import_tasks
docker compose run --rm web python manage.py test web_tests.test_import_views web_tests.test_import_uploads web_tests.test_import_tasks
```

## Current Status

- The GUI upload path is implemented through extraction and library placement.
- `/imports/` now shows both mounted runs and ready uploaded runs.
- Manual path import is still present and not yet moved into an advanced UI
  section.

## Open Issues

- Uploaded-run import queueing is not implemented yet.
- Cleanup for stale failed or incomplete uploads is not implemented yet.
- The imports page still needs the manual-path advanced-section polish.

## Next Step

- Move the manual publish-root import form into an advanced `<details>` block
  and finish the remaining imports-page UX polish.
