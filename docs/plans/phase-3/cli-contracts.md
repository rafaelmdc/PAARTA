# Phase 3 CLI Contracts

## Purpose

This document defines the operational contract for each planned Phase 3 CLI.

The point is to remove guesswork about:
- required inputs
- expected outputs
- side effects
- exit behavior
- warning behavior

These are implementation contracts, not just suggestions.

---

## Shared CLI rules

Every Phase 3 CLI should follow these rules:

### 1. Directly runnable

Each script under `bin/` must be runnable directly from the command line without Nextflow.

### 2. Explicit file arguments

No CLI should depend on implicit current-directory file discovery for primary inputs.

Preferred argument pattern:
- explicit input file arguments
- explicit `--outdir`
- explicit `--tmpdir` only when needed

### 3. No hidden write targets

All CLI outputs must be written either:
- under the provided `--outdir`
- or to a documented external cache path when the command is explicitly cache-aware

### 4. Structured warnings

Non-fatal scientific or data-quality issues must be written to a warning artifact, not only to stderr.

### 5. Exit code policy

Recommended exit codes:
- `0` success
- `1` runtime or environment failure
- `2` invalid CLI usage
- `3` contract validation failure on inputs or outputs

### 6. Deterministic outputs

Given the same inputs, configuration, and reference metadata snapshot, a CLI should emit the same outputs.

### 7. Parameter capture

Whenever a CLI implements method behavior or selection policy, the relevant settings must be serializable into `run_params.tsv` or another documented parameter artifact.

---

## Shared argument conventions

Recommended common arguments:
- `--outdir`
- `--tmpdir`
- `--log-file`
- `--run-params-out`
- `--force`

Recommended acquisition-specific arguments:
- `--batch-id`
- `--batch-manifest`
- `--cache-dir`

Recommended detection-specific arguments:
- `--proteins-tsv`
- `--protein-fasta`
- `--calls-out`

Recommended merge-specific arguments:
- `--inputs`
- `--output`

---

## Acquisition and planning CLIs

### `bin/resolve_taxa.py`

Purpose:
- resolve request rows with `taxon-weaver`

Required inputs:
- `requested_taxa.tsv`
- local taxonomy DB path

Required outputs:
- `resolved_requests.tsv`
- `taxonomy_review_queue.tsv`

Must not:
- auto-accept fuzzy matches
- silently discard unresolved rows

Hard-fail conditions:
- unreadable input manifest
- missing taxonomy DB
- malformed required columns

### `bin/enumerate_assemblies.py`

Purpose:
- query NCBI metadata for deterministic requests

Required inputs:
- `resolved_requests.tsv`

Required outputs:
- `assembly_inventory.tsv`
- optionally raw metadata projection such as `assembly_inventory.jsonl`

Must not:
- perform selection policy
- mutate the request-resolution outputs

Hard-fail conditions:
- required taxid missing on deterministic rows
- malformed NCBI response projection that prevents inventory writing

### `bin/select_assemblies.py`

Purpose:
- apply RefSeq selection policy to the frozen assembly inventory

Required inputs:
- `assembly_inventory.tsv`

Required outputs:
- `selected_assemblies.tsv`
- `selected_accessions.txt`
- `excluded_assemblies.tsv`

Must encode:
- `selection_reason`
- reference-vs-representative choice
- annotation exclusion reasons

Must not:
- re-query NCBI
- derive execution batches

### `bin/plan_batches.py`

Purpose:
- derive operational execution batches from selected assemblies

Required inputs:
- `selected_assemblies.tsv`

Required outputs:
- `selected_batches.tsv`

Must guarantee:
- every selected assembly appears in exactly one batch
- batch derivation is deterministic

Must not:
- change assembly selection itself

### `bin/download_ncbi_packages.py`

Purpose:
- download one batch of annotation-focused packages

Required inputs:
- `selected_batches.tsv`
- batch identifier

Required outputs:
- batch-local raw package directory or zip
- batch-local download logs
- batch-local `download_manifest.tsv` fragment or append-safe equivalent

Required requested content:
- `cds`
- `gff3`
- `seq-report`

Must not:
- download raw genomic FASTA in v1
- normalize package contents directly

Hard-fail conditions:
- missing batch ID
- batch has zero matching rows
- package download fails completely for a selected accession without a documented failure record

### `bin/normalize_cds.py`

Purpose:
- normalize package metadata, GFF, and CDS rows into canonical acquisition outputs

Required inputs:
- batch-local package directory
- taxonomy DB path for `taxon-weaver` lineage enrichment

Required outputs:
- batch-local `genomes.tsv`
- batch-local `taxonomy.tsv`
- batch-local `sequences.tsv`
- normalized CDS FASTA
- `normalization_warnings.tsv`

Must encode:
- deterministic IDs
- linkage warning rows
- taxonomy rows derived from `taxon-weaver` lineage inspection

Must not:
- translate CDS
- emit final protein rows

### `bin/translate_cds.py`

Purpose:
- translate retained CDS rows conservatively into canonical protein inputs

Required inputs:
- batch-local `sequences.tsv`
- normalized CDS FASTA
- any translation-table metadata needed from normalization outputs

Required outputs:
- batch-local `proteins.tsv`
- normalized translated protein FASTA
- `normalization_warnings.tsv` updates or a separate translation-warning artifact

Must enforce:
- conservative translation acceptance rules from Phase 2

Must not:
- repair invalid CDS by guessing
- silently substitute external protein FASTA

### `bin/merge_acquisition_batches.py`

Purpose:
- merge validated batch-local acquisition outputs into global canonical outputs

Required inputs:
- list of successful batch output directories

Required outputs:
- merged `genomes.tsv`
- merged `taxonomy.tsv`
- merged `sequences.tsv`
- merged `proteins.tsv`
- merged warning/provenance artifacts

Must guarantee:
- deterministic merge order
- taxonomy deduplication by stable taxon key
- row-count reconciliation against successful batches

Must not:
- merge failed batches silently
- change stable IDs during merge

---

## Detection CLIs

### `bin/detect_pure.py`

Required inputs:
- merged `proteins.tsv`
- merged translated protein FASTA

Required outputs:
- `pure_calls.tsv`
- method-specific `run_params.tsv` fragment or append-safe equivalent

Must enforce:
- `min_repeat_count = 6` by default
- single-residue interruption rule
- trimming of termini

### `bin/detect_threshold.py`

Required inputs:
- merged `proteins.tsv`
- merged translated protein FASTA

Required outputs:
- `threshold_calls.tsv`
- method-specific `run_params.tsv`

Must enforce:
- default `window_size = 8`
- default `min_target_count = 6`
- merge-plus-extend logic with purity threshold `0.70`

### `bin/detect_blast.py`

Required inputs:
- merged `proteins.tsv`
- merged translated protein FASTA
- explicit backend selection

Required outputs:
- `blast_calls.tsv`
- method-specific `run_params.tsv`

Must record:
- backend identity
- template configuration
- score semantics

Must not:
- treat fallback scores as backend-native bit scores

### `bin/extract_repeat_codons.py`

Required inputs:
- call tables
- merged `sequences.tsv`
- normalized CDS FASTA

Required outputs:
- enriched call tables with codon fields
- codon warning artifact if separate from existing warnings

Must enforce:
- amino-acid coordinates are the only slicing coordinates
- failed codon extraction preserves the amino-acid call and empties codon fields
- no residue-specific metric is emitted in v1

---

## Assembly and reporting CLIs

### `bin/build_sqlite.py`

Required inputs:
- validated canonical TSVs
- validated call tables
- schema SQL
- index SQL

Required outputs:
- `homorepeat.sqlite`
- import validation report

Must enforce:
- transaction-based import
- hard-fail on structural import errors
- post-import row-count and relational checks

### `bin/export_summary_tables.py`

Required inputs:
- finalized call tables or final SQLite artifact

Required outputs:
- `summary_by_taxon.tsv`
- `regression_input.tsv`

Must enforce:
- taxon-direct grouping in v1
- residue-neutral metric behavior

### `bin/prepare_report_tables.py`

Required inputs:
- finalized summaries and any required report-prep tables

Required outputs:
- derived reporting tables
- optionally combined `echarts_options.json`

Must not:
- derive new biological rules
- query raw detection logic directly

---

## Implementation checklist use

Before writing a new CLI:
- confirm its inputs and outputs here
- confirm the owning slice in `implementation-sequence.md`
- confirm the file path in `module-map.md`
- confirm the relevant scientific defaults in Phase 2 docs

If any of those are unclear, the docs need to be updated before coding starts.
