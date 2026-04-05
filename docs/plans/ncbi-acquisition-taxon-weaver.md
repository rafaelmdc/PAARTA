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
5. Split the fixed selection manifest into bounded execution batches when needed.
6. Download annotation-focused assembly packages containing CDS, GFF, and metadata.
7. Rehydrate when NCBI delivers dehydrated packages.
8. Normalize package contents into canonical TSV and FASTA outputs, then translate retained CDS records locally.
9. Enrich taxonomy and lineage using `taxon-weaver`.
10. Emit validation and provenance artifacts for the acquisition stage.

---

## Execution policy for large runs

The rebuild should not default to one giant `download everything, then analyze everything` run.

Planned default:
- perform one global metadata enumeration pass across all requested taxa
- freeze one `selected_assemblies.tsv` manifest before large downloads begin
- process the selected assemblies in bounded batches
- treat SQLite import as a final assembly step after batch validation, not as a live target during batch execution

Recommended batching rule:
- if a requested taxon is small, it may remain one batch
- if a requested taxon is large, split it into fixed assembly-count batches rather than insisting on one taxon per batch

Recommended starting scale for v1:
- small runs may use one batch
- larger runs should start around `50-200` assemblies per batch and adjust only after validation
- dehydrated download plus explicit rehydration should be preferred for very large runs
- rehydration worker counts should start conservatively

Reason:
- lowers the risk of stressing NCBI services
- makes resume/retry behavior much simpler
- keeps runtime, disk use, and validation scope predictable
- fits the project rule that SQLite is a final artifact built from validated flat outputs

Possible problems:
- taxon-by-taxon batching creates very uneven workload sizes
- a single giant batch fails late and wastes time and network traffic
- parallel batch execution multiplies download pressure unexpectedly

Planned mitigation:
- separate the global selection manifest from the execution batches
- let batch boundaries be operational rather than biological when needed
- cap batch concurrency independently from per-batch download worker counts
- record batch membership explicitly so reruns can target failed subsets only

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
- `taxonomy_review_queue.tsv`

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
- emit review-required rows into a review queue artifact and continue only with deterministic rows
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
- RefSeq assemblies only
- keep both reference and representative RefSeq category metadata in the inventory
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
- use RefSeq assemblies only
- prefer reference assemblies
- allow RefSeq representative assemblies when no suitable RefSeq reference assembly exists
- prefer annotated assemblies
- prefer current/latest accessions
- preserve the decision logic in the output manifest, not in code comments

Planned output:
- `selected_assemblies.tsv`
- `selected_accessions.txt`
- `selected_batches.tsv`

Possible problems:
- selection rules are too implicit and become impossible to audit
- “reference-only” quietly excludes too much biology

Mitigation:
- keep `selection_reason` explicit per row
- generate a companion `excluded_assemblies.tsv` for auditability
- derive execution batches from the frozen selection manifest rather than re-querying NCBI during retries
- if no annotation-capable assembly exists, emit the taxon into review/exclusion outputs rather than attempting blind continuation

### Step 4.5: derive execution batches

Planned behavior:
- derive batch membership only after `selected_assemblies.tsv` is frozen
- preserve one assembly accession in exactly one batch
- allow small taxa to remain intact while splitting large taxa into fixed-size batches
- record batch metadata so retries can target only failed subsets

Planned output:
- `selected_batches.tsv`

Planned columns:
- `batch_id`
- `request_id`
- `assembly_accession`
- `taxid`
- `batch_reason`

Possible problems:
- batches are re-derived differently across reruns
- retrying failed work requires reconstructing batch membership from logs

Mitigation:
- materialize the batch file before downloads begin
- make `selected_batches.tsv` the operational input to download and normalization steps

### Step 5: download annotation-focused assembly packages

Planned NCBI interface:
- `datasets download genome accession`

Planned package contents to request:
- CDS FASTA
- GFF3
- assembly metadata reports

Planned download mode:
- use accessions from `selected_accessions.txt` or per-batch projections from `selected_batches.tsv`
- for small/medium runs, use direct zip download
- for larger runs, allow dehydrated download plus explicit rehydration

Example command shape:

```bash
datasets download genome accession \
  --inputfile selected_accessions.txt \
  --include cds,gff3,seq-report \
  --filename acquisition/raw/ncbi_genomes.zip
```

Possible problems:
- downloads are slow or interrupted
- package zips are large enough to stress local disk
- package contents vary across accessions
- too many concurrent batches create avoidable network pressure

Mitigation:
- keep one raw package directory with checksums and logs
- use staged download directories so partially failed runs are obvious
- key normalization off package manifests and metadata, not filename assumptions alone
- cap batch-level parallelism separately from rehydration worker counts

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
- `cds.fna`
- `genomic.gff` or equivalent GFF3 annotation file

Normalization responsibilities:
- assign canonical internal IDs
- map CDS records to gene/transcript identifiers
- translate retained CDS records into canonical protein FASTA
- retain one isoform per gene
- write normalized FASTA with internal IDs
- emit `genomes.tsv`, `taxonomy.tsv`, `sequences.tsv`, and `proteins.tsv`

Default normalization authority:
1. `genomic.gff` is the primary source of gene, transcript, and CDS relationships
2. package metadata and assembly reports are supporting sources
3. CDS FASTA deflines are fallback only

Planned strategy for sequence linkage:
1. use GFF relationships first
2. use structured package metadata where needed
3. use structured CDS defline metadata only when the first two sources are insufficient
4. stop at an explicit warning state rather than silently guessing a biological relationship

Default translation policy:
1. use the retained CDS sequence as the nucleotide source of truth
2. translate locally after normalization and isoform selection
3. emit translated proteins as the canonical amino-acid input for detection
4. exclude CDS records that cannot be translated conservatively and record them in `normalization_warnings.tsv`

Default normalization rule:
- if `genomic.gff` is present and parseable, it is authoritative even when CDS deflines appear to contain overlapping identifiers
- if `genomic.gff` is absent or incomplete, the run may continue only in a degraded mode with explicit `normalization_warnings.tsv` entries
- degraded mode is acceptable only where CDS-to-protein derivation remains conservative

Possible problems:
- GFF conventions differ across packages
- CDS link fields are incomplete
- one gene maps to multiple transcripts in inconsistent ways
- CDS sequences cannot always be translated cleanly under conservative rules
- FASTA headers appear usable but disagree with GFF-backed relationships

Mitigation:
- treat GFF as preferred but not assumed-perfect
- make unresolved linkage an explicit output state
- store enough source identifiers to audit normalization later
- when GFF and FASTA disagree, prefer GFF and emit a warning rather than merging mixed provenance
- exclude translation failures rather than substituting external protein sequences silently

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
- every retained protein can be traced back to a translated CDS record or an explicitly documented local override
- every unresolved linkage is counted and reported
- every excluded translation failure is counted and reported
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
- `taxonomy_review_queue.tsv`
- `assembly_inventory.tsv`
- `selected_assemblies.tsv`
- `selected_batches.tsv`
- `excluded_assemblies.tsv`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

Reason:
- the canonical tables feed the pipeline
- the support artifacts make the retrieval choices reviewable

---

## Settled policy decisions

Settled defaults:
- assembly category policy: `reference preferred, representative allowed` within RefSeq
- missing annotation policy: retain for review/exclusion and do not process automatically
- local cache policy: reusable external cache preferred, project-local fallback allowed

---

## Recommended implementation order later

When implementation is approved, acquisition should be built in this order:

1. taxonomy bootstrap with `taxon-weaver`
2. request resolution artifact
3. assembly inventory enumeration
4. selection manifest generation
5. execution batch derivation
6. raw package download/rehydration
7. normalization of one clean package
8. normalization of multiple assemblies
9. validation/provenance artifacts

This order matters because it lets the project validate scientific intent before dealing with heavy downloads and tricky annotation parsing.
