# Architecture

## Overview

HomoRepeat is a modular Nextflow-based pipeline for detecting and analyzing homorepeat regions, with an initial focus on polyglutamine (polyQ) tracts.

The project is intentionally split into two layers:

1. **Workflow orchestration**
2. **Scientific logic**

Nextflow is responsible for orchestration, execution, caching, profiles, and reproducibility.

Python scripts and small reusable libraries are responsible for:
- sequence processing
- homorepeat detection
- codon extraction
- taxonomy-aware data shaping
- database assembly
- reporting table generation
- plotting

The goal is to keep the workflow easy to rerun and the scientific logic easy to test independently.

---

## Design principles

### 1. Nextflow handles orchestration, not core biology
The `.nf` files should describe:
- what runs
- in what order
- with which inputs and outputs
- under which profile

They should not contain the main biological logic.

### 2. Each step has a stable file contract
Every process must consume and emit predictable files with documented columns and naming.

### 3. Detection methods are peers
The three detection methods are independent strategies:
- pure
- threshold
- blast

They should be implemented as parallel modules with the same output schema.

### 4. SQLite is a final assembly artifact
Pipeline steps should not write directly into a live shared SQLite database.

Instead:
- intermediate steps emit flat files
- one dedicated database step imports those files
- the database is treated as a reproducible build artifact

### 5. Reporting is downstream only
Figures and summary tables should be generated only from finalized analysis-ready tables, never directly from raw detection code.

### 6. Simplicity over cleverness
Prefer explicit modules, explicit file contracts, and small subworkflows over deeply clever channel logic.

---

## Conceptual workflow

The pipeline is divided into four main stages:

1. **Acquisition**
2. **Detection**
3. **Database assembly**
4. **Reporting**

### Acquisition
This stage is responsible for obtaining and normalizing the biological inputs.

Typical tasks:
- fetch genome or CDS/protein inputs
- add taxonomy metadata
- run contamination checks
- normalize metadata
- optionally filter isoforms

### Detection
This stage extracts homorepeat calls from the prepared inputs.

It contains three parallel methods:
- **pure**: strict or near-strict homorepeat detection
- **threshold**: sliding-window or density-based detection
- **blast**: similarity-based detection against repeat templates

All methods must emit the same call schema.

### Database assembly
This stage imports validated flat outputs into SQLite.

Responsibilities:
- build schema
- import detection outputs
- import metadata tables
- build indexes
- validate row counts and key integrity

### Reporting
This stage produces analysis-ready summaries and final outputs.

Responsibilities:
- generate summary tables
- compute grouped statistics
- prepare regression inputs
- render figures
- export publication-ready outputs

---

## Layered repository model

### Workflow layer
Owns:
- `main.nf`
- `nextflow.config`
- `conf/*.config`
- `modules/local/*.nf`
- `subworkflows/*.nf`

Responsibilities:
- orchestration
- profiles
- execution model
- process resource settings
- file routing
- resumability

### Script layer
Owns:
- `bin/*.py`

Responsibilities:
- one script per operational task
- command-line interfaces
- deterministic input/output behavior

### Library layer
Owns:
- `lib/*.py`

Responsibilities:
- shared reusable code
- schema definitions
- sequence utilities
- repeat detection helpers
- db utilities
- plotting helpers

### Data contract layer
Owns:
- `docs/contracts.md`
- `assets/sql/schema.sql`
- `assets/sql/indexes.sql`

Responsibilities:
- document canonical columns
- define table rules
- define IDs and naming conventions

### Documentation layer
Owns:
- `docs/*.md`
- `AGENTS.md`

Responsibilities:
- architecture
- roadmap
- contracts
- repo conventions
- local agent instructions

---

## Recommended repository structure

text
homorepeat/
├── README.md
├── nextflow.config
├── main.nf
├── conf/
├── modules/
│   └── local/
├── subworkflows/
├── bin/
├── lib/
├── assets/
│   ├── sql/
│   └── templates/
├── params/
├── docs/
├── tests/
└── containers/

Subworkflow boundaries
subworkflows/acquisition.nf

Inputs:

accession lists, sequence files, or metadata tables

Outputs:

normalized sequence inputs
normalized metadata
taxonomy-linked records
subworkflows/detection.nf

Inputs:

prepared protein or CDS inputs
method parameters

Outputs:

pure_calls.tsv
threshold_calls.tsv
blast_calls.tsv
subworkflows/database.nf

Inputs:

normalized metadata
detection call tables
schema files

Outputs:

homorepeat.sqlite
subworkflows/reporting.nf

Inputs:

sqlite database or analysis-ready exports

Outputs:

summary tables
regression input tables
figures
supplementary exports
Process-level philosophy

Each process should do one thing only.

Good process examples:

FETCH_GENOMES
ADD_TAXONOMY
FILTER_ISOFORMS
TRANSLATE_CDS
FIND_POLY_PURE
FIND_POLY_THRESHOLD
FIND_POLY_BLAST
BUILD_SQLITE
EXPORT_SUMMARIES
MAKE_PLOTS

Avoid giant mixed-purpose processes.

Identifier policy

The project should define one canonical identifier strategy and preserve it throughout the workflow.

Recommended internal IDs:

genome_id
taxon_id
sequence_id
protein_id
poly_id

External identifiers may also be stored, but internal IDs should be the stable relational backbone.

Output philosophy

There are three output levels:

Raw operational outputs

Examples:

downloaded FASTA files
translated FASTA files
intermediate metadata TSVs
Standardized method outputs

Examples:

pure_calls.tsv
threshold_calls.tsv
blast_calls.tsv

These are the most important portable workflow artifacts.

Final products

Examples:

homorepeat.sqlite
summary tables
figure PDFs
supplementary TSVs
Why this architecture

This design fits the scientific workflow already established in the current project:

data retrieval
contamination/taxonomy handling
three detection strategies
SQLite integration
downstream statistical summaries and visualizations

The refactor keeps that scientific structure, but makes the implementation more reproducible, modular, and easier to rerun.
