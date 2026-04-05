# Phase 3 Implementation Sequence

## Purpose

This document turns the frozen Phase 2 scientific core into an implementation order for standalone scripts and libraries.

Phase 3 is not the Nextflow phase.
Its job is to produce directly runnable CLIs and reusable Python helpers that honor the frozen contracts without depending on workflow orchestration.

---

## Rules for Phase 3

- Keep biology in Python, not in workflow files.
- Keep outputs flat and inspectable before SQLite assembly.
- Make every `bin/` script directly CLI-runnable.
- Validate each vertical slice before starting the next one.
- Reuse frozen Phase 2 decisions instead of reopening them in code.
- Prefer one thin CLI per operational task over giant mixed scripts.

---

## Implementation order

### Slice 0: bootstrap shared foundations

Goal:
- establish the minimum reusable helpers required by every later slice

Planned outputs:
- TSV read/write helpers
- stable ID helpers
- structured warning helpers
- parameter-record writer for `run_params.tsv`
- simple contract validation helpers

Why this comes first:
- every later slice needs deterministic IDs, warnings, and TSV output

Likely problems:
- helpers become a premature framework
- validation logic gets duplicated across scripts before a shared layer exists

Planned mitigation:
- build only the helpers required by the first acquisition and detection scripts
- keep shared utilities small and focused on contracts

Acceptance checks:
- one tiny synthetic TSV round-trip
- one deterministic ID-generation check
- one warning-record emission check

---

### Slice 1: request resolution and assembly planning

Goal:
- turn user intent into a fixed, reviewable assembly manifest

Planned CLI responsibilities:
- resolve taxa with `taxon-weaver`
- enumerate RefSeq assembly candidates from NCBI metadata
- apply selection policy
- derive bounded execution batches

Expected artifacts:
- `resolved_requests.tsv`
- `taxonomy_review_queue.tsv`
- `assembly_inventory.tsv`
- `selected_assemblies.tsv`
- `selected_batches.tsv`
- `excluded_assemblies.tsv`

Why this comes before any heavy download:
- it freezes scientific intent
- it reduces retry cost
- it supports rate-conscious execution

Likely problems:
- batch derivation is tied too tightly to taxonomy rather than workload size
- retries require re-running selection logic instead of reusing the frozen manifest
- selection reasoning becomes opaque

Planned mitigation:
- derive batches only from the frozen selection manifest
- record explicit `selection_reason` and `batch_reason`
- treat `selected_batches.tsv` as the operational input for later download steps

Acceptance checks:
- deterministic taxon request resolves or enters review queue
- same input manifest yields the same selected assemblies
- each selected assembly appears in exactly one batch

---

### Slice 2: package download, normalization, and translation

Goal:
- retrieve annotation-focused RefSeq package contents and normalize them into canonical CDS and protein inputs

Detailed reference:
- [acquisition-implementation.md](./acquisition-implementation.md)

Planned CLI responsibilities:
- download packages from `selected_batches.tsv`
- rehydrate dehydrated packages when needed
- parse package metadata
- normalize CDS records and metadata
- derive one retained translated protein per retained CDS record

Expected artifacts:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- normalized CDS FASTA
- normalized translated protein FASTA
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `acquisition_validation.json`

Why this is the first full biological slice:
- every detection method depends on the same normalized protein inputs
- translation policy is one of the biggest scientific-risk areas in the rebuild

Likely problems:
- GFF parsing varies across packages
- CDS translation failures are more common than expected
- local overrides start bypassing the canonical CDS-driven path
- batch-local outputs become hard to merge deterministically

Planned mitigation:
- keep GFF as the first linkage authority
- exclude translation failures conservatively and record warning codes
- keep external protein use as an explicit local override path only
- define deterministic merge behavior for batch outputs up front

Acceptance checks:
- one clean RefSeq package yields canonical `genomes.tsv`, `sequences.tsv`, and `proteins.tsv`
- one deliberately invalid CDS record is excluded with the expected warning code
- the same package normalized twice yields identical IDs and FASTA headers

---

### Slice 3: pure detection end to end

Goal:
- implement the strictest detection method first and prove the call contract on real inputs

Planned CLI responsibilities:
- scan translated protein inputs
- call `pure` tracts
- emit `pure_calls.tsv`
- emit method parameters to `run_params.tsv`

Why this is the first detection slice:
- it is the smallest and least environment-dependent method
- it establishes the shared call schema early

Likely problems:
- coordinate handling drifts from the contract
- trimming behavior is applied inconsistently
- contiguous-run handling is implemented differently than specified

Planned mitigation:
- build directly against the Phase 2 worked examples
- validate every call with shared contract checks before writing output

Acceptance checks:
- Phase 2 pure-method worked example reproduces exactly
- output rows satisfy `repeat_count + non_repeat_count = length`
- coordinates are 1-based and inclusive

---

### Slice 4: threshold detection end to end

Goal:
- implement the density-based method without breaking schema compatibility

Planned CLI responsibilities:
- scan translated protein inputs
- seed qualifying windows
- merge and extend candidates
- emit `threshold_calls.tsv`

Why this comes after pure:
- it shares the same output contract
- it adds complexity in windowing and boundary extension, not in acquisition

Likely problems:
- extension logic materially changes tract boundaries
- threshold code starts overlapping semantically with pure due to accidental merge rules

Planned mitigation:
- keep pure and threshold logic in separate code paths
- validate against the worked example that pure should reject and threshold should keep

Acceptance checks:
- Phase 2 threshold worked example reproduces exactly
- threshold output contract matches pure output contract
- parameter recording captures window size and minimum count

---

### Slice 5: similarity-based detection

Goal:
- implement a runnable similarity strategy without blocking on final backend environment details

Implementation order inside this slice:
1. deterministic fallback (`template_local`)
2. backend adapter for `blastp`
3. backend adapter for `diamond blastp`

Why this order:
- it keeps the method runnable early
- it isolates backend-specific concerns from shared call shaping

Likely problems:
- fallback behavior gets treated as scientifically identical to BLAST
- backend-native scores are mixed with fallback scores without labeling
- environment setup for `blastp` or `diamond` becomes the blocker for all remaining work

Planned mitigation:
- always record backend identity in `run_params.tsv`
- treat score semantics as backend-local
- keep fallback and production adapters behind one CLI contract but separate internal code paths

Acceptance checks:
- Phase 2 blast-like worked example reproduces under `template_local`
- backend selection is explicit in parameters
- output schema remains method-compatible with pure and threshold

---

### Slice 6: codon extraction and repeat-feature enrichment

Goal:
- attach codon sequences conservatively to amino-acid calls without forcing residue-specific metrics into v1

Planned CLI responsibilities:
- join calls back to normalized CDS records
- slice codons from amino-acid coordinates
- leave codon fields empty when slicing fails
- emit warning artifacts where needed

Why this comes after detection:
- codon extraction depends on finalized amino-acid call boundaries

Likely problems:
- off-by-one slicing bugs
- silent failures create misleading codon strings
- residue-specific metrics creep into the first release

Planned mitigation:
- keep amino-acid call coordinates as the only slicing coordinates
- validate codon length against amino-acid tract length
- leave codon metric fields empty in v1 even when codon sequence is present

Acceptance checks:
- codon length equals `3 * length` for successful rows
- failed slicing preserves the amino-acid call and empties codon fields
- no residue-specific metric is emitted in v1 outputs

---

### Slice 7: SQLite assembly

Goal:
- assemble validated flat outputs into the final SQLite artifact

Planned CLI responsibilities:
- create schema
- import canonical metadata and method outputs
- create indexes after bulk load
- validate row counts and key reachability

Why this comes late:
- SQLite is a sink, not a live workspace

Likely problems:
- import code silently repairs invalid data
- partial imports leave the database inconsistent

Planned mitigation:
- validate before import
- run imports in transactions
- hard-fail on structural import problems

Acceptance checks:
- import order matches the Phase 2 decision register
- foreign-key reachability checks pass
- row counts reconcile with flat inputs

---

### Slice 8: summary exports and report-preparation tables

Goal:
- implement the reporting-prep layer without coupling biological logic to chart rendering

Planned CLI responsibilities:
- aggregate `summary_by_taxon.tsv`
- derive `regression_input.tsv`
- derive any additional report-prep tables needed for ECharts inputs
- optionally emit combined `echarts_options.json` only after data-prep logic is stable

Why this is still Phase 3:
- plotting preparation logic belongs to standalone scientific code
- the final rendering shell can wait until the data-prep layer is reliable

Likely problems:
- chart-oriented grouping logic leaks into the renderer
- codon-specific fields are forced into the residue-neutral first release

Planned mitigation:
- keep grouping logic in explicit reporting helpers
- keep v1 reports taxon-direct and residue-neutral

Acceptance checks:
- summary counts reconcile with call tables
- regression groups reconcile with summaries
- chart-prep JSON, if emitted, is fully derivable from finalized tables

---

## What not to do in Phase 3

- do not introduce Nextflow orchestration
- do not write directly into SQLite from acquisition or detection steps
- do not widen scope into annotation/domain enrichment
- do not build a browser application
- do not treat fallback similarity output as equivalent to validated BLAST output

---

## Phase 3 exit criteria

Phase 3 is complete when:
- each major scientific step runs as a direct CLI without Nextflow
- batch outputs can be validated and merged deterministically
- `pure`, `threshold`, and similarity-based methods all emit the shared call schema
- SQLite can be built from validated flat outputs only
- summary/report-prep outputs can be generated from finalized tables only
- the implementation can move into Phase 4 without inventing new biological rules
