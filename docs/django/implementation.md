# HomoRepeat Raw-Mode Refactor Architecture

## Summary

This document replaces the earlier flat-TSV import plan.

`homorepeat` must now align with the current pipeline contract in
`../homorepeat_pipeline/`, specifically the current `raw` publish mode.

The app should be structured around two clearly separated layers:

- canonical raw imported truth
- derived merged or deduplicated browsing views

The canonical raw layer must preserve what the pipeline actually emitted,
including batch structure and operational provenance. The merged layer exists
only as a reproducible browsing convenience built on top of that raw truth.

## Current Implementation Status

As of `2026-04-11`, the raw import refactor, browser work, merged redesign,
and acceptance sweep are implemented and validated against the real pipeline
outputs.

Implemented:

- raw publish discovery from `publish/metadata/run_manifest.json`
- batch-scoped acquisition import from `publish/acquisition/batches/<batch_id>/`
- run-level import of `repeat_calls.tsv`, `run_params.tsv`,
  `accession_status.tsv`, and `accession_call_counts.tsv`
- relational storage for:
  - `AcquisitionBatch`
  - `DownloadManifestEntry`
  - `NormalizationWarning`
  - `AccessionStatus`
  - `AccessionCallCount`
- residue-scoped `RunParameter` import
- `seed_extend` support across parser, schema, and import logic
- database-backed storage of matched CDS and protein sequence content
- queued/background import execution via `ImportBatch`
- Postgres-first heartbeat and progress reporting during long imports
- PostgreSQL bulk-load path for the largest imported tables
- run-first raw browser pages backed by imported database state only
- operational artifact browsers for normalization warnings, accession status,
  accession call counts, and download manifest entries
- contextual cross-links between runs, accessions, proteins, repeat calls, and
  operational provenance
- cursor pagination and virtual-scroll fragments on the largest raw list pages
- derived merged browsing built over imported raw evidence with
  method-sensitive identities:
  - protein-level `(accession, protein_id, method)`
  - residue-level `(accession, protein_id, method, residue)`
- evidence-first merged summaries with contributing-run counts, source-row
  counts, representative evidence rows, and backlinks to raw proteins and
  repeat calls
- operator-facing documentation for the Docker-first import boundary and
  Postgres-backed runtime model

Current storage/runtime behavior:

- the app stores all raw repeat calls and supporting provenance rows in
  PostgreSQL
- the app stores only call-linked `Sequence` and `Protein` rows, not the full
  raw sequence/protein inventories
- raw mode remains canonical imported truth
- merged mode remains a derived browsing layer over imported raw evidence
- the running website serves from PostgreSQL after import and does not depend
  on direct runtime reads of pipeline TSV files

Validated behavior:

- focused acceptance suite passes:
  - `python3 manage.py test web_tests.test_import_command web_tests.test_import_views web_tests.test_browser_views web_tests.test_browser_merge_views web_tests.test_merged_helpers`
- small real run `live_raw_effective_params_2026_04_09` imports successfully in
  Docker + Postgres:
  - `1` genome
  - `303` proteins
  - `608` repeat calls
- large real run `chr_all3_raw_2026_04_09` imports successfully in Docker +
  Postgres:
  - `905` genomes
  - `382649` proteins
  - `1395494` repeat calls
- the large run imports `pure`, `threshold`, and `seed_extend` into both
  `RunParameter` and `RepeatCall`
- imported browser routes return successfully on loaded data for:
  - `/browser/`
  - `/browser/runs/`
  - `/browser/runs/<pk>/`
  - merged accession and repeat-call browse paths

No required refactor slices remain. Any further work is follow-up UX polish or
evidence-driven profiling rather than contract or semantics cleanup.

## Source Of Truth

The authoritative contract lives in the sibling pipeline repository:

- `../homorepeat_pipeline/docs/contracts.md`
- `../homorepeat_pipeline/docs/operations.md`
- `../homorepeat_pipeline/docs/methods.md`
- `../homorepeat_pipeline/runs/live_raw_effective_params_2026_04_09/`
- `../homorepeat_pipeline/runs/chr_all3_raw_2026_04_09/`

`homorepeat` should not preserve earlier assumptions unless they are confirmed
by those sources.

## Actual Raw Publish Contract

### Run-level authoritative files

The current run-level raw interface is:

- `publish/metadata/run_manifest.json`
- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/status/accession_status.tsv`
- `publish/status/accession_call_counts.tsv`

Important points:

- `publish/metadata/run_manifest.json` is the authoritative manifest path.
- `publish/calls/repeat_calls.tsv` is still the canonical downstream call table,
  even in raw mode.
- `publish/calls/run_params.tsv` is now keyed by
  `(method, repeat_residue, param_name)`.
- supported methods are `pure`, `threshold`, and `seed_extend`.

### Batch-scoped acquisition files

In raw mode, acquisition outputs are not flat under `publish/acquisition/`.
They are published under:

- `publish/acquisition/batches/<batch_id>/`

Each batch currently contains:

- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- `cds.fna`
- `proteins.faa`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

### Scientific meaning of the main tables

- `genomes.tsv`
  One row per assembly-level genome or accession unit.
- `taxonomy.tsv`
  One row per taxon in the imported lineage materialization.
- `sequences.tsv`
  One row per retained CDS or translation-source nucleotide sequence.
- `proteins.tsv`
  One row per retained translated or provided protein.
- `repeat_calls.tsv`
  One row per detected homorepeat tract with method-specific semantics
  normalized into one shared schema.
- `run_params.tsv`
  One row per method, repeat residue, and parameter value used for the run.
- `download_manifest.tsv`
  One row per accession download attempt within a batch.
- `normalization_warnings.tsv`
  One row per acquisition or normalization warning with explicit scope and
  provenance.
- `accession_status.tsv`
  One row per requested accession summarizing acquisition and detection outcome.
- `accession_call_counts.tsv`
  One row per accession, method, and residue summarizing emitted calls.

## Incorrect Legacy Assumptions To Remove

The current app still encodes several assumptions that are now false:

- manifest path is `publish/manifest/run_manifest.json`
- acquisition tables are flat under `publish/acquisition/*.tsv`
- sequence rows contain `sequence_path`
- protein rows contain `protein_path`
- genome rows contain canonical `download_path`
- repeat calls contain canonical `source_file`
- taxonomy should be compacted before storage and treated as the stored truth
- only `pure` and `threshold` methods exist
- `repeat_residue` is encoded as an ordinary parameter row rather than a
  first-class dimension on run parameters
- only repeat-linked sequence and protein rows matter to raw provenance

These need to be removed rather than preserved behind compatibility shims.

## Canonical Storage Model

### Design rule

Raw imported truth is canonical.

Merged or deduplicated views must always be derived from canonical raw storage
and remain traceable back to contributing raw records.

### Database choice

Use a relational database, specifically PostgreSQL.

Reasoning:

- the data model is structured and relational
- the product needs exact filters, joins, provenance, and traceability
- the main access patterns are by run, accession, taxon, method, residue,
  protein, and coordinates
- there is no current requirement for nearest-neighbor similarity search over
  learned embeddings

A vector database is not the right primary store for this product.

If vector search becomes useful later, the simplest path is to add vector
columns to PostgreSQL with `pgvector` rather than introducing a separate vector
database now. `pgvector` is explicitly for vector similarity search and
embeddings, which is not the current workload:

- <https://github.com/pgvector/pgvector>

### Runtime dependency model

The app must not depend on the pipeline pod's local TSV files after import.

The intended runtime model is:

- TSV and JSON files are the ingestion contract
- PostgreSQL is the canonical runtime store for all app queries
- every raw table needed for browsing, filtering, provenance, and merged views
  is imported into the app-owned database
- optional preservation of original published artifacts, if desired, must use
  app-owned storage such as object storage or uploaded blobs, not direct reads
  from the pipeline pod filesystem

That means:

- regular list and detail pages read from Postgres after import
- no normal page request should require opening a pipeline-produced TSV
- the importer may use TSVs once, but the running app must be self-contained

### Deployment boundary

For the current implementation, optimize for Docker-first deployment.

Practical rule:

- the importer may read a run from a mounted path or copied artifact location
- after import, the app serves from Postgres only
- no serving path should depend on direct runtime access to the pipeline files

If the deployment later moves to a more distributed environment, the same rule
still applies: import once, then serve from the database.

### Canonical storage approach

Use a self-contained raw storage model:

- import relationally all raw tables needed for the product's truth layer
- preserve raw versus merged separation inside the database, not by keeping part
  of the truth only in files
- treat original artifacts as optional reproducibility attachments rather than a
  required serving dependency

Important scope limit:

- store the repeat call records
- store the proteins and CDS rows linked to those calls
- store the genome, taxon, parameter, and provenance rows needed to explain and
  browse those calls
- do not store the entire raw sequence and protein inventories if the product
  does not need them

This is the best tradeoff for the current product and machine targets.

This is the correct boundary for a split deployment where pipeline, database,
and web app run as separate services.

## Data Model

### Core provenance models

- `PipelineRun`
  one imported pipeline run keyed by pipeline `run_id`
- `ImportBatch`
  stores one import attempt into the Django app
- `AcquisitionBatch`
  stores one raw acquisition batch under one imported run

`AcquisitionBatch` should include:

- `pipeline_run`
- `batch_id`
- batch-scoped artifact paths
- counts for genomes, taxonomy rows, sequences, proteins, warnings, downloads
- optional validation payload or path metadata from `acquisition_validation.json`

### Raw biological models

- `Taxon`
- `TaxonClosure`
- `Genome`
- `Sequence`
- `Protein`
- `RepeatCall`
- `RunParameter`

Required model changes:

- `Genome` should gain `acquisition_batch`
- `RunParameter` must include `repeat_residue`
- `RunParameter` uniqueness must become
  `(pipeline_run, method, repeat_residue, param_name)`
- `RepeatCall` and `RunParameter` must accept `seed_extend`
- deleted contract fields should be removed from the relational schema:
  - `Genome.download_path`
  - `Sequence.sequence_path`
  - `Protein.protein_path`
  - `RepeatCall.source_file`

`Sequence` and `Protein` should represent the call-linked subset only.

This subset should be defined explicitly:

- a `Sequence` row is stored only if at least one imported repeat call points to
  its `sequence_id`
- a `Protein` row is stored only if at least one imported repeat call points to
  its `protein_id`

The full inventory size should still remain visible via counts on
`AcquisitionBatch` and genome-level summary fields where needed.

### Provenance and operational models

Add relational models for raw side artifacts:

- `DownloadManifestEntry`
- `NormalizationWarning`
- `AccessionStatus`
- `AccessionCallCount`

These should remain queryable in the app, not just stored as loose files.

Suggested ownership:

- `DownloadManifestEntry` belongs to `AcquisitionBatch`
- `NormalizationWarning` belongs to `AcquisitionBatch`
- `AccessionStatus` belongs to `PipelineRun` and references `AcquisitionBatch`
  by batch ID or FK when resolvable
- `AccessionCallCount` belongs to `PipelineRun` and references
  `AccessionStatus` or accession plus batch scope

Optional reproducibility storage:

- if the product needs downloadable originals later, store copied artifact
  payloads or uploaded files in app-owned storage
- do not model pipeline pod paths as a required runtime dependency

## Import Architecture

### Execution model

Real raw imports will likely be long-running and must not depend on a blocking
web request.

Use this execution model:

- the web UI creates an `ImportBatch` row and queues an import job
- the default implementation can run the import in a simple background worker
  process or operator-launched management command inside the Docker deployment
- a broker-backed queue or orchestration-specific job runner is optional and
  should be added only if the deployment later needs it
- the import runner and the management command both call the same import
  service layer
- the UI polls or streams status from the database rather than waiting for the
  import request to finish

This keeps the architecture simple while still allowing responsive imports.

### Responsiveness requirements

The import path should remain observable while it is running.

Required behavior:

- import state persists in the database
- the current phase is visible
- progress counters are updated at batch and chunk boundaries
- a heartbeat timestamp proves the worker is still alive during long phases
- failures record both the failing phase and the last known progress

Suggested progress phases:

- validating contract
- discovering batches
- importing taxonomy
- importing genomes
- importing sequences
- importing proteins
- importing warnings and statuses
- importing repeat calls
- finalizing import

Suggested `ImportBatch` additions:

- `job_status`
- `phase`
- `progress_payload`
- `heartbeat_at`

`progress_payload` can hold counters such as:

- batches discovered
- batches imported
- genomes imported
- sequences imported
- proteins imported
- warnings imported
- status rows imported
- repeat calls imported

### Supported mode

The importer should support only `raw` publish mode in this refactor.

Behavior:

- import `raw` runs
- reject `merged` runs with a clear contract error
- keep the code structured so `merged` can be added later without redesigning
  the raw model

### Import inputs

Required run-level inputs:

- `publish/metadata/run_manifest.json`
- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/status/accession_status.tsv`
- `publish/status/accession_call_counts.tsv`

Required batch-level inputs per discovered batch:

- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

### Import order

Recommended transactional order:

1. validate manifest and raw publish mode
2. create `ImportBatch`
3. create or replace `PipelineRun`
4. discover and register `AcquisitionBatch` rows
5. import full taxonomy and rebuild closure
6. import `Genome` rows with batch provenance
7. import `RunParameter`
8. import `AccessionStatus`
9. import `AccessionCallCount`
10. import `DownloadManifestEntry`
11. import `NormalizationWarning`
12. import call-linked `Sequence`
13. import call-linked `Protein`
14. import `RepeatCall`

### Transaction and progress model

The import must balance progress visibility with replacement safety.

Rules:

- small setup work may commit early so the operator immediately sees a running
  import record
- long row imports should update progress incrementally instead of hiding
  inside one opaque request
- replacement of an already imported run should be safe and explicit

Acceptable implementation patterns include:

- a straightforward run-scoped transactional replace for the first
  implementation
- staging tables only if simple replacement proves too risky or too slow
- phase-bounded transactions with careful replacement semantics

The product requirement is:

- progress remains visible during long imports
- failures do not leave an existing imported run half-replaced
- the operator can tell whether the import is alive

### Call-linked sequence and protein import

The relational `Sequence` and `Protein` tables should represent only the
sequence and protein rows linked to imported repeat calls.

Rules:

- determine the referenced `sequence_id` and `protein_id` set from
  `repeat_calls.tsv`
- import only the batch-scoped `sequences.tsv` and `proteins.tsv` rows needed
  for those referenced IDs
- keep batch-level counts for reconciliation and monitoring
- optimize import for scale with PostgreSQL-native bulk loading rather than
  ORM-heavy row-by-row insertion

Implementation guidance:

- parse large tables in chunks
- prefer PostgreSQL `COPY` or equivalent copy-style loading paths for the
  largest tables such as `repeat_calls`
- use ORM `bulk_create()` only for smaller tables or as a fallback path
- update `ImportBatch` progress after each chunk or batch
- avoid ORM row-by-row inserts for the largest tables

### Derived view strategy

Merged and deduplicated browsing should start as ordinary SQL queries or views
over the canonical raw tables.

Do not start with materialized views unless query profiling shows the derived
views are too slow.

### Browse performance model

The website's hot path is browse and filter performance, especially on repeat
calls.

Design the schema around that fact:

- `RepeatCall` is the primary browse table
- `Protein` is the secondary browse table
- `Sequence` is mostly detail or provenance support

For fast list filtering, denormalize a small set of stable filter fields onto
the hot tables rather than forcing joins on every request.

Recommended `RepeatCall` browse columns in addition to the canonical IDs and
FKs:

- `accession`
- `gene_symbol`
- `protein_name`
- `protein_length`
- `taxon_id`
- `pipeline_run_id`
- `method`
- `repeat_residue`
- `start`
- `end`
- `length`
- `purity`

Recommended `Protein` browse columns:

- `accession`
- `gene_symbol`
- `protein_name`
- `protein_length`
- `taxon_id`
- `pipeline_run_id`
- `repeat_call_count`

This is intentional duplication for read performance, not a replacement for raw
provenance.

### Large-text storage strategy

Keep the hot rows narrow.

Rules:

- do not load large text columns on list pages
- keep protein and CDS sequence strings out of the default list projections
- keep `aa_sequence` and `codon_sequence` out of default repeat-call list
  projections

If row width becomes a measurable bottleneck, split large text payloads into
detail-oriented companion tables rather than widening the hot browse rows.

PostgreSQL can store large text efficiently via TOAST, but the app should still
avoid selecting large text on hot list queries:

- <https://www.postgresql.org/docs/current/storage-toast.html>

### Index strategy

Prefer the minimum useful index set for the first implementation.

Keep:

- primary and unique keys
- composite indexes that support the core run, accession, method, residue, and
  taxon filters
- indexes needed for FK joins on the largest tables

Recommended first-pass indexes:

- on `RepeatCall`:
  - `(pipeline_run_id, method, repeat_residue, length, id)`
  - `(pipeline_run_id, accession, id)`
  - `(pipeline_run_id, taxon_id, id)`
  - `(pipeline_run_id, protein_id, id)`
- on `Protein`:
  - `(pipeline_run_id, accession, id)`
  - `(pipeline_run_id, gene_symbol, id)`
  - `(pipeline_run_id, taxon_id, id)`
- on `Genome`:
  - `(pipeline_run_id, accession)`
  - `(pipeline_run_id, taxon_id)`

The exact ordering should match the final query shapes, but the key rule is:

- align composite indexes with real filter plus sort combinations
- do not rely on many single-column indexes for multi-column browse queries

Defer unless profiling proves they are needed:

- broad text-search indexes
- many low-selectivity secondary indexes on `Sequence` and `Protein`
- partitioning of large tables

Partitioning is viable later, but it is not the best first optimization.

### Deliberate deferrals

Do not build these in the first implementation unless profiling or concrete
operational requirements force them:

- a broker-backed worker system
- table partitioning
- materialized views for merged browsing
- external search infrastructure
- broad text search over the stored sequence and protein tables

These are viable techniques, but they should be introduced only after the
basic raw import path and core browse queries are proven.

### Search and pagination policy

Default search behavior should be index-friendly.

Prefer:

- exact match
- prefix match
- explicit structured filters

Defer broad substring search on the large tables until there is a clear product
need. If substring search is required later, add selective trigram indexes only
for the fields the UI really exposes.

Use keyset pagination on the largest list pages, especially repeat calls, rather
than deep offset pagination.

Recommended stable sort for repeat calls:

- `(pipeline_run_id, accession, protein_name, start, call_id)`

Recommended stable sort for proteins:

- `(pipeline_run_id, accession, protein_name, protein_id)`

### Taxonomy policy

Do not compact taxonomy before storage.

Store the taxonomy the pipeline emitted, then derive closure rows for lineage
queries. If the UI later wants a compact display lineage, that should be a
presentation concern, not a destructive import policy.

## Browser Model

### Raw-first browsing

The default browser should emphasize raw imported truth:

- runs
- batches
- genomes
- repeat calls
- proteins
- sequences
- warnings
- accession statuses
- accession call counts

The UI should make it clear when a page shows:

- canonical raw records
- a focused browse filter over canonical raw tables
- a derived merged view

### Required raw browsing behavior

Run detail should show:

- run metadata from the manifest
- available batches and batch-scoped imported counts
- counts for genomes, repeat calls, warnings, status rows, and linked browse
  projections
- enabled methods and residues
- current or latest import status when relevant

Batch-scoped provenance should remain visible from run detail and the
operational artifact browsers:

- batch artifact inventory and imported counts
- links into warning, status, call-count, and download-manifest views filtered
  by run and batch
- active import phase, heartbeat, and progress summaries when relevant

Genome and repeat-call detail should show:

- raw provenance
- batch provenance
- links back to run and batch
- traceability to underlying accession and taxon

Sequence and protein pages should clearly indicate that they cover the
call-linked subset stored for browsing and provenance, not the full raw
sequence or protein inventories emitted by the pipeline.

Largest raw list pages should use narrow projections and cursor-based browsing
mechanics so realistic imports remain usable without loading large sequence
payloads by default.

### Derived merged browsing

Merged browsing remains allowed and useful, but it must remain derived-only.

Keep the accession-centered merged layer and make its grouping rules explicit.

Current grouping rule to preserve:

- genome merge key: `accession`
- protein-level merged key: `(accession, protein_id, method)`
- residue-level merged key: `(accession, protein_id, method, residue)`

Required derived-view behavior:

- never collapse raw rows at import time
- exclude rows lacking a trustworthy merged identity from merged statistics
  while keeping them visible in raw mode
- always show how many raw records and runs contributed
- show methods observed, coordinate drift, and representative evidence rows
  explicitly as evidence rather than canonical truth
- link back to raw source proteins and raw source calls
- expose analyzed-protein denominator conflicts instead of hiding them

## Validation Strategy

### Small example run

Use `live_raw_effective_params_2026_04_09` to validate:

- manifest resolution
- one-batch raw acquisition import
- removed-column handling
- corrected method and parameter handling
- raw side-artifact import

### Large final-style run

Use `chr_all3_raw_2026_04_09` to validate:

- multi-batch discovery
- `seed_extend` support
- large raw run counts
- call-linked sequence and protein import under realistic scale
- run-level call import against a much larger `repeat_calls.tsv`
- progress and heartbeat updates during a long-running import
- safe replacement behavior

### Import UX acceptance

The import flow is acceptable only if:

- a staff user can trigger an import without holding open a long request
- the UI can show the current phase and recent progress
- a failed import leaves an actionable error state
- a long import still appears alive via heartbeat or changing counters

## Future `merged` Support

This design intentionally leaves room for future `merged` publish-mode support.

When that work happens later:

- the importer can add a second acquisition resolver for flat merged outputs
- the canonical raw-side models can remain intact
- the run-level call and parameter handling should already be compatible

The immediate refactor should not spend time trying to fully support `merged`.
