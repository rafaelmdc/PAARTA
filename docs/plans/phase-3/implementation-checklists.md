# Phase 3 Implementation Checklists

## Purpose

This document provides explicit review checklists for each Phase 3 slice.

Use these checklists before declaring a slice done.
They are meant to prevent “mostly works” milestones from slipping through.

---

## Slice 0 checklist: shared foundations

- deterministic ID helpers exist and are covered by small tests
- TSV helpers preserve headers and field order
- warning-row helpers exist
- parameter-record helpers exist
- contract validation helpers exist for required-column checks
- no helper layer has grown into a generic framework with unclear ownership

---

## Slice 1 checklist: request resolution and assembly planning

- deterministic requests resolve cleanly
- review-required requests are written to `taxonomy_review_queue.tsv`
- `assembly_inventory.tsv` is reproducible from the same fixture
- `selected_assemblies.tsv` records explicit `selection_reason`
- `selected_batches.tsv` covers every selected assembly exactly once
- retries can target a batch without recomputing selection

---

## Slice 2 checklist: download, normalization, and translation

- annotation-focused download requests use `cds,gff3,seq-report`
- raw genomic FASTA is not requested
- dehydrated package handling is explicit
- rehydration completeness is checked before normalization
- GFF is used as primary linkage authority
- one isoform per gene is retained deterministically
- CDS translation rejection writes explicit warning codes
- translated proteins are derived from retained CDS records, not silently substituted
- merged acquisition outputs are deterministic across repeated runs

---

## Slice 3 checklist: pure detection

- default `min_repeat_count = 6` is implemented explicitly
- single-residue interruption rule matches Phase 2
- termini are trimmed correctly
- coordinates are 1-based and inclusive
- `pure_calls.tsv` satisfies the shared call schema
- worked example output matches the documented example

---

## Slice 4 checklist: threshold detection

- default `window_size = 8` is explicit
- default `min_target_count = 6` is explicit
- window merge logic is implemented separately from pure logic
- extension purity threshold `0.70` is explicit
- worked example output matches the documented example
- `threshold_calls.tsv` is schema-compatible with `pure_calls.tsv`

---

## Slice 5 checklist: similarity-based detection

- backend selection is explicit
- backend identity is written to `run_params.tsv`
- deterministic fallback exists as `template_local`
- fallback score semantics are not mislabeled as bit scores
- `blastp` and `diamond blastp` adapters are isolated from fallback logic
- worked example output matches the documented fallback example

---

## Slice 6 checklist: codon extraction

- codon slicing uses amino-acid call coordinates only
- successful codon rows satisfy length `3 * tract_length`
- failed codon extraction preserves the amino-acid call
- failed codon extraction leaves codon fields empty
- residue-specific metric fields remain empty in v1

---

## Slice 7 checklist: SQLite assembly

- import order matches the Phase 2 decision register
- imports run inside transactions
- structural import failures hard-fail
- row counts reconcile with flat inputs
- foreign-key reachability checks pass
- the database is built only from validated flat outputs

---

## Slice 8 checklist: summary and report-prep

- `summary_by_taxon.tsv` groups directly by taxon in v1
- `regression_input.tsv` uses `group_label` consistently
- summary counts reconcile with call tables
- regression rows reconcile with summaries
- any `echarts_options.json` is derived only from finalized tables
- no renderer-specific biology is introduced

---

## Final Phase 3 readiness checklist

- all required CLIs have explicit ownership
- acquisition can run from request resolution through merged canonical outputs
- all three detection methods are runnable outside Nextflow
- codon enrichment is conservative and non-destructive
- SQLite assembly works from flat files only
- summary/report-prep outputs are reproducible
- no Phase 2 scientific rule had to be improvised in code
