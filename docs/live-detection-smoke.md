# Live Detection Smoke Check

## Purpose

This document defines the opt-in live detection smoke check for the current standalone Phase 3 implementation.

It exists because:
- the main live smoke now validates acquisition through summary/report-prep on one `pure` detection path
- `threshold` still needs a focused live check separate from the main acquisition smoke

This smoke check is not part of the default unit-test suite.

---

## Scope

The current detection smoke verifies, on top of an existing merged acquisition result:
1. `detect_threshold.py` runs on real acquired proteins and emits non-empty `threshold_calls.tsv`
2. `extract_repeat_codons.py` can enrich threshold calls conservatively
3. threshold call rows preserve the shared call schema and leave codon metric fields empty in v1

It does not currently test:
- taxonomy resolution
- live NCBI downloads
- SQLite assembly for threshold-specific outputs
- Nextflow orchestration

Those are already covered elsewhere or belong to later phases.

---

## Entry Point

Script:
- `scripts/smoke_live_detection.sh`

This script is intentionally separate from the main live smoke so the acquisition path stays bounded and the detection-specific validation remains focused.

---

## Required Environment

Required:
- Python
- one existing merged acquisition result containing:
  - `proteins.tsv`
  - `proteins.faa`
  - `sequences.tsv`
  - `cds.fna`

Optional:
- `PYTHON_BIN`
  Defaults to `python3`
- `HOMOREPEAT_SMOKE_REPEAT_RESIDUE`
  Defaults to `Q`
- `HOMOREPEAT_SMOKE_SOURCE_RUN_ROOT`
  Points to a previous `live_smoke_*` run root
- `HOMOREPEAT_SMOKE_SOURCE_ACQUISITION_DIR`
  Points directly to a merged acquisition directory
- `HOMOREPEAT_DETECTION_SMOKE_RUN_ID`
  Override the generated run ID. The default format is `live_detection_smoke_YYYY-MM-DD_HH-MM-SSZ`.
- `HOMOREPEAT_DETECTION_SMOKE_RUN_ROOT`
  Override the default run root

Default source resolution:
- if `HOMOREPEAT_SMOKE_SOURCE_ACQUISITION_DIR` is set, it is used directly
- otherwise, if `HOMOREPEAT_SMOKE_SOURCE_RUN_ROOT` is set, the script uses `<run_root>/merged/acquisition`
- otherwise, the script uses the latest `runs/live_smoke_*` directory under the repo root

---

## Run In Docker

If you built the detection image:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  homorepeat-detection:0.1 \
  bash scripts/smoke_live_detection.sh
```

To point the smoke at a specific acquisition run:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  -e HOMOREPEAT_SMOKE_SOURCE_RUN_ROOT=/work/runs/live_smoke_2026-04-05_20-10-51Z \
  homorepeat-detection:0.1 \
  bash scripts/smoke_live_detection.sh
```

---

## Success Criteria

The smoke check passes only if:
- `threshold_calls.tsv` is non-empty
- call rows remain structurally valid
- threshold parameters record the default sliding-window settings
- threshold codon-enriched outputs are non-empty
- at least one threshold call has a non-empty `codon_sequence`
- every non-empty `codon_sequence` has length `3 * length`
- `codon_metric_name` and `codon_metric_value` remain empty

Warnings are allowed.
Structural failure is not.

---

## Run Naming

By default the detection smoke writes runs under:

- `runs/live_detection_smoke_YYYY-MM-DD_HH-MM-SSZ`

It also writes:

- `run_started_at_utc.txt`
- `source_acquisition_dir.txt`

at the run root.

---

## Operational Notes

- this smoke reuses real acquired proteins rather than repeating NCBI download work
- `threshold` is currently the default live-validated secondary detection method
- the default `Q` target keeps the smoke aligned with the existing live acquisition reference case
- run this smoke intentionally after threshold changes, or before cutting a reproducibility milestone that claims live validation of all implemented detection methods
