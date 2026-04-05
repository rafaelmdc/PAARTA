# Phase 3 Acquisition Implementation

## Purpose

This document makes the Phase 3 acquisition work explicit.

It covers the part of Phase 3 that:
- resolves requests
- selects RefSeq assemblies
- derives execution batches
- downloads NCBI package contents
- rehydrates large downloads
- normalizes CDS and metadata
- translates CDS into canonical protein inputs

This is the front half of Phase 3.
Detection, SQLite assembly, and reporting depend on it.

---

## Core rule

Phase 3 does include downloading data.

The production path is:
1. resolve taxa
2. enumerate RefSeq assemblies
3. freeze `selected_assemblies.tsv`
4. derive `selected_batches.tsv`
5. download one batch at a time
6. rehydrate if needed
7. normalize CDS plus GFF plus reports
8. translate retained CDS
9. validate and merge batch outputs

The implementation should not:
- query NCBI repeatedly during retries when the frozen manifest already exists
- write directly into SQLite during downloads or normalization
- download raw genomic FASTA in v1

---

## Phase 3 acquisition slices

### A1: request resolution

Inputs:
- `requested_taxa.tsv`

Outputs:
- `resolved_requests.tsv`
- `taxonomy_review_queue.tsv`

Responsibilities:
- use `taxon-weaver` for deterministic name resolution
- pass deterministic rows forward
- isolate review-required rows without blocking deterministic rows

Likely problems:
- ambiguous common names
- stale local taxonomy DB

Mitigation:
- record taxonomy build metadata
- write review-required rows explicitly

---

### A2: assembly enumeration and selection

Inputs:
- `resolved_requests.tsv`

Outputs:
- `assembly_inventory.tsv`
- `selected_assemblies.tsv`
- `selected_accessions.txt`
- `excluded_assemblies.tsv`

Responsibilities:
- enumerate RefSeq assemblies from NCBI metadata
- prefer RefSeq reference assemblies
- allow RefSeq representative assemblies when no suitable reference exists
- exclude assemblies lacking the annotation needed for v1 automatic processing

Likely problems:
- large taxa return many candidate assemblies
- selection logic becomes opaque

Mitigation:
- record `selection_reason` explicitly
- keep raw metadata projection artifacts

---

### A3: batch planning

Inputs:
- `selected_assemblies.tsv`

Outputs:
- `selected_batches.tsv`

Responsibilities:
- create bounded execution batches from the frozen assembly manifest
- keep every selected assembly in exactly one batch
- use operational batch sizing rather than insisting on one taxon per batch

Default starting policy:
- small selections may remain one batch
- larger runs should start at roughly `50-200` assemblies per batch
- batch concurrency should remain conservative

Likely problems:
- one taxon dominates the run and creates a giant batch
- retries are impossible without reconstructing membership

Mitigation:
- materialize `selected_batches.tsv`
- retry by batch ID, not by recomputing selection

---

### A4: package download and rehydration

Inputs:
- `selected_batches.tsv`

Per-batch outputs:
- raw package zip or dehydrated package directory
- rehydrated package directory when needed
- download logs
- checksums or manifest traces in `download_manifest.tsv`

Requested NCBI package contents:
- `cds`
- `gff3`
- `seq-report`

Responsibilities:
- download one batch at a time
- use dehydrated downloads for large runs
- rehydrate explicitly before normalization
- record batch-level provenance

Likely problems:
- interrupted downloads
- partially rehydrated package directories
- too many concurrent workers stressing the service

Mitigation:
- detect incomplete rehydration before normalization starts
- keep batch-local raw directories
- cap batch concurrency separately from rehydration worker count

---

### A5: normalization and translation

Inputs:
- one normalized package directory for one batch

Per-batch outputs:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- normalized CDS FASTA
- normalized translated protein FASTA
- `normalization_warnings.tsv`
- `acquisition_validation.json`

Responsibilities:
- parse package metadata
- parse GFF-backed relationships
- retain one isoform per gene
- translate retained CDS conservatively
- exclude invalid CDS translations with warning codes

Likely problems:
- inconsistent GFF conventions
- CDS records without clean linkage
- translation failures due to partial or invalid CDS

Mitigation:
- treat GFF as the primary authority
- preserve degraded states explicitly
- exclude translation failures instead of substituting external protein sequences silently

---

### A6: batch merge

Inputs:
- validated per-batch canonical outputs

Merged outputs:
- global `genomes.tsv`
- global `taxonomy.tsv`
- global `sequences.tsv`
- global `proteins.tsv`
- merged warning and provenance artifacts

Responsibilities:
- merge batches deterministically
- deduplicate taxonomy rows safely
- preserve batch provenance in supporting artifacts

Likely problems:
- row-order-dependent merge behavior
- duplicate taxa or genomes merge incorrectly

Mitigation:
- merge on stable IDs and contract keys, not file order
- validate merged row counts against the sum of successful batches

---

## Planned CLI ownership

Suggested acquisition CLIs:
- `bin/resolve_taxa.py`
- `bin/enumerate_assemblies.py`
- `bin/select_assemblies.py`
- `bin/plan_batches.py`
- `bin/download_ncbi_packages.py`
- `bin/normalize_cds.py`
- `bin/translate_cds.py`
- `bin/merge_acquisition_batches.py`

The merge CLI is worth keeping separate because merging validated batches is operationally different from parsing one package.

---

## Phase 3 acquisition acceptance gate

The acquisition side of Phase 3 is not complete until:
- deterministic requests resolve reproducibly
- `selected_assemblies.tsv` and `selected_batches.tsv` are reproducible from the same input
- one clean RefSeq batch can be downloaded and normalized end to end
- one invalid CDS example is rejected with the expected warning code
- merged canonical outputs are deterministic across repeated runs on the same input

If those are not true, Phase 3 is not actually ready for detection implementation.
