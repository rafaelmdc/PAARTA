# Phase 2 Decision Register

## Purpose

This document records the settled v1 defaults for the scientific core.

It is the implementation gate for Phase 3.
If a future change needs different behavior, the change should update this document and the relevant contract docs explicitly.

---

## 2.1 Acquisition normalization

Settled defaults:
- assemblies are enumerated globally from NCBI metadata before any heavy download starts
- v1 uses `RefSeq only` for assembly source policy
- v1 does not download raw genomic FASTA
- v1 downloads annotation-focused package contents:
  - `cds`
  - `gff3`
  - `seq-report`
- the fixed selection manifest is written before execution batches are derived
- large runs are processed in bounded batches rather than one monolithic job

Why this is the default:
- it keeps the trusted source inside RefSeq
- it reduces download volume
- it makes CDS the single nucleotide source of truth for translation and codon extraction
- it lowers retry and rate-limit risk for large runs

---

## 2.2 Taxonomy integration

Settled defaults:
- `taxon-weaver` is the canonical taxonomy dependency
- deterministic exact resolution is authoritative
- fuzzy or transformed matches are not auto-accepted
- review-required requests are written to `taxonomy_review_queue.tsv`
- runs continue automatically only for deterministic rows
- lineage enrichment is required for downstream grouping and reporting
- taxonomy build metadata is recorded per run

Why this is the default:
- taxonomy is a scientific dependency, not a cosmetic label layer
- silent taxon coercion would make the pipeline scientifically untrustworthy

---

## 2.3 Isoform selection and sequence linkage

Settled defaults:
- `genomic.gff` is the primary authority for gene, transcript, and CDS relationships
- package metadata is secondary
- CDS FASTA deflines are a documented fallback only
- file-order pairing is never allowed
- one isoform is retained per gene per genome
- the retained isoform is the one with the longest translated protein sequence
- ties are broken lexicographically by the derived `protein_id`
- if `gene_symbol` is absent, grouping falls back to a stable transcript- or sequence-derived key

Translation-driven canonical protein policy:
- retained CDS records are translated locally
- translated proteins are the canonical amino-acid input for detection
- external protein FASTA is not the preferred scientific source in v1
- external protein FASTA may still exist as a local smoke-test override path

Why this is the default:
- one nucleotide source of truth is cleaner than reconciling CDS and provided protein products
- longest-protein-per-gene is deterministic and easy to audit

---

## 2.4 CDS translation acceptance rules

Settled defaults:
- CDS translation happens only after normalization and isoform selection
- translation table comes from annotation metadata when available
- when no translation table is available, default to NCBI translation table `1`
- a terminal stop codon may be removed before final protein derivation
- after terminal-stop handling, the CDS length must be divisible by `3`
- CDS with internal stop codons are rejected
- CDS with unsupported ambiguity that would yield unresolved amino acids are rejected
- CDS marked partial in a way that prevents confident full translation are rejected

Rejection policy:
- rejected CDS records do not produce canonical protein rows
- rejected CDS records are excluded from protein-based detection
- rejection reasons are recorded in `normalization_warnings.tsv`

Recommended warning codes:
- `unresolved_linkage`
- `partial_cds`
- `non_triplet_length`
- `internal_stop`
- `unsupported_ambiguity`
- `unknown_translation_table`

Why this is the default:
- conservative exclusion is safer than mixing multiple amino-acid sources or guessing translation intent

---

## 2.5 Pure detection

Settled defaults:
- a target `repeat_residue` is required
- default `min_repeat_count = 6`
- any non-target residue breaks the tract
- report the maximal tract under those rules
- trim leading and trailing non-target residues from the final tract

Interpretation note:
- pure calls are contiguous runs only, not interrupted tracts

---

## 2.6 Threshold detection

Settled defaults:
- a target `repeat_residue` is required
- default `window_size = 8`
- default `min_target_count = 6`
- any window meeting that threshold is a qualifying seed
- overlapping or directly adjacent qualifying windows are merged
- the final tract is trimmed to remove leading and trailing non-target residues

Interpretation note:
- threshold exists to recover tracts with denser impurity than the pure method allows

---

## 2.7 Similarity-based detection

Settled default:
- removed from the current v1 baseline

Why this is the default:
- current implementation and contracts are intentionally limited to `pure` and `threshold`
- any future similarity method should return only through a new explicit planning and contract pass

---

## 2.8 Codon extraction and repeat-feature rules

Settled defaults:
- amino-acid call coordinates are the only slicing coordinates used for codon extraction
- codon slicing uses the normalized CDS sequence as nucleotide source of truth
- if the retained amino-acid call exists but codon slicing fails, keep the amino-acid call and leave codon fields empty
- the first release remains residue-neutral even if codon sequence evidence exists
- codon metric fields stay empty in v1 unless a later contract explicitly enables a residue-specific metric
- non-target codons inside an interrupted tract are stored unchanged when codon extraction succeeds

Why this is the default:
- v1 is detection-first and residue-neutral
- codon-aware infrastructure is retained without forcing residue-specific reporting into the first release

---

## 2.9 Database import

Settled defaults:
- SQLite is a final assembly artifact
- validation happens before import
- structural validation failures are hard-fail conditions for the import step
- the import step does not silently skip invalid rows
- imports run inside transactions
- indexes are created after bulk import

Recommended import order:
1. `taxonomy`
2. `genomes`
3. `sequences`
4. `proteins`
5. `run_params`
6. `repeat_calls`

Why this is the default:
- the database must assemble validated outputs, not repair scientific mistakes

---

## 2.10 Summary exports

Settled defaults:
- `summary_by_taxon.tsv` groups by:
  - `method`
  - `repeat_residue`
  - `taxon_id`
  - `taxon_name`
- `regression_input.tsv` groups by:
  - `method`
  - `repeat_residue`
  - `group_label`
  - `repeat_length`
- in v1, `group_label` mirrors the direct taxon grouping rather than a curated macro-group
- low-observation groups are retained rather than filtered out upstream
- codon-metric columns are omitted or left empty in the residue-neutral first release

Why this is the default:
- taxon-direct grouping is reproducible and does not encode subjective biology into v1

---

## 2.11 ECharts boundary

Settled defaults:
- chart generation is downstream only
- chart inputs come from finalized call tables, validated summaries, or derived reporting tables
- the front end must not re-derive biological groupings or call boundaries
- chart options are serialized as inspectable JSON
- the HTML report is a rendering shell, not a scientific logic layer

---

## 2.12 Contamination policy

Settled defaults:
- contamination checking remains a documented note-only step in v1
- contamination notes may appear in provenance or warning artifacts
- contamination signals do not automatically delete or hard-fail otherwise valid deterministic rows in v1
- a future dedicated contamination-validation step may harden this behavior later

Why this is the default:
- contamination handling was present historically, but it should not block the first clean rebuild before the rest of the scientific core is validated

---

## 2.13 Additional settled operational policies

Assembly category fallback within RefSeq:
- default policy is `reference preferred, representative allowed`
- if a suitable RefSeq reference assembly exists, select it first
- if no suitable RefSeq reference assembly exists, a RefSeq representative assembly may be selected with an explicit `selection_reason`

Missing annotation policy:
- assemblies lacking the CDS/GFF annotation needed for v1 are not processed automatically
- they are recorded for review and excluded from automatic normalization/detection

Local cache policy:
- reusable external caches are preferred for raw downloads and taxonomy DBs
- project-local cache paths remain acceptable for small or self-contained runs
- cache location should be configurable, not hard-coded into biological tables
