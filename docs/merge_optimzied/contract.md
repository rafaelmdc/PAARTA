# Merged Serving Contract

## Purpose

This document locks the serving contract for merged optimization so later
implementation slices do not need to invent storage or rebuild semantics.

This contract preserves the merged semantics in
[docs/django/merged.md](/home/rafael/Documents/GitHub/homorepeat/docs/django/merged.md)
while moving merged browse paths off Python-side full evidence materialization.

## Identity Rules

These rules are fixed:

- protein summary identity: `(accession, protein_id, method)`
- residue summary identity: `(accession, protein_id, method, repeat_residue)`
- method remains part of identity
- residue is part of identity only for residue-level summaries
- rows missing a trustworthy accession or protein ID are excluded from merged
  biological statistics
- rows missing a trustworthy residue are excluded from residue-level merged
  summaries

Raw tables remain canonical. The serving layer is rebuildable and derived only.

## Storage Layout

### Summary rows

`MergedProteinSummary`

- one row per `(accession, protein_id, method)`
- stores stable display fields and precomputed counters used by merged list and
  detail pages
- stores deterministic representative backlinks

Stored fields:

- identity: `accession`, `protein_id`, `method`
- display: `protein_name`, `protein_length`
- labels: `gene_symbol_label`, `methods_label`, `repeat_residues_label`,
  `coordinate_label`, `protein_length_label`
- representative backlinks:
  - `representative_protein`
  - `representative_repeat_call`
- counters:
  - `source_runs_count`
  - `source_taxa_count`
  - `source_proteins_count`
  - `source_repeat_calls_count`
  - `residue_groups_count`
  - `collapsed_repeat_calls_count`

`MergedResidueSummary`

- one row per `(accession, protein_id, method, repeat_residue)`
- stores residue-level display fields and counters used by merged residue pages

Stored fields:

- identity: `accession`, `protein_id`, `method`, `repeat_residue`
- display: `protein_name`, `protein_length`, `start`, `end`, `length`,
  `normalized_purity`
- labels: `gene_symbol_label`, `methods_label`, `coordinate_label`,
  `protein_length_label`, `length_label`, `purity_label`
- representative backlinks:
  - `representative_protein`
  - `representative_repeat_call`
- counters:
  - `source_runs_count`
  - `source_taxa_count`
  - `source_proteins_count`
  - `source_count`

### Occurrence rows

`MergedProteinOccurrence`

- one row per `(summary, pipeline_run, taxon)`
- supports run and branch filtering without re-grouping raw evidence

Stored fields:

- `summary`
- `pipeline_run`
- `taxon`
- representative backlinks for the scoped occurrence
- scoped counters:
  - `source_proteins_count`
  - `source_repeat_calls_count`
  - `residue_groups_count`
  - `collapsed_repeat_calls_count`

`MergedResidueOccurrence`

- one row per `(summary, pipeline_run, taxon)`
- supports run and branch filtering for residue summaries

Stored fields:

- `summary`
- `pipeline_run`
- `taxon`
- representative backlinks for the scoped occurrence
- scoped counters:
  - `source_proteins_count`
  - `source_count`

## Rebuild Rules

### Import-time build

Merged serving rows are built after raw import succeeds and before the
`ImportBatch` is marked completed.

The import state model should gain a dedicated merged summary phase:

- `SUMMARIZING_MERGED = "summarizing_merged"`

Expected order:

1. parse contract
2. prepare raw import
3. import raw rows
4. persist `PipelineRun.browser_metadata`
5. rebuild merged serving rows for the imported run
6. mark the batch completed

### Replace-existing behavior

When `--replace-existing` is used:

1. delete the existing run-scoped raw rows
2. import the replacement raw rows
3. delete any existing merged occurrence rows for that run
4. rebuild the run-scoped occurrence rows from the newly imported raw data
5. recalculate affected summary rows from the current full set of occurrence
   rows and raw evidence
6. delete summary rows that no longer have any occurrences

The merged layer must never preserve stale run-scoped occurrences after a
replace-existing import.

### Backfill contract

Add a management command:

- `backfill_merged_summaries`

Command behavior:

- `--run-id <run_id>` rebuilds one run only
- `--force` rebuilds even if occurrence rows already exist
- default behavior skips already-populated runs
- rebuilding one run refreshes the affected summary rows as well

## Read-Path Contract

### Summary-backed reads

The following reads move onto the serving layer:

- merged proteins list
- merged repeat-call list
- accession analytics
- accession detail top-level merged counters
- taxon-detail merged counters

### Filter routing

Use summary rows for:

- accession filters
- protein ID filters
- method filters
- residue filters
- text search fields already represented on the summaries

Use occurrence rows for:

- `run=<run_id>`
- branch or taxon scope filters

Use raw `RepeatCall` evidence with `Exists(...)` only where exact evidence
matching is still required:

- `length_min`
- `length_max`
- `purity_min`
- `purity_max`
- other filters whose semantics depend on at least one matching contributing
  raw row rather than only on precomputed summary labels

### Provenance contract

The serving layer must preserve drill-down to raw evidence, but list pages do
not need to inline the full provenance set.

Default page behavior:

- list pages show counts and representative evidence links
- detail pages or filtered evidence pages provide the full backlink set

## Representative Evidence Policy

Representative evidence remains deterministic and compatible with the current
merged helper policy.

Selection priority:

1. row has a protein name
2. row has a gene symbol
3. row has a positive protein length
4. row has an amino-acid sequence
5. row has a method
6. row has a trustworthy residue when relevant
7. larger protein length
8. larger repeat length
9. higher purity
10. newer imported run
11. lexical run id
12. lexical call id

If later code changes the ranking implementation, it must preserve the same
deterministic ordering contract.
