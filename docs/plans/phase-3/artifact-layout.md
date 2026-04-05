# Phase 3 Artifact Layout

## Purpose

This document defines the default on-disk layout for standalone Phase 3 runs.

The goal is to avoid:
- ad hoc output placement
- hidden files outside the run tree
- merge confusion across batches

---

## Core layout rules

- each standalone run has one explicit `run_id`
- all non-cache outputs live under one run root
- batch-local outputs live under batch-specific directories
- merged outputs live under a dedicated merged directory
- SQLite and reporting outputs are never written into batch-local directories

External caches are allowed for:
- taxonomy DBs
- downloaded NCBI package caches

Those caches must still be referenced by run provenance.

---

## Default run tree

Recommended layout:

```text
runs/
  <run_id>/
    planning/
      requested_taxa.tsv
      resolved_requests.tsv
      taxonomy_review_queue.tsv
      assembly_inventory.tsv
      selected_assemblies.tsv
      selected_accessions.txt
      selected_batches.tsv
      excluded_assemblies.tsv
    batches/
      <batch_id>/
        raw/
        normalized/
        validation/
        logs/
    merged/
      acquisition/
      calls/
      sqlite/
      reports/
    logs/
```

---

## Directory meanings

### `planning/`

Contains:
- request resolution artifacts
- assembly inventory artifacts
- frozen selection artifacts
- batch plan artifacts

Rules:
- files here are planning inputs for later slices
- these files should be immutable once execution starts

### `batches/<batch_id>/raw/`

Contains:
- raw downloaded package zip or directory
- rehydrated package directory
- raw download logs

Rules:
- raw package contents stay batch-local
- normalization should read from here and write elsewhere

### `batches/<batch_id>/normalized/`

Contains:
- batch-local canonical TSVs
- normalized CDS FASTA
- translated protein FASTA
- warning artifacts

Preferred names inside each batch:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- `cds.fna`
- `proteins.faa`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

### `batches/<batch_id>/validation/`

Contains:
- batch-local validation summaries
- reconciliation artifacts

### `batches/<batch_id>/logs/`

Contains:
- CLI logs for that batch only

### `merged/acquisition/`

Contains:
- merged canonical acquisition outputs across successful batches

Preferred names:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- `cds.fna`
- `proteins.faa`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

### `merged/calls/`

Contains:
- merged method outputs and parameter records

Preferred names:
- `pure_calls.tsv`
- `threshold_calls.tsv`
- `run_params.tsv`

### `merged/sqlite/`

Contains:
- `homorepeat.sqlite`
- SQLite validation artifacts

### `merged/reports/`

Contains:
- `summary_by_taxon.tsv`
- `regression_input.tsv`
- derived report-prep tables
- `echarts_options.json`
- any later report shell artifacts

---

## Merge rules by artifact

### Concatenate with validation

Use for:
- `genomes.tsv`
- `sequences.tsv`
- `proteins.tsv`
- call tables
- `run_params.tsv`
- warning tables
- download manifests

Requirements:
- same header
- deterministic batch-order concatenation
- duplicate-key checks before final write

### Deduplicate by stable key

Use for:
- `taxonomy.tsv`

Stable dedupe key:
- `taxon_id`

Conflict rule:
- if two taxonomy rows with the same `taxon_id` disagree materially, hard-fail the merge and write a conflict report

### JSON merge

Use for:
- validation summaries
- report-option payloads

Requirement:
- merged JSON must keep stable top-level keys and preserve batch provenance when relevant

---

## Naming rules

- canonical merged filenames should match `docs/contracts.md`
- batch-local files may reuse canonical filenames because the batch directory already scopes them
- avoid encoding critical biology only in filenames
- batch IDs should be operational IDs, not semantic labels that try to encode taxonomy hierarchy

Recommended batch IDs:
- `batch_0001`
- `batch_0002`

Recommended run IDs:
- timestamped or user-provided, but stable for the life of the run

---

## Side-effect rules

- no script should write merged outputs directly from batch-local execution unless it is a merge CLI
- no script should write SQLite during acquisition or detection
- no script should modify files in `planning/` after batch execution begins

---

## Artifact checklist before coding

Before implementing a CLI, confirm:
- which directory it reads from
- which directory it writes to
- whether it is batch-local or merged
- whether its outputs are canonical, supporting, or validation-only

If that is not obvious, the implementation is still under-specified.
