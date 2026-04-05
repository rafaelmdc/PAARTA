# Roadmap

## Goal

Rebuild the homorepeat pipeline from scratch as a modular Nextflow project, using the current project only as a source of scientific logic, method definitions, and output goals.

This is not a code migration.

It is a clean reimplementation based on:
- the current biological questions
- the current detection strategies
- the current data model
- the current downstream analysis goals

The priority is to preserve scientific intent while replacing the implementation with a simpler, cleaner, and more reproducible workflow.

---

## Core intent to preserve

The rebuilt workflow should preserve the main scientific structure of the current project:

1. acquire sequence data and metadata
2. enrich or validate taxonomic context
3. detect homorepeat regions using multiple methods
4. store standardized outputs in a structured database
5. generate downstream summaries and figures

The implementation may change completely, but this scientific flow should remain stable.

---

## Guiding principles

1. Rebuild from scratch, do not imitate old code structure.
2. Preserve method meaning, not implementation details.
3. Define contracts early.
4. Keep Nextflow responsible for orchestration only.
5. Keep scientific logic in small scripts or modules.
6. Prefer inspectable intermediate files over hidden state.
7. Optimize for clarity first, performance second.

---

## Phase 0 — Define the scientific specification

### Objective
Write down exactly what the new pipeline is supposed to do, independent of the old implementation.

### Tasks
- define the biological scope of the pipeline
- define which repeat types are in scope for v1
- define the three detection strategies conceptually
- define the required metadata and outputs
- define which analyses and figures are in scope
- define what must remain comparable to the current project
- define what can be dropped or simplified

### Deliverables
- `docs/architecture.md`
- `docs/contracts.md`
- `docs/methods.md` if needed

### Exit criteria
- the pipeline behavior is specified clearly enough to implement without relying on old code

---

## Phase 1 — Define the data and output model

### Objective
Establish the canonical data contracts before implementation begins.

### Tasks
- define metadata tables
- define sequence and protein input contracts
- define the shared detection-call schema
- define database tables
- define naming conventions
- define internal identifier policy
- define summary-table outputs
- define validation rules

### Deliverables
- `docs/contracts.md`
- initial SQL schema
- naming rules for outputs

### Exit criteria
- every major workflow stage has a documented input/output contract

---

## Phase 2 — Define the scientific core

### Objective
Fully define the core biological operations before implementation begins, so the workflow is built from explicit method decisions rather than from ad hoc coding.

### Tasks
- define sequence preparation logic
- define taxonomy integration logic
- decide whether contamination checking remains in scope
- define the pure detection method
- define the threshold detection method
- define the BLAST-based detection method
- define codon extraction and repeat feature calculation rules
- define database import behavior
- define summary export behavior
- define plotting responsibilities and boundaries

### Deliverables
- written method definitions and operational decisions
- edge-case notes and worked examples where needed
- approved implementation plans for acquisition, detection, database, and reporting boundaries

### Exit criteria
- each major scientific operation is explicitly defined before implementation
- implementation can begin without inventing new method rules or fallback policies

---

## Phase 3 — Implement the scientific core as standalone logic

### Objective
Implement the core biological and data-processing operations as standalone scripts or modules before wrapping them in Nextflow.

### Tasks
- implement sequence preparation logic
- implement taxonomy integration logic
- implement contamination-check logic if retained
- implement pure detection
- implement threshold detection
- implement BLAST-based detection
- implement codon extraction and repeat feature calculation
- implement database import logic
- implement summary export logic
- implement plotting preparation logic

### Deliverables
- working standalone scripts or modules
- reusable helper library code
- method-level validation fixtures or examples where appropriate

### Exit criteria
- each major scientific operation works independently of the workflow engine
- the standalone logic can be tested without Nextflow

---

## Phase 4 — Build the minimal Nextflow workflow

### Objective
Create a clean end-to-end workflow around the standalone logic.

### Tasks
- create `main.nf`
- create execution configs
- create subworkflows for acquisition, detection, database, and reporting
- wrap standalone logic in small DSL2 modules
- define profiles for local execution
- validate resume behavior and output stability

### Deliverables
- `main.nf`
- `nextflow.config`
- `conf/base.config`
- `conf/local.config`

### Exit criteria
- the new workflow runs end-to-end on a small dataset

---

## Phase 5 — Validate scientific behavior

### Objective
Check that the new implementation behaves in line with the intended scientific model.

### Tasks
- validate pure-method behavior on representative examples
- validate threshold-method behavior on representative examples
- validate BLAST-method behavior on representative examples
- validate codon extraction logic
- validate repeat length and purity calculations
- validate database row relationships
- validate summary statistics
- compare major trends against expected biological patterns

### Deliverables
- validation notes
- smoke tests
- regression-style example cases

### Exit criteria
- the rebuilt workflow is scientifically trustworthy for its intended scope

---

## Phase 6 — Rebuild downstream outputs

### Objective
Recreate the useful outputs of the project in a cleaner and more reproducible way.

### Tasks
- build summary tables by taxon and method
- build regression input tables
- generate key plots
- generate supplementary exports
- make figure generation independent from raw detection code

### Deliverables
- reporting scripts
- figure outputs
- table exports

### Exit criteria
- the workflow produces the main outputs needed for analysis and writing

---

## Phase 7 — Improve usability and reproducibility

### Objective
Make the project easy to run, inspect, and maintain.

### Tasks
- add example parameter files
- add clear run instructions
- add container or environment definitions
- add smoke-test datasets
- add structured output directories
- add help text and examples
- simplify configuration where possible

### Deliverables
- improved README
- example params
- environment/container files
- test data

### Exit criteria
- a new user can understand the project structure and run it without reading internal implementation details

---

## Phase 8 — Future extensions

### Objective
Prepare the project for later expansion without blocking v1.

### Possible extensions
- support additional homorepeat types beyond polyQ
- add functional annotation integration
- add protein domain context
- add richer database exports
- add better comparative analysis layers
- add support for alternative databases or backends if needed

### Rule
These should remain future extensions unless they are required for the first scientifically valid release.

---

## Priorities

When tradeoffs appear, prioritize in this order:

1. scientific correctness
2. contract clarity
3. reproducibility
4. debuggability
5. maintainability
6. performance
7. convenience

---

## Non-goals for v1

The first rebuild does not need to:
- support every possible repeat type
- perfectly optimize runtime
- reproduce every historical implementation quirk
- include full annotation enrichment
- include web or UI layers
- overgeneralize beyond the current scientific scope

---

## Definition of done for v1

Version 1 of the rebuild is complete when:

- the pipeline is implemented cleanly in Nextflow
- the three detection methods exist and share a common contract
- outputs are standardized and inspectable
- SQLite is built from flat intermediate files
- summary tables and key figures are reproducible
- the architecture and contracts are documented
- the workflow is scientifically valid for the intended use case
