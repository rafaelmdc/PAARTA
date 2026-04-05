# Phase 3 Acquisition CLI Flags

## Purpose

This document freezes the initial CLI flag specifications for the first acquisition-side Phase 3 scripts.

The goal is to stop implementation from inventing incompatible flag names and calling conventions across the first coding slices.

These are the highest-priority CLIs because they define the front door of the standalone implementation.

---

## Shared conventions

### Required conventions

- long-form flags only in docs and examples
- kebab-case flag names
- explicit `--outdir`
- explicit input path flags instead of positional ambiguity
- explicit `--log-file` supported when the script performs meaningful IO or remote work

### Output convention

Unless otherwise stated, outputs are written under `--outdir` using the canonical filenames defined in the relevant contract docs.

---

## `bin/resolve_taxa.py`

### Purpose

Resolve user taxon requests with `taxon-weaver`.

### Required flags

- `--requested-taxa`
  Path to `requested_taxa.tsv`.
- `--taxonomy-db`
  Path to the local `taxon-weaver` SQLite taxonomy DB.
- `--outdir`
  Output directory.

### Optional flags

- `--log-file`
- `--fail-on-review-queue`
  Optional stricter mode for future use; should default to `false` in v1.

### Required outputs

- `resolved_requests.tsv`
- `taxonomy_review_queue.tsv`

### Example shape

```bash
bin/resolve_taxa.py \
  --requested-taxa runs/run_001/planning/requested_taxa.tsv \
  --taxonomy-db cache/taxonomy/ncbi_taxonomy.sqlite \
  --outdir runs/run_001/planning
```

---

## `bin/enumerate_assemblies.py`

### Purpose

Enumerate RefSeq candidate assemblies for deterministic requests.

### Required flags

- `--resolved-requests`
  Path to `resolved_requests.tsv`.
- `--outdir`
  Output directory.

### Optional flags

- `--log-file`
- `--api-key`
  NCBI API key when available.
- `--include-raw-jsonl`
  When true, also emit `assembly_inventory.jsonl`.

### Required outputs

- `assembly_inventory.tsv`

### Optional outputs

- `assembly_inventory.jsonl`

### Example shape

```bash
bin/enumerate_assemblies.py \
  --resolved-requests runs/run_001/planning/resolved_requests.tsv \
  --outdir runs/run_001/planning \
  --api-key "$NCBI_API_KEY" \
  --include-raw-jsonl
```

---

## `bin/select_assemblies.py`

### Purpose

Apply the settled RefSeq selection policy.

### Required flags

- `--assembly-inventory`
  Path to `assembly_inventory.tsv`.
- `--outdir`
  Output directory.

### Optional flags

- `--log-file`
- `--allow-refseq-representative`
  Should default to `true` in v1.
- `--require-annotation`
  Should default to `true` in v1.

### Required outputs

- `selected_assemblies.tsv`
- `selected_accessions.txt`
- `excluded_assemblies.tsv`

### Example shape

```bash
bin/select_assemblies.py \
  --assembly-inventory runs/run_001/planning/assembly_inventory.tsv \
  --outdir runs/run_001/planning \
  --allow-refseq-representative \
  --require-annotation
```

---

## `bin/plan_batches.py`

### Purpose

Derive bounded execution batches from the frozen selection manifest.

### Required flags

- `--selected-assemblies`
  Path to `selected_assemblies.tsv`.
- `--outdir`
  Output directory.

### Optional flags

- `--log-file`
- `--target-batch-size`
  Default should be a conservative value in the `50-200` range.
- `--max-batches`
  Optional operational cap for manual control.

### Required outputs

- `selected_batches.tsv`

### Example shape

```bash
bin/plan_batches.py \
  --selected-assemblies runs/run_001/planning/selected_assemblies.tsv \
  --outdir runs/run_001/planning \
  --target-batch-size 100
```

---

## `bin/download_ncbi_packages.py`

### Purpose

Download and optionally rehydrate one execution batch.

### Required flags

- `--batch-manifest`
  Path to `selected_batches.tsv`.
- `--batch-id`
  Operational batch ID such as `batch_0001`.
- `--outdir`
  Batch-local raw output directory.

### Optional flags

- `--log-file`
- `--api-key`
- `--cache-dir`
- `--dehydrated`
  Force dehydrated mode.
- `--rehydrate`
  Explicitly run rehydration after download.
- `--rehydrate-workers`
  Conservative worker count for rehydration.

### Required outputs

- batch-local raw download artifact
- batch-local `download_manifest.tsv`

### Example shape

```bash
bin/download_ncbi_packages.py \
  --batch-manifest runs/run_001/planning/selected_batches.tsv \
  --batch-id batch_0001 \
  --outdir runs/run_001/batches/batch_0001/raw \
  --api-key "$NCBI_API_KEY" \
  --dehydrated \
  --rehydrate \
  --rehydrate-workers 4
```

---

## `bin/normalize_cds.py`

### Purpose

Normalize one batch-local package directory into canonical acquisition outputs.

### Required flags

- `--package-dir`
  Path to the batch-local rehydrated package directory.
- `--batch-id`
- `--outdir`
  Batch-local normalized output directory.

### Optional flags

- `--log-file`
- `--warning-out`
  Explicit warning path when not using the canonical filename under `--outdir`.

### Required outputs

- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- normalized `cds.fna`
- `normalization_warnings.tsv`

### Example shape

```bash
bin/normalize_cds.py \
  --package-dir runs/run_001/batches/batch_0001/raw/ncbi_package \
  --batch-id batch_0001 \
  --outdir runs/run_001/batches/batch_0001/normalized
```

---

## `bin/translate_cds.py`

### Purpose

Translate retained CDS rows into canonical protein inputs.

### Required flags

- `--sequences-tsv`
  Path to normalized `sequences.tsv`.
- `--cds-fasta`
  Path to normalized CDS FASTA.
- `--batch-id`
- `--outdir`
  Batch-local normalized output directory.

### Optional flags

- `--log-file`
- `--warning-out`

### Required outputs

- `proteins.tsv`
- normalized `proteins.faa`
- warning artifact update or append-safe equivalent

### Example shape

```bash
bin/translate_cds.py \
  --sequences-tsv runs/run_001/batches/batch_0001/normalized/sequences.tsv \
  --cds-fasta runs/run_001/batches/batch_0001/normalized/cds.fna \
  --batch-id batch_0001 \
  --outdir runs/run_001/batches/batch_0001/normalized
```

---

## `bin/merge_acquisition_batches.py`

### Purpose

Merge validated acquisition outputs across successful batches.

### Required flags

- `--batch-inputs`
  Repeated flag or manifest path describing successful batch normalized directories.
- `--outdir`
  Merged acquisition output directory.

### Optional flags

- `--log-file`
- `--strict-taxonomy-merge`
  Should default to `true`.

### Required outputs

- merged `genomes.tsv`
- merged `taxonomy.tsv`
- merged `sequences.tsv`
- merged `proteins.tsv`
- merged `download_manifest.tsv`
- merged `normalization_warnings.tsv`
- merged `acquisition_validation.json`

### Example shape

```bash
bin/merge_acquisition_batches.py \
  --batch-inputs runs/run_001/batches/batch_0001/normalized \
  --batch-inputs runs/run_001/batches/batch_0002/normalized \
  --outdir runs/run_001/merged/acquisition \
  --strict-taxonomy-merge
```

---

## v1 flag freeze rule

Before implementing any of the acquisition CLIs above:
- use these flag names unless there is a strong documented reason not to
- if a flag changes, update this doc before or with the code change

This is the point where implementation consistency starts, so these flags should not drift casually.
