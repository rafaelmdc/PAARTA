# Phase 3 Module Map

## Purpose

This document proposes the minimal file ownership layout for Phase 3.

The goal is not to overdesign the repository.
The goal is to stop implementation from scattering responsibilities across random files once coding starts.

---

## Guiding layout rules

- `bin/` owns CLI entry points only.
- `lib/` owns reusable logic.
- `tests/fixtures/` owns synthetic and smoke-test inputs.
- `assets/sql/` owns schema and indexes.
- no biological rules belong in Nextflow files during Phase 3.

---

## Planned CLI entry points

### Acquisition and planning

- `bin/resolve_taxa.py`
  Resolve user requests with `taxon-weaver` and write `resolved_requests.tsv` plus `taxonomy_review_queue.tsv`.

- `bin/enumerate_assemblies.py`
  Query NCBI metadata and write `assembly_inventory.tsv`.

- `bin/select_assemblies.py`
  Apply RefSeq selection policy and write `selected_assemblies.tsv`, `selected_accessions.txt`, and `excluded_assemblies.tsv`.

- `bin/plan_batches.py`
  Derive `selected_batches.tsv` from the frozen selection manifest.

- `bin/download_ncbi_packages.py`
  Download and optionally rehydrate annotation-focused packages for one batch.

- `bin/normalize_cds.py`
  Parse package metadata, GFF, and CDS FASTA into canonical `genomes.tsv`, `sequences.tsv`, and normalized CDS FASTA.

- `bin/translate_cds.py`
  Translate retained CDS rows into canonical protein FASTA and `proteins.tsv`.

### Detection

- `bin/detect_pure.py`
  Emit `pure_calls.tsv`.

- `bin/detect_threshold.py`
  Emit `threshold_calls.tsv`.

- `bin/extract_repeat_codons.py`
  Join calls back to CDS rows and populate codon fields conservatively.

### Assembly and reporting

- `bin/build_sqlite.py`
  Build the final SQLite artifact from validated flat files.

- `bin/export_summary_tables.py`
  Emit `summary_by_taxon.tsv` and `regression_input.tsv`.

- `bin/prepare_report_tables.py`
  Emit any extra report-prep tables or combined ECharts options payloads needed by later phases.

---

## Planned library modules

### Low-level shared helpers

- `lib/tsv_io.py`
  TSV reading, writing, and header validation.

- `lib/ids.py`
  Deterministic internal ID generation.

- `lib/warnings.py`
  Structured warning-row helpers.

- `lib/run_params.py`
  Shared helpers for `run_params.tsv`.

### Acquisition and normalization

- `lib/taxonomy.py`
  Thin wrapper around `taxon-weaver` integration and resolution status shaping.

- `lib/ncbi_datasets.py`
  Command helpers and response shaping for NCBI Datasets CLI usage.

- `lib/gff_norm.py`
  GFF parsing and CDS/transcript/gene relationship extraction.

- `lib/translation.py`
  Conservative CDS translation and rejection logic.

- `lib/batching.py`
  Execution-batch derivation from a frozen selection manifest.

### Detection

- `lib/detect_pure.py`
  Pure-method tract finding logic.

- `lib/detect_threshold.py`
  Threshold-method window/merge/extend logic.

  Similarity-method coordination across fallback and production backends.

- `lib/repeat_features.py`
  Shared feature calculations such as purity and coordinate shaping.

### Post-detection

- `lib/codon_extract.py`
  Codon slicing from finalized amino-acid call coordinates.

- `lib/sqlite_build.py`
  Import order, transaction control, and post-import checks.

- `lib/summaries.py`
  Summary aggregation logic.

- `lib/report_prep.py`
  Derived reporting-table logic and optional ECharts payload shaping.

---

## Planned fixture layout

- `tests/fixtures/requests/`
  Input request tables for taxonomy and assembly-planning tests.

- `tests/fixtures/synthetic/`
  Small string-level and record-level fixtures for detection and translation.

- `tests/fixtures/packages/`
  Tiny normalized package snapshots or reduced package fragments for acquisition tests.

- `tests/fixtures/smoke/`
  Small end-to-end manifests and expected outputs.

---

## Ownership boundaries

Acquisition CLIs own:
- request resolution
- assembly planning
- download and normalization

Detection CLIs own:
- amino-acid tract calling only

Codon enrichment owns:
- codon attachment to finalized calls

SQLite owns:
- import only

Reporting owns:
- summary and report-prep tables only

These boundaries matter because they stop Phase 3 from becoming an unreviewable mixed implementation.

---

## Likely structural problems

- too many tiny modules create indirection without helping review
- too few modules create giant scripts that mix IO, biology, and formatting
- backend-specific logic leaks into shared detection helpers
- report generation starts owning scientific grouping logic

Planned mitigation:
- start with this file map, but merge helpers only when they are truly inseparable
- keep CLI files thin and library files operationally focused
- keep backend adapters separate from shared call shaping
- keep reporting helpers downstream of finalized tables
