# Acquisition

## Purpose

This document describes the current implemented acquisition behavior for the standalone Phase 3 pipeline.

Use it for:
- how data is actually retrieved today
- how taxonomy is resolved and enriched
- what is retained versus ignored by default
- what the live smoke check has already validated

This document is intentionally implementation-facing.
For the earlier design rationale, see:
- [methods.md](./methods.md)
- [plans/phase-3/acquisition-implementation.md](./plans/phase-3/acquisition-implementation.md)

---

## Current status

The acquisition side of Phase 3 is implemented through:
- request resolution
- assembly enumeration and selection
- batch planning
- NCBI package download
- CDS normalization
- local CDS translation
- batch merge and validation

As of `2026-04-05`, the live Docker-backed smoke check has passed against:
- taxon: `Homo sapiens`
- accession: `GCF_000001405.40`

The latest checked live smoke ended with:
- acquisition validation status `warn`
- all structural validation checks `true`
- `unresolved_linkage = 0`
- `partial_cds = 405` out of `131840` normalized CDS rows (`0.3072%`)

The remaining warnings are now dominated by conservative translation exclusions, not by broken linkage.

---

## Implemented acquisition flow

### 1. Resolve user requests

`bin/resolve_taxa.py` accepts request rows and normalizes them into:
- `resolved_requests.tsv`
- `taxonomy_review_queue.tsv`

Current behavior:
- scientific names are resolved with `taxon-weaver`
- deterministic matches go forward automatically
- ambiguous or fuzzy results go to the review queue
- direct assembly-accession requests also pass through the same planning contract

### 2. Enumerate candidate assemblies

`bin/enumerate_assemblies.py` queries NCBI metadata and writes `assembly_inventory.tsv`.

Current behavior:
- NCBI `datasets` is the metadata source of truth
- assembly enumeration happens before any sequence package download
- the inventory is preserved as a flat artifact instead of querying NCBI again during later steps

### 3. Select assemblies

`bin/select_assemblies.py` applies the current RefSeq-only selection policy.

Rows are selected only when all of the following are true:
- `source_database == REFSEQ`
- `assembly_status == current`
- `assembly_accession == current_accession`
- annotation is present when `--require-annotation` is enabled, which is the default

Selection order:
- `reference genome`
- `representative genome` when representatives are allowed, which is the default
- otherwise annotated uncategorized RefSeq rows are still accepted

Additional behavior:
- the same accession is selected only once even if multiple requests resolve to it
- duplicate selections are pushed into `excluded_assemblies.tsv` with an explicit reason

### 4. Plan bounded batches

`bin/plan_batches.py` turns the frozen selection manifest into `selected_batches.tsv`.

Current behavior:
- each selected accession belongs to exactly one batch
- retries happen by `batch_id`
- the pipeline does not treat one giant global run as the default operating mode

### 5. Download NCBI package contents

`bin/download_ncbi_packages.py` downloads one batch at a time.

Current behavior:
- the package is assembly-centered, but v1 requests only annotation-focused contents
- raw genomic FASTA is not part of the canonical acquisition path
- the raw archive and extracted package directory are preserved on disk
- dehydrated download plus explicit `rehydrate` is supported for larger runs

Current package contents:
- `cds`
- `gff3`
- `seq-report`

### 6. Normalize CDS and metadata

`bin/normalize_cds.py` turns one extracted package into canonical acquisition outputs.

Current behavior:
- `assembly_data_report.jsonl` provides genome-level metadata
- `taxon-weaver inspect-lineage` builds `taxonomy.tsv`
- `sequence_report.jsonl` is used to limit normalization to allowed molecules
- `genomic.gff` is the primary linkage authority
- normalized CDS records are written to `cds.fna`

Current linkage order:
1. GFF transcript-like aliases
2. GFF protein aliases
3. GFF CDS ID aliases
4. GFF gene-segment alias `cds-<gene_symbol>` when the CDS header has no transcript or protein ID and carries `exception=rearrangement required for product`
5. CDS FASTA header fallback, with a warning

This fourth rule is what resolves the immunoglobulin and T-cell receptor segment cases that were previously left as unresolved linkage.

### 7. Translate retained CDS locally

`bin/translate_cds.py` translates normalized CDS into canonical proteins.

Current behavior:
- CDS translation is local and deterministic
- only translation table `1` is currently accepted
- a terminal stop codon is stripped
- internal stops are rejected
- ambiguous nucleotide codes are rejected
- non-triplet CDS lengths are rejected
- one protein per genome per gene group is retained using the longest-protein rule

### 8. Merge and validate

`bin/merge_acquisition_batches.py` merges validated batch outputs.

Current behavior:
- canonical merged outputs stay as flat files
- SQLite is still a later assembly artifact, not a live acquisition workspace
- `acquisition_validation.json` is written for both batch-local and merged results

---

## What is ignored or excluded by default

### Ignored before package download

These assembly rows are excluded during selection:
- non-RefSeq rows
- non-current rows
- superseded accessions where `assembly_accession != current_accession`
- rows missing required annotation
- duplicate accessions already selected under another request

### Ignored during package normalization

These sequence contexts are ignored before CDS normalization:
- raw genomic FASTA, because it is not requested in v1
- sequence-report rows outside `Primary Assembly` and `non-nuclear`
- alternate loci such as `ALT_REF_LOCI_*`
- patch units such as `PATCHES`

If a selected assembly is missing required annotation files:
- a `missing_annotation_component` warning is emitted
- that assembly does not contribute normalized sequences

### Ignored or degraded during linkage

Exact implemented behavior:
- exact duplicate CDS rows collapse silently into one normalized record
- same-key duplicate CDS rows with different nucleotide sequence emit `conflicting_duplicate_cds_key`
- header-only fallback is allowed when GFF linkage is missing, but it is recorded as a warning and a degraded linkage state

The current live smoke no longer leaves any rows in `unresolved_linkage`, but the fallback path still exists by design.

### Ignored during translation

These rows remain in `sequences.tsv` but do not become retained proteins:
- `partial_cds`
- `non_triplet_length`
- `internal_stop`
- `unknown_translation_table`
- `unsupported_ambiguity`

This is a conservative exclusion policy, not a parser failure policy.

### Immune receptor segment policy

Immunoglobulin and T-cell receptor segment rows are now linked correctly through the GFF gene-segment alias rule.

Many of them are still excluded from translated proteins because the GFF marks them as partial, often together with:
- `exception=rearrangement required for product`

For v1, these rows are intentionally:
- kept in normalized CDS outputs when they pass normalization
- excluded from protein-based detection when they are partial

This is why the remaining live warnings are dominated by `partial_cds` rather than `unresolved_linkage`.

---

## Canonical acquisition outputs

Per validated batch, the current acquisition path writes:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `cds.fna`
- `proteins.tsv`
- `proteins.faa`
- `normalization_warnings.tsv`
- `download_manifest.tsv`
- `acquisition_validation.json`

Merged acquisition outputs preserve the same canonical tables and warning artifacts across successful batches.

---

## Live smoke behavior

The opt-in live smoke check lives at:
- `scripts/smoke_live_acquisition.sh`

Current behavior:
- if the taxonomy DB does not exist, the script builds it with `taxon-weaver build-db --download`
- then it runs one deterministic name-resolution check
- then it runs one bounded single-accession acquisition check

The smoke check is intentionally:
- real
- networked
- opt-in

It is not part of the default unit-test suite.

For execution details, see:
- [live-smoke.md](./live-smoke.md)
