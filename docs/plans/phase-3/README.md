# Phase 3 Reference

This folder contains the implementation-oriented documents for Phase 3.

Contents:
- `../../acquisition.md`
  The current implemented acquisition behavior, including default ignore/exclude rules and live-smoke status.
- `acquisition-implementation.md`
  The explicit download, rehydration, normalization, translation, and batch-merge plan for Phase 3.
- `cli-contracts.md`
  Script-by-script operational contracts for Phase 3 CLIs.
- `artifact-layout.md`
  The default run tree, file placement, and merge rules for standalone Phase 3 runs.
- `support-artifact-schemas.md`
  Explicit schemas for Phase 3 support artifacts such as batch plans, download manifests, and warning tables.
- `implementation-sequence.md`
  The vertical implementation order for the standalone scientific core.
- `implementation-checklists.md`
  Completion checklists for each implementation slice.
- `module-map.md`
  The planned script, library, and artifact layout for Phase 3.
- `acquisition-cli-flags.md`
  Exact initial CLI flag specifications for the first acquisition-side scripts.
- `validation-strategy.md`
  The test and acceptance strategy for the standalone implementation before Nextflow wrapping.

These documents assume that:
- Phase 0 scope is frozen
- Phase 1 contracts are frozen
- Phase 2 scientific defaults are frozen
- Docker is the current reproducible runtime baseline for external tool dependencies

Current implementation status:
- acquisition, pure detection, threshold detection, codon extraction, SQLite assembly, and summary/report-prep are implemented and live-smoked
- similarity-based detection has been removed from the current v1 codebase and planning baseline

The Phase 2 implementation gate remains:
- [../phase-2/decision-register.md](../phase-2/decision-register.md)
- [../phase-2/worked-examples.md](../phase-2/worked-examples.md)

Phase 3 should not invent new biological rules.
If implementation exposes a real gap, the fix belongs in docs first, then in code.
