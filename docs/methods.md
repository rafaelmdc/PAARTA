# Methods

## Purpose

This document records the v1 operational decisions that sit between the high-level roadmap and the implementation.

It answers the questions that were still underspecified in the original docs:
- how data enters the workflow
- how local and NCBI-backed acquisition coexist
- how one isoform per gene is selected
- what the three detection methods mean operationally
- how codon extraction, SQLite import, summaries, and ECharts reporting are bounded

These rules are the implementation target unless a later contract change is made explicitly.

---

## Scientific scope for v1

The first rebuild targets polyglutamine (`Q`) tracts only.

The workflow must support:
- acquisition of protein and optionally CDS data
- one retained isoform per gene
- three peer detection strategies: `pure`, `threshold`, and `blast`
- codon-aware feature extraction when CDS is available
- SQLite assembly from flat files
- summary tables and ECharts-based reporting from finalized outputs

The first rebuild does not require:
- non-polyQ repeat classes
- annotation/domain enrichment
- browser-facing applications
- direct database mutation during earlier pipeline stages

---

## Acquisition strategy

### Supported input modes

Two acquisition modes are supported in the same manifest contract:

1. `ncbi_datasets`
2. `local`

`ncbi_datasets` is the production path for rebuilding the original project from scratch.
`local` exists for tests, smoke datasets, and offline development.

### NCBI-backed acquisition

The planned acquisition step uses the NCBI `datasets` CLI for assembly/package retrieval and `taxon-weaver` as the canonical local taxonomy layer.

Current intent:
- enumerate candidate assemblies from NCBI metadata before downloading sequence packages
- request reference assemblies by accession
- include protein and CDS sequence files when available
- retain the raw package on disk for reproducibility
- normalize package contents into the canonical TSVs and normalized FASTA files

The implementation should tolerate either a hydrated local package or an already-downloaded package directory.

### Local acquisition

Local mode is planned to accept protein FASTA and optional CDS FASTA paths directly from the manifest.

This mode must:
- preserve the same downstream contracts as NCBI-backed acquisition
- write normalized FASTA files with internal IDs as headers
- remain deterministic for tests

### Taxonomy handling

Taxonomy metadata is planned to be normalized into `taxonomy.tsv`.

For v1:
- `taxon_id` is the stable reporting identifier
- `taxon_name`, `parent_taxon_id`, `rank`, and `lineage` are retained when available
- missing hierarchy information is allowed, but `taxon_id` must still exist

Operationally:
- build a local NCBI taxonomy SQLite database with `taxon-weaver`
- use `taxon-weaver` resolution for user-supplied taxon names
- use `taxon-weaver` lineage inspection for taxids returned by NCBI assembly metadata
- keep deterministic resolution authoritative and treat fuzzy suggestions as review-only

### Contamination checking

The original project performed contamination lineage checks during acquisition.

For the rebuild:
- contamination screening is not a blocker for v1 execution
- the acquisition layer records notes and source metadata
- explicit contamination validation can be added later as a separate single-purpose step

---

## Sequence preparation

### Normalized FASTA outputs

Acquisition is planned to write normalized FASTA files so downstream scripts do not rely on source-specific headers.

Rules:
- CDS FASTA headers become `sequence_id`
- protein FASTA headers become `protein_id`
- normalized rows point to those normalized FASTA paths

### Sequence-to-protein linkage

Default normalization authority:
1. `genomic.gff` feature relationships and attributes
2. structured package metadata and assembly reports
3. FASTA header metadata only as a documented fallback

The preferred linkage order is:
1. GFF-backed protein/CDS/transcript/gene relationships
2. explicit `protein_id` or transcript linkage carried in package metadata
3. shared transcript identifier recovered from FASTA metadata
4. shared gene identifier recovered from FASTA metadata

The workflow must not default to pairing records by normalized file order.
If a confident biological linkage cannot be established from the sources above, the record is emitted with a linkage warning rather than silently guessed.

When a confident CDS-to-protein mapping is not available:
- protein records are still emitted
- codon extraction is skipped for that record

### Isoform selection

The workflow is planned to keep one isoform per gene per genome.

v1 selection rule:
- group by `gene_symbol` when present
- otherwise group by a stable fallback key derived from transcript or sequence identity
- keep the longest protein sequence in each group
- break ties lexicographically by protein identifier

This rule is deterministic and easy to validate, even if it does not recover all historical choices.

---

## Detection methods

All methods are planned to emit the shared call contract.

Coordinates are 1-based and inclusive in amino-acid space.
All methods must trim leading and trailing non-`Q` residues from the final called tract.

### Pure method

Intent:
- capture canonical polyQ tracts with at most one single-residue interruption at a time

Default rule:
- detect maximal tracts containing `Q` runs separated by gaps of length at most 1
- require at least `min_q_count=6`

Reported features:
- `q_count`
- `non_q_count`
- `purity = q_count / length`

### Threshold method

Intent:
- capture biologically plausible but slightly impure tracts using a density rule

Default rule:
- sliding window size `8`
- minimum `Q` count `6`
- merge overlapping or directly adjacent qualifying windows
- extend merged candidates while tract purity stays above `0.70`

The default window definition is reported as `Q6/8`.

### Blast method

Intent:
- capture divergent or interrupted Q-rich tracts that resemble a polyQ template

Preferred backend:
- external `blastp` when available

v1 fallback backend:
- deterministic local template scoring against a polyQ template of length `10`
- score `+2` for `Q`, `-1` for non-`Q`
- retain positive-scoring segments that satisfy `min_q_count=6`
- merge hits when the gap between them is less than or equal to `template_length / 2`

The fallback is explicitly a `blast` contract implementation, not a claim of identical BLAST output.
Its purpose is to keep the workflow runnable and contract-compatible before a strict `blastp` integration is validated.

---

## Codon extraction and repeat features

Codon extraction is planned to be attempted only when a CDS sequence can be linked to the detected protein.

Rules:
- derive codon coordinates directly from amino-acid coordinates
- use the normalized CDS sequence as the nucleotide source of truth
- if translated CDS length disagrees with the retained protein sequence, leave `codon_sequence` empty
- compute CAG ratio only from glutamine codons within the extracted tract

Reported feature semantics:
- `length` counts the full amino-acid tract after trimming termini
- `q_count` counts only `Q` residues
- `non_q_count = length - q_count`
- `purity` is a decimal fraction in `[0, 1]`

---

## Database assembly

SQLite is planned to be assembled only after metadata and call files validate.

v1 rules:
- create schema from `assets/sql/schema.sql`
- import flat files inside transactions
- import method outputs into a unified `poly_calls` table
- create indexes after bulk import
- validate row counts and foreign-key reachability after import

SQLite remains a build artifact, not a workspace.

---

## Summary exports

### `summary_by_taxon.tsv`

Grouped by:
- `method`
- `taxon_id`
- `taxon_name`

Metrics:
- unique genomes
- unique proteins
- call counts
- tract length summary statistics
- purity summary statistics
- mean CAG ratio
- mean start fraction when protein length is known

### `regression_input.tsv`

Grouped by:
- `method`
- `macro_group`
- `poly_length`

For v1:
- `macro_group` defaults to `taxon_name`
- a later extension may derive coarser macro-groups from taxonomy lineage

---

## ECharts reporting

The reporting layer is downstream only.

v1 reporting outputs:
- a grouped bar chart summarizing calls by taxon and method
- a line/scatter style chart for mean CAG ratio by polyQ length
- a single reproducible HTML report backed by serialized ECharts options

Rules:
- report generation depends only on finalized tables or SQLite
- chart configuration is emitted as JSON for inspection and reuse
- the HTML report may load a pinned ECharts runtime from CDN in v1

---

## Known v1 boundaries

- NCBI-backed acquisition depends on the `datasets` CLI being installed in the execution environment
- the `blast` method uses a deterministic fallback when `blastp` is unavailable
- annotation and domain context are deferred
- contamination checks are documented but not enforced as a hard failure path
