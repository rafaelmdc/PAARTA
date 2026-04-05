# Phase 2 Plan: Scientific Core

## Objective

Freeze the operational biology and data-processing rules before implementation starts.

This phase answers:
- how data is normalized
- how taxonomy is resolved and enriched
- how one isoform per gene is chosen
- how each detection method works
- how codons are extracted
- how summaries are derived

If Phase 1 is “what the files mean”, Phase 2 is “what the steps do”.

---

## Planned work packages

### Work package 2.1: acquisition normalization logic

This work package converts raw retrieval artifacts into canonical workflow inputs.

Planned scope:
- enumerate NCBI candidate assemblies
- download selected data packages
- retain raw package provenance
- extract normalized protein/CDS files
- emit canonical metadata tables

Detailed acquisition plan:
- [ncbi-acquisition-taxon-weaver.md](./ncbi-acquisition-taxon-weaver.md)

Possible problems:
- package layouts differ across assemblies or over time
- annotated proteins exist but CDS files are missing or incomplete
- package parsing becomes dependent on fragile FASTA deflines

Planned mitigation:
- treat package manifest and assembly report as authoritative metadata
- make `genomic.gff` the default normalization authority for biological joins
- use package metadata second and FASTA deflines only as a documented fallback
- record degraded states explicitly instead of silently inventing links

### Work package 2.2: taxonomy integration logic

Planned behavior:
- use `taxon-weaver` to resolve user-supplied names and build local lineage context
- treat taxids returned by NCBI as authoritative identifiers when present
- use `taxon-weaver` lineage lookup to enrich `taxonomy.tsv`
- preserve status/warning information from taxonomy resolution

Possible problems:
- name-based requests resolve ambiguously
- lineage enrichment silently diverges from NCBI metadata if taxdump versions change
- fuzzy fallback is used as though it were deterministic

Planned mitigation:
- pin one taxonomy build per run
- record taxonomy build metadata in outputs
- require review for fuzzy or transformed matches

### Work package 2.3: isoform and sequence-linkage policy

Planned behavior:
- select one isoform per gene per genome
- prefer longest protein when multiple isoforms remain
- use GFF-backed joins by default to connect genes, transcripts, CDS, and proteins
- allow metadata-backed or FASTA-backed linkage only as an explicit degraded fallback
- emit unresolved-linkage warnings when codon extraction will be impossible

Possible problems:
- eukaryotic annotations are inconsistent across assemblies
- some records have proteins without clean transcript or gene identifiers
- the “longest isoform” rule may drift from old project behavior
- fallback sources disagree with GFF-backed relationships

Planned mitigation:
- make the selection rule deterministic and documented
- preserve enough source identifiers to audit unexpected choices
- include a later validation task comparing a representative subset to the old project
- when sources disagree, prefer GFF and record the disagreement instead of reconciling heuristically

### Work package 2.4: pure detection definition

Questions to freeze:
- minimum Q count
- how single-residue interruptions are handled
- whether adjacent qualifying segments are merged or kept separate
- whether termini are always trimmed to Q

Possible problems:
- the method becomes too permissive and overlaps conceptually with threshold detection
- small implementation choices materially change counts

Planned mitigation:
- specify the method with worked examples before coding
- define edge cases explicitly: leading interruptions, repeated single interruptions, adjacent tracts

### Work package 2.5: threshold detection definition

Questions to freeze:
- default window size and Q threshold
- extension rule after a qualifying window is found
- merge rule for overlapping windows
- purity threshold during extension

Possible problems:
- different extension rules produce materially different tract boundaries
- the default threshold becomes embedded everywhere and hard to vary later

Planned mitigation:
- freeze one default operational rule for v1
- require all parameters to be recorded in `run_params.tsv`

### Work package 2.6: BLAST-based detection definition

Questions to freeze:
- whether real `blastp` is mandatory in the first implementation
- what template is used
- how hits are merged
- what score field means in the shared schema

Possible problems:
- the method is underspecified and cannot be validated
- BLAST behavior becomes environment-dependent
- fallback behavior is confused with true BLAST behavior

Planned mitigation:
- document the preferred real-BLAST path and any allowed temporary fallback separately
- record backend type in parameters or metadata
- define one validation set specifically for BLAST-like edge cases

### Work package 2.7: codon extraction and repeat feature logic

Questions to freeze:
- what happens when translated CDS does not match the retained protein
- whether codon extraction is skipped or partially rescued
- how CAG ratio is computed for interrupted tracts
- whether non-Q codons inside a tract are stored unchanged

Possible problems:
- codon ratios are computed from invalid sequence alignments
- off-by-one coordinate bugs corrupt codon extraction silently

Planned mitigation:
- define amino-acid coordinates as the single source for codon slicing
- require translation cross-checks before codon extraction
- defer to empty codon output on mismatch rather than guessing

### Work package 2.8: database import logic

Questions to freeze:
- import order
- transaction boundaries
- index timing
- validation failures: warn, skip, or hard-fail

Possible problems:
- invalid rows are partially imported
- SQLite import logic starts doing scientific correction instead of assembly

Planned mitigation:
- validate before import
- treat SQLite as a sink, not a repair layer

### Work package 2.9: summary export logic

Questions to freeze:
- exact groupings for summary and regression tables
- macro-group source
- how mean CAG ratio is handled when codon data is missing
- whether low-observation groups are filtered upstream or only flagged

Possible problems:
- reporting code starts inventing biological groupings not present upstream
- missing codon data biases aggregated means

Planned mitigation:
- document aggregation semantics and missing-data behavior now
- keep group derivation in explicit helper logic, not chart code

### Work package 2.10: ECharts boundary

What to freeze now:
- chart inputs come from finalized summary/regression outputs only
- chart configs are serialized as inspectable JSON
- the HTML report is a rendering shell, not the location of scientific logic

Possible problems:
- plotting code reimplements grouping/filtering logic
- chart output becomes difficult to diff or test

Planned mitigation:
- separate data preparation from rendering
- keep chart JSON as a first-class artifact

---

## Required written examples before implementation

Before approving Phase 2, the docs should include at least:
- one pure-method worked example
- one threshold-method worked example
- one BLAST-method worked example
- one CDS/protein mismatch example and expected behavior
- one ambiguous taxonomy example and expected review behavior

---

## Files expected to be finalized in this phase

- `docs/methods.md`
- `docs/plans/ncbi-acquisition-taxon-weaver.md`
- optional edge-case note file if the examples become too long for `docs/methods.md`

---

## Exit criteria

Phase 2 is done when:
- every major scientific operation has a written operational definition
- major edge cases are named
- taxonomy behavior is conservative and explicit
- the report layer has documented upstream inputs
- implementation could start without inventing new method rules

---

## Reviewer checklist

Before approving Phase 2, confirm:
- acquisition and taxonomy rules are specific enough to code
- isoform policy is scientifically acceptable
- method boundaries are distinct and testable
- codon extraction failure behavior is conservative
- reporting depends on finalized tables only

---

## Open questions requiring user decision

1. Should unresolved CDS/protein mismatches drop the affected call entirely, or keep the amino-acid call with empty codon fields?
2. Is contamination checking a documented note-only step in v1, or a hard validation gate?
3. For BLAST, do you want the first implementation to wait for a real `blastp` path, or is a temporary documented fallback acceptable while validation is being built?
