# Implementation Plan

## Purpose

This document turns the roadmap into an execution plan without starting implementation.

It is intentionally biased toward:
- explicit phase gates
- dependency choices made up front
- likely failure points identified before coding
- small reviewable increments instead of a single large build

The detailed plans for the first four phases live under `docs/plans/`.

---

## Planning assumptions

These plans assume:
- the current repository remains documentation-first until implementation is explicitly approved
- `taxon-weaver` will be used as a real dependency for taxonomy resolution and lineage retrieval
- NCBI Datasets is the primary acquisition source for assembly metadata plus CDS/GFF annotation data
- the first end-to-end release supports generic homorepeat detection with residue-neutral reporting
- taxonomic scope is configured by taxon name or taxid rather than hardcoded to Deuterostomia
- the first reporting rebuild will end with reproducible ECharts outputs, but ECharts implementation starts only after the scientific core is stable

---

## Phase map

### Phase 0

Freeze the scientific specification.

Main outcome:
- one unambiguous statement of scope, acquisition policy, detection intent, comparability requirements, and non-goals

Detailed plan:
- [phase-0-scientific-specification.md](./plans/phase-0-scientific-specification.md)

### Phase 1

Freeze the data and output model.

Main outcome:
- canonical file/table contracts and validation rules strong enough that implementation can begin without schema drift

Detailed plan:
- [phase-1-data-output-model.md](./plans/phase-1-data-output-model.md)

### Phase 2

Freeze the scientific core before writing the code.

Main outcome:
- explicit operational decisions for acquisition normalization, taxonomy integration, isoform policy, detection algorithms, codon extraction, database import, and reporting inputs

Detailed plan:
- [phase-2-scientific-core.md](./plans/phase-2-scientific-core.md)

### Phase 3 and later

Only after Phases 0 to 2 are accepted:
- build standalone scripts/modules
- wrap them in Nextflow DSL2
- validate against smoke and representative datasets
- rebuild reports and ECharts outputs

At that point the implementation order should still be vertical:
1. acquisition
2. normalization and taxonomy enrichment
3. one detection method end-to-end
4. remaining detection methods
5. SQLite import
6. summary exports
7. ECharts reporting
8. Nextflow wrapping and validation

Phase 3 implementation reference:
- [phase-3/README.md](./plans/phase-3/README.md)

---

## Core dependency decisions

### NCBI retrieval

Planned source of truth:
- NCBI Datasets CLI metadata and data packages

Reason:
- it provides assembly metadata, package manifests, CDS/GFF files, and a documented rehydration path for large downloads

Detailed plan:
- [ncbi-acquisition-taxon-weaver.md](./plans/ncbi-acquisition-taxon-weaver.md)

### Taxonomy integration

Planned source of truth:
- `taxon-weaver`

Planned use:
- build a local taxonomy SQLite database from NCBI taxdump
- resolve user-supplied taxon names deterministically
- fetch lineage for taxids returned by NCBI assembly metadata
- keep fuzzy suggestions as review-only, not silent auto-accepts

### Similarity backend

Planned source of truth:
- configurable production backend using `blastp` or `diamond blastp`

Planned use:
- record the selected backend in run metadata or parameter outputs
- allow a deterministic local fallback only during early validation
- validate representative cases before treating backend outputs as interchangeable

### Reporting runtime

Planned output layer:
- analysis-ready TSVs and SQLite first
- ECharts JSON/HTML second

Reason:
- charting should not drive early scientific-contract decisions

### Execution model

Planned default:
- perform one global metadata enumeration pass first
- freeze a `selected_assemblies.tsv` manifest before large downloads begin
- process selected assemblies in bounded batches rather than as one unbounded run
- import into SQLite only after batch outputs validate

Reason:
- reduces the risk of overloading NCBI services
- makes retries and resume behavior tractable
- keeps SQLite as a final assembly artifact rather than a live parallel workspace

---

## Settled defaults before coding

The current documentation baseline assumes:

1. Assembly source policy
   v1 defaults to `RefSeq only`.

2. Isoform policy
   v1 keeps the deterministic `longest protein per gene` rule.

3. Taxonomy review policy
   unresolved or fuzzy `taxon-weaver` results are emitted into a review queue rather than hard-failing the full run.

4. Contamination policy
   contamination remains note-only in v1.

5. Execution policy
   large runs use a frozen selection manifest plus bounded execution batches.

The detailed operational defaults are recorded in:
- [phase-2/decision-register.md](./plans/phase-2/decision-register.md)
- [phase-2/worked-examples.md](./plans/phase-2/worked-examples.md)

---

## Main cross-phase risks

### Risk: acquisition logic becomes too coupled to one exact package layout

Why it matters:
- NCBI package contents and metadata fields can shift over time

Mitigation:
- plan around package manifest inspection and schema-aware parsing
- preserve raw package paths and package metadata in outputs
- separate metadata enumeration from sequence normalization

### Risk: large runs fail late after excessive downloading

Why it matters:
- a single monolithic run is harder to retry, audit, and rate-limit safely

Mitigation:
- freeze the global selection manifest first
- process downloads and normalization in bounded batches
- assemble SQLite only from validated flat outputs after batch completion

### Risk: taxonomy ambiguity is hidden instead of surfaced

Why it matters:
- silent taxonomy “fixes” would undermine scientific trust

Mitigation:
- use `taxon-weaver` deterministic paths first
- treat fuzzy or transformed matches as review-required
- persist taxonomy warnings in intermediate outputs

### Risk: scientific definitions drift during coding

Why it matters:
- rebuilding from scratch makes it easy to accidentally encode convenience instead of intent

Mitigation:
- treat Phase 2 documents as the implementation gate
- do not write detection/reporting code until method rules are accepted

### Risk: reporting needs back-propagate into contracts too late

Why it matters:
- missing columns for codon ratios, macro-groups, or taxon lineage would force churn

Mitigation:
- include summary/regression/ECharts requirements in Phase 1 and Phase 2 planning
- define report inputs before figure code exists

---

## Immediate documentation deliverables

Before any code:
- finalize the detailed plans in `docs/plans/`
- reconcile any remaining contract gaps these plans expose
- mark open questions clearly where user approval is needed
