# NCBI Acquisition Plan With Taxon Weaver

## Purpose

Define, in implementation-ready detail, how HomoRepeat will:
- choose target taxa or accessions
- retrieve assemblies and sequence packages from NCBI
- resolve and enrich taxonomy with `taxon-weaver`
- normalize raw package contents into the canonical workflow inputs

This plan is intentionally explicit because acquisition is the most failure-prone part of the rebuild.

---

## Core dependency choices

### NCBI side

Planned tools:
- `datasets summary genome`
- `datasets download genome`
- `datasets rehydrate` when downloads are dehydrated or too large
- `datasets summary taxonomy` only when extra taxonomy metadata is needed for debugging or audits

Reason:
- these are the documented NCBI-supported interfaces for assembly enumeration, package download, and large-download rehydration

### Taxonomy side

Planned dependency:
- `taxon-weaver`

Planned usage:
- bootstrap a local taxonomy SQLite database from NCBI taxdump
- resolve user-provided taxon names conservatively
- fetch lineage for NCBI taxids during enrichment
- keep deterministic resolution authoritative and treat fuzzy suggestions as review-only

Preferred integration mode:
- direct Python service calls inside HomoRepeat code

Acceptable bootstrap CLI use:
- `taxon-weaver build-db`

Reason:
- the `taxon-weaver` docs explicitly position the Python service as the long-term integration boundary, while the CLI is thin and mainly operational

Dependency rule:
- install `taxon-weaver` into HomoRepeat as a dependency
- do not vendor or copy its source tree into this repository

---

## High-level acquisition flow

1. Build or reuse a local taxonomy database with `taxon-weaver`.
2. Resolve requested taxa or validate requested taxids.
3. Enumerate candidate assemblies from NCBI metadata before downloading sequence data.
4. Apply assembly-selection rules and record the selection manifest.
5. Download genome data packages containing proteins, CDS, and metadata.
6. Rehydrate when NCBI delivers dehydrated packages.
7. Normalize package contents into canonical TSV and FASTA outputs.
8. Enrich taxonomy and lineage using `taxon-weaver`.
9. Emit validation and provenance artifacts for the acquisition stage.

---

## Planned input model

### User-facing scientific input

Planned file:
- `requested_taxa.tsv`

Planned columns:
- `request_id`
- `input_value`
- `input_type`
- `provided_rank`
- `selection_policy`
- `notes`

Allowed `input_type` values:
- `taxid`
- `scientific_name`
- `common_name`
- `assembly_accession`

Reason:
- separate the user’s scientific request from the internal assembly-selection artifact

Possible problems:
- users mix taxon names and direct accessions in ad hoc ways
- ambiguous names are silently coerced into taxids

Mitigation:
- keep a pre-download resolution step that emits explicit statuses
- require review if resolution is ambiguous or fuzzy

### Internal selection artifact

Planned file:
- `assembly_inventory.tsv`

This is not the user’s request.
It is the machine-generated record of all candidate assemblies considered for download.

Planned columns:
- `request_id`
- `resolved_taxid`
- `resolved_name`
- `assembly_accession`
- `current_accession`
- `source_database`
- `assembly_level`
- `assembly_type`
- `assembly_status`
- `refseq_category`
- `annotation_status`
- `organism_name`
- `taxid`
- `selection_decision`
- `selection_reason`

Reason:
- assembly enumeration and assembly selection need to be inspectable and reproducible

---

## Step-by-step plan

### Step 1: bootstrap taxonomy with `taxon-weaver`

Planned operation:
- build a local NCBI taxonomy SQLite file once per taxonomy version

Planned command shape:

```bash
taxon-weaver build-db \
  --download \
  --dump data/taxdump/taxdump.tar.gz \
  --db data/ncbi_taxonomy.sqlite \
  --report-json data/ncbi_taxonomy_build.json
```

Planned artifacts:
- `data/ncbi_taxonomy.sqlite`
- `data/taxdump/taxdump.tar.gz`
- `data/ncbi_taxonomy_build.json`

Possible problems:
- rebuilding taxonomy every run wastes time
- taxonomy build version drifts between runs and breaks reproducibility
- the taxonomy DB is present but stale relative to the run

Mitigation:
- cache the taxonomy DB outside the main run workspace when possible
- record taxonomy build metadata in acquisition outputs
- allow “reuse existing taxonomy DB” versus “rebuild now” as an explicit run choice

### Step 2: resolve requested taxa conservatively

Planned behavior:
- numeric `taxid` inputs bypass name resolution and use lineage inspection directly
- string inputs are resolved through `taxon-weaver`
- deterministic exact results are accepted
- fuzzy or transformed matches are emitted into a review-required artifact

Preferred API use:
- `TaxonomyResolverService.resolve_name()`
- `TaxonomyResolverService.get_lineage()`

Planned output:
- `resolved_requests.tsv`

Planned columns:
- `request_id`
- `original_input`
- `normalized_input`
- `resolution_status`
- `review_required`
- `matched_taxid`
- `matched_name`
- `matched_rank`
- `warnings`
- `taxonomy_build_version`

Possible problems:
- large clade names resolve to unexpected ranks
- common names resolve differently than expected
- fuzzy suggestions are tempting but unsafe

Mitigation:
- require exact/deterministic status for automatic continuation
- treat review-required rows as a hard gate unless the user explicitly overrides
- preserve warnings and lineage context in the resolution artifact

### Step 3: enumerate candidate assemblies from NCBI before download

Planned behavior:
- use resolved taxids to query NCBI assembly metadata first
- build a candidate inventory before any large file download

Planned NCBI interface:
- `datasets summary genome taxon`

Planned query defaults for v1:
- annotated assemblies only
- latest assembly version only
- reference assemblies by default
- keep all assembly levels relevant to the original project unless the user narrows them

Planned artifact:
- `assembly_inventory.jsonl`
- `assembly_inventory.tsv`

Example command shape:

```bash
datasets summary genome taxon 33511 \
  --annotated \
  --assembly-version latest \
  --as-json-lines \
  > acquisition/assembly_inventory.jsonl
```

Possible problems:
- querying a very broad taxon returns too many assemblies
- reference-only filtering is too strict for some clades
- metadata fields relevant for later normalization are missing from the first pass

Mitigation:
- separate query policy from download policy
- record when no reference assembly exists so fallback policy can be reviewed explicitly
- preserve raw JSONL inventory alongside the TSV projection

### Step 4: apply assembly-selection policy

Planned default policy for first implementation:
- prefer reference assemblies
- prefer annotated assemblies
- prefer current/latest accessions
- preserve the decision logic in the output manifest, not in code comments

Fallback policy questions to settle before coding:
- if no reference assembly exists, should GenBank be allowed automatically?
- if no annotated assembly exists, should the taxon be skipped or retained for review?

Planned output:
- `selected_assemblies.tsv`
- `selected_accessions.txt`

Possible problems:
- selection rules are too implicit and become impossible to audit
- “reference-only” quietly excludes too much biology

Mitigation:
- keep `selection_reason` explicit per row
- generate a companion `excluded_assemblies.tsv` for auditability

### Step 5: download genome data packages

Planned NCBI interface:
- `datasets download genome accession`

Planned package contents to request:
- protein FASTA
- CDS FASTA
- GFF3
- assembly metadata reports

Planned download mode:
- use accessions from `selected_accessions.txt`
- for small/medium runs, use direct zip download
- for larger runs, allow dehydrated download plus explicit rehydration

Example command shape:

```bash
datasets download genome accession \
  --inputfile selected_accessions.txt \
  --include protein,cds,gff3,seq-report \
  --filename acquisition/raw/ncbi_genomes.zip
```

Possible problems:
- downloads are slow or interrupted
- package zips are large enough to stress local disk
- package contents vary across accessions

Mitigation:
- keep one raw package directory with checksums and logs
- use staged download directories so partially failed runs are obvious
- key normalization off package manifests and metadata, not filename assumptions alone

### Step 6: rehydrate when needed

Planned NCBI interface:
- `datasets rehydrate`

When to use it:
- large runs
- dehydrated package mode
- resumed downloads after partial network failure

Possible problems:
- users assume the zip already contains all sequences
- rehydration is run from the wrong directory
- the final normalized stage consumes a partially rehydrated bag

Mitigation:
- detect dehydration state explicitly before normalization
- add a completion check before any parsing starts
- record rehydration status in acquisition metadata

Example command shape:

```bash
unzip acquisition/raw/ncbi_genomes.zip -d acquisition/raw/ncbi_package
datasets rehydrate --directory acquisition/raw/ncbi_package
```

### Step 7: normalize package contents

Planned authoritative package components:
- `assembly_data_report.jsonl`
- package manifest/catalog file
- `protein.faa`
- `cds.fna`
- `genomic.gff` or equivalent GFF3 annotation file

Normalization responsibilities:
- assign canonical internal IDs
- map proteins to CDS/gene/transcript identifiers
- retain one isoform per gene
- write normalized FASTA with internal IDs
- emit `genomes.tsv`, `taxonomy.tsv`, `sequences.tsv`, and `proteins.tsv`

Default normalization authority:
1. `genomic.gff` is the primary source of gene, transcript, CDS, and protein relationships
2. package metadata and assembly reports are supporting sources
3. FASTA deflines are fallback only

Planned strategy for sequence linkage:
1. use GFF relationships first
2. use structured package metadata where needed
3. use structured FASTA defline metadata only when the first two sources are insufficient
4. stop at an explicit warning state rather than silently guessing a biological relationship

Default normalization rule:
- if `genomic.gff` is present and parseable, it is authoritative even when FASTA deflines appear to contain overlapping identifiers
- if `genomic.gff` is absent or incomplete, the run may continue only in a degraded mode with explicit `normalization_warnings.tsv` entries
- degraded mode is acceptable for amino-acid detection, but codon-aware joins must remain conservative

Possible problems:
- GFF conventions differ across packages
- CDS/protein link fields are incomplete
- one gene maps to multiple proteins and transcripts in inconsistent ways
- FASTA headers appear usable but disagree with GFF-backed relationships

Mitigation:
- treat GFF as preferred but not assumed-perfect
- make unresolved linkage an explicit output state
- store enough source identifiers to audit normalization later
- when GFF and FASTA disagree, prefer GFF and emit a warning rather than merging mixed provenance

### Step 8: enrich taxonomy using `taxon-weaver`

Planned behavior:
- enrich each selected assembly with lineage from `taxon-weaver`
- build `taxonomy.tsv` from taxids observed in selected assemblies
- use `get_lineage(taxid)` for enrichment when NCBI already provides the taxid

Why not resolve names again here:
- once NCBI metadata gives the assembly taxid, the taxid is the authoritative join key

Possible problems:
- taxonomy DB version and NCBI assembly metadata date are out of sync
- lineage retrieval fails for obsolete/merged taxids

Mitigation:
- record taxonomy build version and acquisition date in run metadata
- if a taxid lookup fails, emit a hard warning and stop before downstream grouping logic

### Step 9: acquisition validation and provenance

Planned outputs:
- `acquisition_validation.json`
- `download_manifest.tsv`
- `normalization_warnings.tsv`

Validation checks:
- every selected accession produced a package or a documented failure
- every genome row has a taxid
- every protein row belongs to a genome
- every retained protein has a deterministic isoform decision
- every unresolved linkage is counted and reported
- every codon-capable linkage can be traced back to GFF or an explicitly documented fallback path

Possible problems:
- acquisition “succeeds” with large silent losses
- later phases inherit missing data without context

Mitigation:
- fail loudly on structural losses
- allow degraded-but-documented continuation only where scientifically acceptable

---

## Planned integration with HomoRepeat contracts

Acquisition must emit these canonical outputs:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`

It should also emit these supporting artifacts:
- `resolved_requests.tsv`
- `assembly_inventory.tsv`
- `selected_assemblies.tsv`
- `excluded_assemblies.tsv`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

Reason:
- the canonical tables feed the pipeline
- the support artifacts make the retrieval choices reviewable

---

## Policy decisions to settle before coding

1. Default assembly source policy
   `RefSeq only` or `RefSeq preferred, GenBank fallback`

2. Default assembly category policy
   `reference only` or `reference preferred, representative allowed`

3. Missing annotation policy
   skip unannotated assemblies or retain them in a review queue

4. Taxonomy ambiguity policy
   hard-fail on review-required request resolution or allow a user-approved override manifest

5. Local cache policy
   whether raw downloads and taxonomy DBs live inside the project tree or in a reusable external cache

---

## Recommended implementation order later

When implementation is approved, acquisition should be built in this order:

1. taxonomy bootstrap with `taxon-weaver`
2. request resolution artifact
3. assembly inventory enumeration
4. selection manifest generation
5. raw package download/rehydration
6. normalization of one clean package
7. normalization of multiple assemblies
8. validation/provenance artifacts

This order matters because it lets the project validate scientific intent before dealing with heavy downloads and tricky annotation parsing.
