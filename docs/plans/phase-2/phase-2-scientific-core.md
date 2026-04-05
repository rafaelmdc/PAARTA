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

Phase 2 implementation-gating references:
- [phase-2/decision-register.md](./phase-2/decision-register.md)
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

---

## Planned work packages

### Work package 2.1: acquisition normalization logic

This work package converts raw retrieval artifacts into canonical workflow inputs.

Planned scope:
- enumerate NCBI candidate assemblies
- download selected data packages
- retain raw package provenance
- extract normalized CDS files and derive translated proteins
- emit canonical metadata tables

Detailed acquisition plan:
- [ncbi-acquisition-taxon-weaver.md](./ncbi-acquisition-taxon-weaver.md)

Possible problems:
- package layouts differ across assemblies or over time
- CDS files are missing, partial, or inconsistently annotated
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
- emit fuzzy or otherwise review-required resolutions into a review queue artifact

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
- use GFF-backed joins by default to connect genes, transcripts, and CDS records
- derive canonical proteins by translating retained CDS records
- allow metadata-backed or FASTA-backed linkage only as an explicit degraded fallback
- emit unresolved-linkage or translation warnings when protein-based detection will be impossible

Possible problems:
- eukaryotic annotations are inconsistent across assemblies
- some records have CDS without clean transcript or gene identifiers
- the “longest isoform” rule may drift from old project behavior
- fallback sources disagree with GFF-backed relationships or translation expectations

Planned mitigation:
- make the selection rule deterministic and documented
- preserve enough source identifiers to audit unexpected choices
- include a later validation task comparing a representative subset to the old project
- when sources disagree, prefer GFF and record the disagreement instead of reconciling heuristically

### Work package 2.4: pure detection definition

Settled defaults:
- default `min_repeat_count = 6`
- keep only contiguous target runs
- trim leading and trailing non-target residues from the final tract

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

Possible problems:
- the method becomes too permissive and overlaps conceptually with threshold detection
- small implementation choices materially change counts

Planned mitigation:
- specify the method with worked examples before coding
- define edge cases explicitly: sequence edges, interruption rejection, adjacent tracts

### Work package 2.5: threshold detection definition

Settled defaults:
- default `window_size = 8`
- default `min_target_count = 6`
- every qualifying sliding window is threshold-positive
- merge overlapping or directly adjacent qualifying windows

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

Possible problems:
- different extension rules produce materially different tract boundaries
- the default threshold becomes embedded everywhere and hard to vary later

Planned mitigation:
- freeze one default operational rule for v1
- require all parameters to be recorded in `run_params.tsv`

### Work package 2.6: BLAST-based detection definition

Settled defaults:
- backend is selected explicitly by configuration
- accepted production external backend is `diamond blastp`
- deterministic fallback remains available during early validation
- default fallback template length is `10`
- fallback scoring is `+2` for target residues and `-1` for non-target residues

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

Possible problems:
- the method is underspecified and cannot be validated
- BLAST behavior becomes environment-dependent
- fallback behavior is confused with true BLAST behavior

Planned mitigation:
- document the accepted production backend (`diamond blastp`) and the allowed temporary fallback separately
- record backend type in parameters or metadata
- define one validation set specifically for BLAST-like edge cases

### Work package 2.7: codon extraction and repeat feature logic

Settled defaults:
- CDS translation is conservative and happens before detection
- CDS records that cannot be translated confidently are excluded from protein-based detection
- codon metric fields remain empty in the residue-neutral first release
- non-target codons inside retained interrupted tracts are preserved unchanged when extraction succeeds

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

Possible problems:
- translated proteins diverge from intended annotation because translation rules are underspecified
- off-by-one coordinate bugs corrupt codon extraction silently
- legacy residue-specific codon assumptions leak into the residue-agnostic core

Planned mitigation:
- define CDS-to-protein translation rules before detection starts
- define amino-acid coordinates as the single source for codon slicing
- exclude records that fail conservative translation validation from protein-based detection rather than mixing sources
- defer to empty codon output on slicing failure rather than guessing

### Work package 2.8: database import logic

Settled defaults:
- validate before import
- hard-fail on structural import errors
- import inside transactions
- build indexes after bulk load

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)

Possible problems:
- invalid rows are partially imported
- SQLite import logic starts doing scientific correction instead of assembly

Planned mitigation:
- validate before import
- treat SQLite as a sink, not a repair layer

### Work package 2.9: summary export logic

Settled defaults:
- summary exports group directly by taxon in v1
- `group_label` mirrors the direct taxon grouping
- codon metric fields remain empty or omitted in the residue-neutral first release
- low-observation groups are retained rather than filtered upstream

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)

Possible problems:
- reporting code starts inventing biological groupings not present upstream
- missing codon data biases aggregated means

Planned mitigation:
- document aggregation semantics and missing-data behavior now
- keep group derivation in explicit helper logic, not chart code
- keep the first reporting release residue-neutral even if codon-aware infrastructure exists underneath

### Work package 2.10: ECharts boundary

Settled defaults:
- chart inputs come from finalized tables only
- chart configs are serialized as inspectable JSON
- the HTML report is a rendering shell, not the location of scientific logic

Reference:
- [phase-2/decision-register.md](./phase-2/decision-register.md)

Possible problems:
- plotting code reimplements grouping/filtering logic
- chart output becomes difficult to diff or test

Planned mitigation:
- separate data preparation from rendering
- keep chart JSON as a first-class artifact

---

## Required written examples before implementation

Implemented here:
- [phase-2/worked-examples.md](./phase-2/worked-examples.md)

---

## Files expected to be finalized in this phase

- `docs/methods.md`
- `docs/plans/ncbi-acquisition-taxon-weaver.md`
- `docs/plans/phase-2/decision-register.md`
- `docs/plans/phase-2/worked-examples.md`

---

## Exit criteria

Phase 2 is done when:
- every major scientific operation has a written operational definition
- major edge cases are named
- taxonomy behavior is conservative and explicit
- the report layer has documented upstream inputs
- implementation could start without inventing new method rules

Current status:
- the required decision register exists
- the required worked examples exist
- contamination policy is settled as note-only for v1

---

## Reviewer checklist

Before approving Phase 2, confirm:
- acquisition and taxonomy rules are specific enough to code
- isoform policy is scientifically acceptable
- method boundaries are distinct and testable
- codon extraction failure behavior is conservative
- reporting depends on finalized tables only

---

## Phase 2 status

No remaining Phase 2 blockers are recorded in the scientific-core docs.
