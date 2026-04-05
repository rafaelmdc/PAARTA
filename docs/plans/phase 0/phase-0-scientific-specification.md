# Phase 0 Plan: Scientific Specification

## Objective

Lock the scientific meaning of the rebuild before any implementation starts.

This phase is complete when the project can be described without referring to:
- old code structure
- implicit habits from the original project
- undocumented assumptions about NCBI records

---

## What this phase must answer

### Scope

- Is v1 residue-agnostic across homorepeats in both detection and the first reporting release?
- Is the biological scope taxon-agnostic and configured by taxon name or taxid?
- Are local inputs a testing/development mode only, or a supported scientific mode?

### Comparability

- Which outputs must remain comparable to the old project?
- Which historical quirks are explicitly allowed to change?
- What counts as a scientifically meaningful difference versus a workflow artifact?

### Detection intent

- What does each method mean conceptually, independent of implementation?
- Which impurities or interruptions are biologically relevant enough to keep in v1?
- What is the role of the BLAST-based method: sensitivity extension, divergence recovery, or both?

### Reporting intent

- Which summaries are mandatory for v1?
- Which figures are mandatory for the first ECharts rebuild?
- Which analysis questions from the dissertation remain in scope?

---

## Planned work packages

### Work package 0.1: freeze v1 scope

Docs to update:
- `docs/architecture.md`
- `docs/methods.md`
- `docs/roadmap.md` only if scope wording needs correction

Deliverables:
- explicit statement that v1 supports generic homorepeat detection
- explicit statement that the first reporting release remains residue-neutral
- explicit statement that residue-specific downstream analyses are deferred from the first release
- explicit statement that acquisition starts from NCBI Datasets plus local test mode
- explicit statement that annotation/domain enrichment is deferred

Possible problems:
- the repository quietly grows into a general repeat-analysis framework too early
- acquisition scope remains vague enough that later contracts branch in incompatible ways

Planned mitigation:
- keep future extensions listed separately from v1 requirements
- mark unsupported-but-planned areas as deferred rather than half-included

### Work package 0.2: freeze taxonomy intent

Docs to update:
- `docs/methods.md`
- new acquisition planning doc

Decisions to freeze:
- `taxon-weaver` is the canonical taxonomy dependency
- deterministic resolution is authoritative
- fuzzy suggestions are review-only
- lineage enrichment is required for downstream grouping/reporting

Possible problems:
- taxonomy is treated as a cosmetic annotation instead of a scientific dependency
- fuzzy name resolution silently changes target taxa

Planned mitigation:
- require that resolution status and warnings are recorded
- separate “resolved” from “suggested” from “unresolved” states in the plan

### Work package 0.3: freeze the expected output family

Needed outputs to list explicitly:
- canonical metadata tables
- method-specific call tables with shared schema
- integrated SQLite database
- summary tables
- regression input tables
- ECharts-ready reporting bundle

Possible problems:
- reporting needs emerge after implementation and force schema churn
- “core output” versus “supplementary output” remains ambiguous

Planned mitigation:
- define a short mandatory output set for v1
- move optional exports to a later phase list

### Work package 0.4: freeze non-goals

Non-goals to state clearly:
- full annotation enrichment
- web application features beyond reproducible HTML/JSON reporting
- aggressive performance tuning before validation
- custom downstream figure suites for every residue in the first release

Possible problems:
- implementation effort leaks into domain mapping, UI, or backend generalization

Planned mitigation:
- add an explicit “not in v1” section to planning docs and treat it as binding

---

## Artifacts to produce or refine

- `docs/methods.md`
- `docs/implementation-plan.md`
- `docs/plans/ncbi-acquisition-taxon-weaver.md`

Optional clarifying artifact if needed:
- `docs/figures.md` for the exact first reporting scope

---

## Exit criteria

Phase 0 is done when all of the following are true:
- the scientific scope of v1 fits in one page without code references
- the acquisition source and taxonomy dependency are explicit
- the three methods are conceptually distinguished
- mandatory outputs are named
- deferred topics are named and excluded

---

## Reviewer checklist

Before approving Phase 0, confirm:
- the target dataset definition is correct
- the taxonomy behavior is conservative enough
- the intended figures/tables still reflect the actual scientific questions
- nothing important from the old project remains only in the PDF and not in the docs

---

## Open questions requiring user decision

No additional Phase 0 decisions are currently blocking the documentation baseline.
