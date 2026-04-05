# Phase 1 Plan: Data and Output Model

## Objective

Freeze the data contracts tightly enough that implementation can start without schema churn.

This phase is about:
- table/file structure
- IDs
- validation rules
- output naming
- which stage owns which artifact

It is not about algorithm implementation yet.

---

## Primary design rule

Every stage must emit inspectable flat artifacts before anything is inserted into SQLite.

That implies:
- acquisition owns normalized TSV and FASTA outputs
- detection owns method-specific call tables
- database assembly owns import only
- reporting owns summaries and charts only

---

## Planned work packages

### Work package 1.1: freeze acquisition input contracts

Contracts to finalize:
- `acquisition_targets.tsv`
- allowed `source` modes
- required fields for NCBI mode versus local mode

Planned fields:
- request identity: target taxon or accession input
- retrieval policy: source, assembly filters, include/exclude flags
- local-path mode fields for smoke/offline data

Possible problems:
- the manifest becomes too low-level and hard to use
- critical retrieval policy ends up encoded only in Nextflow params or filenames

Planned mitigation:
- keep one manifest for scientific intent
- keep runtime-only options in params/config, not in biological tables

### Work package 1.2: freeze canonical metadata tables

Tables:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`

Decisions to freeze:
- one biological row unit per table
- which fields are required versus optional
- whether absent CDS data is allowed and how it is represented
- taxonomy lineage is stored as explicit parent-linked taxon rows in v1

Possible problems:
- sequence-to-protein linkage is under-specified
- locally translated proteins are not distinguished cleanly from externally provided proteins
- acquisition outputs become impossible to validate because nullable behavior is vague

Planned mitigation:
- define null semantics explicitly
- document fallback behavior when CDS normalization or translation is missing or partial
- state one normalization authority explicitly: GFF-backed joins first, metadata second, FASTA headers last

### Work package 1.3: freeze detection-call schema

Tables/files:
- `pure_calls.tsv`
- `threshold_calls.tsv`

Decisions to freeze:
- residue-agnostic required columns for homorepeat calls
- coordinate system
- purity semantics
- codon sequence semantics
- score semantics for methods that emit method-specific scores
- provenance fields for method settings

Possible problems:
- the current draft remains residue-biased and leaks residue-specific assumptions into the canonical schema
- methods end up emitting comparable-looking but semantically incompatible fields
- later summary code has to branch by method because the shared schema is not actually shared

Planned mitigation:
- define one required shared core
- keep method-specific extras optional and clearly named
- generalize residue-specific draft fields before treating the contract as stable

### Work package 1.4: freeze SQLite ownership

Database artifacts:
- `assets/sql/schema.sql`
- `assets/sql/indexes.sql`

Decisions to freeze:
- unified `repeat_calls` table versus one table per method
- foreign-key relationships
- import order
- which integrity checks are mandatory post-import

Possible problems:
- SQLite becomes a live workspace instead of a final artifact
- the schema overfits early convenience and becomes painful to evolve

Planned mitigation:
- keep SQLite as import-only
- keep raw TSVs as the canonical exchange boundary

### Work package 1.5: freeze reporting contracts

Outputs:
- `summary_by_taxon.tsv`
- `regression_input.tsv`
- ECharts JSON payload
- reproducible HTML report shell

Decisions to freeze:
- grouping keys
- generic codon-metric field semantics
- report-group derivation source
- how chart configs are serialized

Possible problems:
- charts need fields that are not present in the summaries
- report-group logic is hidden inside plotting code instead of documented upstream

Planned mitigation:
- define chart input tables before plotting starts
- make chart JSON a first-class output, not an implementation side effect

---

## Identifier policy to settle in this phase

The following must be finalized before coding:
- whether `taxon_id` is stored as NCBI taxid directly
- whether `genome_id`, `sequence_id`, and `protein_id` are deterministic internal IDs or preserved accessions
- how `call_id` is generated and whether it must be reproducible across reruns with the same inputs

Recommended direction:
- keep `taxon_id` as NCBI taxid when available
- use internal deterministic IDs for genome/sequence/protein/call rows
- preserve source accessions in separate columns or metadata

Possible problems:
- fragile source IDs leak into relational joins
- internal IDs become non-deterministic if generated from file order only

Planned mitigation:
- derive IDs from stable biological/source keys and documented normalization rules

---

## Validation plan to define now

### Structural validation

- headers exist
- required columns exist
- file names are canonical
- numeric columns parse correctly

### Relational validation

- every protein row points to a valid genome
- every call row points to a valid protein
- every linked sequence row is reachable
- every taxon referenced in genomes or calls exists in `taxonomy.tsv`

### Scientific sanity validation

- no negative lengths
- no purity outside `[0, 1]`
- no `start > end`
- `repeat_count + non_repeat_count = length`

### Reporting validation

- summary counts reconcile with source calls
- regression counts reconcile with grouped summaries
- chart JSON can be generated from finalized report tables alone

Possible problems:
- validation remains a prose idea and is not represented in outputs

Planned mitigation:
- define a future `validation_report.json` artifact in the implementation plan even if it is not coded yet

---

## Files expected to be finalized in this phase

- `docs/contracts.md`
- `assets/sql/schema.sql`
- `assets/sql/indexes.sql`
- `docs/implementation-plan.md`

Optional if needed:
- `docs/validation.md`

---

## Exit criteria

Phase 1 is done when:
- every stage has a named input/output contract
- all required columns are explicit
- all major IDs have a policy
- database ownership is documented
- reporting inputs are defined before plotting code exists

---

## Reviewer checklist

Before approving Phase 1, confirm:
- the acquisition manifest is expressive enough for real NCBI retrieval
- no important semantics are hidden in filenames
- the call schema is truly method-compatible
- the SQLite schema reflects contracts rather than implementation convenience

---

## Phase 1 status

Settled defaults:
1. `taxonomy.tsv` should materialize the lineage tree as explicit rows linked by `parent_taxon_id`.
2. `summary_by_taxon.tsv` is taxon-level only in v1.
3. the report layer serializes one combined `echarts_options.json` keyed by chart name.
