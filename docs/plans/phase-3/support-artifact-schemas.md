# Phase 3 Support Artifact Schemas

## Purpose

This document freezes the schemas for supporting artifacts that are critical to Phase 3 implementation but are not yet fully defined in `docs/contracts.md`.

These artifacts are operationally important because they connect acquisition, batching, validation, and merge behavior.

If any of these schemas change later, implementation and merge logic must be updated explicitly.

---

## General rules

- all tabular artifacts are TSV with headers
- all JSON artifacts are UTF-8 JSON objects
- missing scalar values are empty fields unless otherwise specified
- booleans in TSV should be lowercase `true` or `false`
- every supporting artifact must be reproducible from the same inputs

---

## `selected_batches.tsv`

### Row unit

One row per selected assembly assigned to one execution batch.

### Required columns

- `batch_id`
- `request_id`
- `assembly_accession`
- `taxon_id`
- `batch_reason`

### Optional columns

- `resolved_name`
- `refseq_category`
- `assembly_level`
- `annotation_status`

### Rules

- every row in `selected_batches.tsv` must correspond to one row in `selected_assemblies.tsv`
- every selected assembly appears in exactly one batch
- `batch_id` is an operational identifier such as `batch_0001`
- `batch_reason` should explain the operational grouping choice, for example:
  - `single_small_taxon_batch`
  - `split_large_taxon_fixed_size`
  - `manual_override`

### Validation checks

- no duplicate `assembly_accession`
- every `batch_id` has at least one row
- every `assembly_accession` exists in `selected_assemblies.tsv`

---

## `download_manifest.tsv`

### Row unit

One row per selected assembly download attempt.

### Required columns

- `batch_id`
- `assembly_accession`
- `download_status`
- `package_mode`
- `download_path`

### Optional columns

- `rehydrated_path`
- `checksum`
- `file_size_bytes`
- `download_started_at`
- `download_finished_at`
- `notes`

### Allowed `download_status`

- `downloaded`
- `rehydrated`
- `failed`
- `skipped`

### Allowed `package_mode`

- `direct_zip`
- `dehydrated`

### Rules

- one row per attempted accession per batch
- `download_path` must point to the raw downloaded package or dehydrated directory
- `rehydrated_path` is required when `download_status=rehydrated`
- failed rows must still exist and include an explanatory `notes` value

### Validation checks

- no selected accession is missing from the manifest for a completed batch
- `download_status=rehydrated` implies non-empty `rehydrated_path`
- no successful row has an empty `download_path`

---

## `normalization_warnings.tsv`

### Row unit

One warning event affecting one biological record or one package-level normalization outcome.

### Required columns

- `warning_code`
- `warning_scope`
- `warning_message`

### Optional columns

- `batch_id`
- `genome_id`
- `sequence_id`
- `protein_id`
- `assembly_accession`
- `source_file`
- `source_record_id`

### Allowed `warning_scope`

- `package`
- `genome`
- `sequence`
- `protein`
- `call`

### Recommended warning codes

- `unresolved_linkage`
- `partial_cds`
- `non_triplet_length`
- `internal_stop`
- `unsupported_ambiguity`
- `unknown_translation_table`
- `gff_fasta_disagreement`
- `missing_annotation_component`
- `codon_slice_failed`

### Rules

- warnings are non-fatal unless the owning CLI also exits with a hard-fail code
- warning rows should identify the narrowest applicable scope
- `warning_message` should be human-readable, concise, and stable enough to diff across runs

### Validation checks

- `warning_code` is non-empty
- `warning_scope` is one of the allowed values
- at least one identifying column beyond the generic message is present when the scope is narrower than `package`

---

## `acquisition_validation.json`

### Object purpose

Summarize the validation result for one batch or one merged acquisition result.

### Required top-level keys

- `status`
- `scope`
- `counts`
- `checks`

### Allowed `status`

- `pass`
- `warn`
- `fail`

### Allowed `scope`

- `batch`
- `merged`

### Required `counts` keys

- `n_selected_assemblies`
- `n_downloaded_packages`
- `n_genomes`
- `n_sequences`
- `n_proteins`
- `n_warning_rows`

### Required `checks` keys

- `all_selected_accessions_accounted_for`
- `all_genomes_have_taxids`
- `all_proteins_belong_to_genomes`
- `all_retained_proteins_trace_to_cds`

### Optional keys

- `batch_id`
- `failed_accessions`
- `warning_summary`
- `notes`

### Rules

- `checks` values are booleans
- `failed_accessions` should be an array when present
- `warning_summary` should be an object keyed by warning code when present

---

## `taxonomy_review_queue.tsv`

### Row unit

One request row requiring manual review before deterministic continuation.

### Required columns

- `request_id`
- `original_input`
- `normalized_input`
- `resolution_status`
- `review_required`
- `warnings`
- `taxonomy_build_version`

### Optional columns

- `matched_taxid`
- `matched_name`
- `matched_rank`

### Rules

- `review_required` must be `true` for every row in this file
- `resolution_status` should usually be `review_required`
- rows in this file must also be representable in `resolved_requests.tsv`

---

## `excluded_assemblies.tsv`

### Row unit

One candidate assembly that was considered but not selected.

### Required columns

- `request_id`
- `assembly_accession`
- `taxon_id`
- `exclusion_reason`

### Optional columns

- `resolved_name`
- `refseq_category`
- `assembly_level`
- `annotation_status`

### Rules

- `exclusion_reason` should be stable and explicit, for example:
  - `not_preferred_vs_reference`
  - `missing_required_annotation`
  - `not_refseq`
  - `not_current_accession`

---

## Relationship to `docs/contracts.md`

These schemas are operational extensions of the main contracts.

If an artifact here becomes part of the long-term public contract surface, it should be promoted into:
- [contracts.md](/home/rafael/Documents/GitHub/homorepeat/docs/contracts.md)

Until then, this file is the implementation reference for these support artifacts.
