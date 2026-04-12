# Cleanup Module Map

## Purpose

This document maps the current monolithic Python modules to the target package
layout for the cleanup program.

The target layout is organized by domain and responsibility, with stable
top-level re-export surfaces preserved for callers.

## Current Hotspots

| Area | Current module | Current problem |
| --- | --- | --- |
| Browser views | `apps/browser/views.py` | Shared base classes, domain views, query helpers, cursor helpers, filter resolution, and navigation helpers are all mixed together |
| Browser merged logic | `apps/browser/merged.py` | Accession summaries, merged grouping, identity rules, and numeric helpers share one file |
| Browser models | `apps/browser/models.py` | Core run models, taxonomy, entity tables, repeat calls, and operational tables all live together |
| Import parser | `apps/imports/services/published_run.py` | Artifact resolution, manifest logic, contract types, load flow, and row iterators share one file |
| Import execution | `apps/imports/services/import_run.py` | Public service API, state transitions, COPY helpers, retained-row prep, taxonomy rebuild, entity writers, and operational writers are mixed together |
| Tests | `web_tests/test_browser_views.py`, `web_tests/test_import_command.py`, related large files | Tests still follow the old monolithic runtime layout |

## Stable Surfaces To Preserve

These import paths should keep working after the split:

- `apps.browser.views`
- `apps.browser.merged`
- `apps.browser.models`
- `apps.imports.services`
- `apps.imports.services.import_run`
- `apps.imports.services.published_run`

The cleanup should preserve those surfaces through package `__init__.py`
re-exports rather than forcing broad call-site churn.

## Target Browser View Layout

### Stable surface

- `apps/browser/views/__init__.py`

### Support modules

- `apps/browser/views/base.py`
  - `BrowserListView`
- `apps/browser/views/pagination.py`
  - `CursorPaginator`
  - `CursorPage`
  - `CursorPaginatedListView`
  - `VirtualScrollListView`
- `apps/browser/views/cursor.py`
  - cursor token encode/decode
  - ordering reversal
  - cursor filter helpers
- `apps/browser/views/filters.py`
  - run, batch, branch, and entity filter resolution
  - branch-scope helper logic
  - repeat-call filter helper builders
- `apps/browser/views/querysets.py`
  - annotated run/genome/sequence/protein query helpers
  - subquery-based count annotations
- `apps/browser/views/navigation.py`
  - browser directory sections
  - URL query helpers
- `apps/browser/views/formatting.py`
  - ordering labels
  - record sorting
  - numeric parsing

### Domain modules

- `apps/browser/views/home.py`
- `apps/browser/views/runs.py`
- `apps/browser/views/taxonomy.py`
- `apps/browser/views/genomes.py`
- `apps/browser/views/sequences.py`
- `apps/browser/views/proteins.py`
- `apps/browser/views/repeat_calls.py`
- `apps/browser/views/accessions.py`
- `apps/browser/views/operations.py`

## Target Browser Merged Layout

### Stable surface

- `apps/browser/merged/__init__.py`

### Modules

- `apps/browser/merged/accessions.py`
  - accession-group querysets
  - accession summary assembly
- `apps/browser/merged/proteins.py`
  - merged protein grouping helpers
- `apps/browser/merged/repeat_calls.py`
  - merged repeat-call grouping helpers
- `apps/browser/merged/identity.py`
  - identity keys
  - representative-row selection
  - collapse rules
- `apps/browser/merged/metrics.py`
  - purity formatting
  - numeric helper logic

## Target Browser Model Layout

### Stable surface

- `apps/browser/models/__init__.py`

### Modules

- `apps/browser/models/base.py`
- `apps/browser/models/runs.py`
- `apps/browser/models/taxonomy.py`
- `apps/browser/models/genomes.py`
- `apps/browser/models/repeat_calls.py`
- `apps/browser/models/operations.py`

Expected ownership:

- `runs.py`: `PipelineRun`, `AcquisitionBatch`
- `taxonomy.py`: `Taxon`, `TaxonClosure`
- `genomes.py`: `Genome`, `Sequence`, `Protein`
- `repeat_calls.py`: `RunParameter`, `RepeatCall`
- `operations.py`: `DownloadManifestEntry`, `NormalizationWarning`,
  `AccessionStatus`, `AccessionCallCount`

## Target Import Parser Layout

### Stable surface

- `apps/imports/services/published_run/__init__.py`

### Modules

- `apps/imports/services/published_run/contracts.py`
- `apps/imports/services/published_run/artifacts.py`
- `apps/imports/services/published_run/manifest.py`
- `apps/imports/services/published_run/iterators.py`
- `apps/imports/services/published_run/load.py`

Expected ownership:

- `contracts.py`: dataclasses and parser-facing contract types
- `artifacts.py`: required path discovery and inspection
- `manifest.py`: manifest loading and validation
- `iterators.py`: TSV row readers
- `load.py`: high-level parsed-run assembly

## Target Import Execution Layout

### Stable surface

- `apps/imports/services/import_run/__init__.py`

### Modules

- `apps/imports/services/import_run/api.py`
- `apps/imports/services/import_run/state.py`
- `apps/imports/services/import_run/copy.py`
- `apps/imports/services/import_run/prepare.py`
- `apps/imports/services/import_run/taxonomy.py`
- `apps/imports/services/import_run/entities.py`
- `apps/imports/services/import_run/operational.py`
- `apps/imports/services/import_run/orchestrator.py`

Expected ownership:

- `api.py`: public service entrypoints
- `state.py`: import phases, batch claiming, progress reporting, completion and
  failure handling
- `copy.py`: PostgreSQL COPY helpers and row serialization
- `prepare.py`: retained-row discovery and FASTA subset loading
- `taxonomy.py`: taxon upsert and closure rebuild
- `entities.py`: genome, sequence, protein, and repeat-call creation
- `operational.py`: run parameters, download manifest rows, normalization
  warnings, accession status rows, accession call count rows
- `orchestrator.py`: transaction-heavy import assembly if `api.py` would
  otherwise become too large

## Target Test Layout

Recommended runtime-aligned test split:

- `web_tests/test_browser_home_runs.py`
- `web_tests/test_browser_taxa_genomes.py`
- `web_tests/test_browser_sequences.py`
- `web_tests/test_browser_proteins.py`
- `web_tests/test_browser_repeat_calls.py`
- `web_tests/test_browser_accessions.py`
- `web_tests/test_browser_operations.py`
- `web_tests/test_browser_merged.py`
- `web_tests/test_import_commands.py`
- `web_tests/test_import_published_run.py`
- `web_tests/test_import_process_run.py`
- `web_tests/test_import_views.py`

## Dependency Direction Rules

These rules should hold after the split:

- browser domain view modules may depend on browser support modules
- browser support modules must not depend on browser domain view modules
- merged helpers must not depend on browser views
- import parser modules must not depend on import execution modules
- import execution modules may depend on parser modules and browser metadata or
  models where needed
- tests should prefer public package surfaces unless directly targeting a
  private helper
