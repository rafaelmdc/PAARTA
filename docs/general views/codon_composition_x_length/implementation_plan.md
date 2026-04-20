# Codon Composition x Length Implementation Plan

## Purpose

This document turns
[overview.md](/home/rafael/Documents/GitHub/homorepeat/docs/general views/codon_composition_x_length/overview.md)
into an execution sequence for building the codon-composition-by-length viewer.

It is explicitly architecture-aware:

- reuse the existing browser stats stack
- reuse the existing codon-composition aggregation contract
- reuse the existing length-bin and lineage-order helpers
- only extract shared frontend/backend pieces when a second consumer already
  exists or this viewer clearly needs them

It is also explicitly performance-aware:

- this page combines two high-cardinality dimensions
- the default path must stay bounded and cheap enough for browser use
- the implementation should be designed around grouped rows and compact
  payloads, not raw repeat-call materialization

## Product Boundary

This plan is for a browser viewer inside `apps.browser`.

Out of scope for this track:

- changing `homorepeat_pipeline`
- introducing a second filter architecture
- adding mixed-residue codon aggregation
- building an unbounded all-taxa trend page
- shipping per-call codon x length rows to the browser

## Reuse Rules

The implementation should preferentially reuse:

- `apps/browser/views/stats/codon_ratios.py`
- `apps/browser/views/stats/lengths.py`
- `apps/browser/stats/filters.py`
- `apps/browser/stats/queries.py`
- `apps/browser/stats/summaries.py`
- `apps/browser/stats/payloads.py`
- `apps/browser/stats/taxonomy_gutter.py`
- `apps/browser/stats/bins.py`
- `static/js/pairwise-overview.js`

Reuse intent:

- codon composition supplies the residue-scoped grouped-composition semantics
- length view supplies the shared length-bin contract and support-aware grouped
  numeric handling
- the pairwise-overview code supplies visible-window rendering, zoom handling,
  and taxonomy gutter integration patterns

Do not:

- fork a second lineage-order implementation
- let JS invent bin definitions
- compute the same grouped taxon set separately for overview and browse when
  one shared bundle can drive both

## Performance Rules

These are implementation constraints, not later cleanup work.

- always bound the visible taxa through the existing `top_n`, `rank`,
  `min_count`, and branch-scope controls
- require a residue before activating the page's biological contract
- do not materialize per-call codon rows in Python for the default page path
- prefer grouped SQL rows of the form:
  - `display_taxon_id`
  - `length_bin`
  - `codon`
  - `observation_count`
  - `species_count`
  - `codon_share`
- keep zero-heavy payloads compact by sending:
  - one ordered visible codon list
  - one ordered visible bin list
  - sparse per-taxon occupied-bin rows
- treat the default unscoped page as the optimization target
- plan for a rollup table once the live grouped path is correct and testable

## Current Baseline

Already implemented elsewhere in the browser:

- normalized stats filter parsing
- lineage-aware visible-taxon ordering
- taxonomy gutter payload generation and attachment
- pairwise overview shell with visible-window rendering
- codon-composition grouped summaries and inspect mode
- length-bin helpers and optimized grouped length profile generation
- codon-composition summary rollup table for the default residue-scoped path

Missing for this viewer:

- route and page shell
- grouped `taxon x length-bin x codon` data contract
- `Taxon x Length-bin` overview renderer
- browse small-multiples for composition-across-length
- inspect table/chart for focused composition-across-length
- default-path rollup table for fast generation

## Current Status

As of `2026-04-20`:

- `CL3.1` remains implemented and should be kept
- `CL3.2` was attempted, but then reverted back to the `CL3.1` baseline
- the live/runtime codon-length overview payload was verified to be correct on
  the real dataset:
  - `38` taxa
  - `287` bins
  - `910` occupied cells
  - row indices spanning `0..37`

Current interpretation:

- the failed `CL3.2` attempt was a frontend rendering problem
- the problem was not in the summarized backend bundle
- the next `CL3.2` attempt should start from a fresh renderer, not from
  patching the discarded implementation

Implementation rule for the retry:

- prove plain `row x bin` binding first
- do not add taxonomy gutter until the minimal matrix is visually correct
- do not start with custom glyphs or support-opacity tricks
- only reintroduce gutter and richer encodings after the base matrix is stable

## Target Internal Contract

The page should be built around one shared summarized bundle.

Recommended builder:

- `build_codon_length_composition_bundle(filter_state)`

Recommended bundle shape:

- `matching_repeat_calls_count`
- `visible_taxa_count`
- `total_taxa_count`
- `visible_codons`
- `visible_bins`
- `matrix_rows`

Recommended `matrix_rows` shape:

- one row per visible taxon
- fixed lineage order
- sparse occupied-bin entries only

Recommended occupied-bin entry shape:

- `bin_start`
- `bin_label`
- `observation_count`
- `species_count`
- `codon_shares`
- `dominant_codon`
- `dominance_margin`

Design rule:

- overview, browse, and most inspect views should read from this same bundle
- dominant-codon and shift modes should be derived from this bundle, not built
  through separate database passes

## Phase 1: Page Ownership And Shared Contract

### Slice `CL1.1`: Add route, view shell, and template skeleton

Goal:

- give the viewer a stable browser entry point without inventing new page
  conventions

Scope:

- add `/browser/codon-composition-length/` to `apps/browser/urls.py`
- add a URL-facing view under `apps/browser/views/stats/`
- add a dedicated template under `templates/browser/`
- re-export the view from `apps/browser/views/__init__.py`

Required behavior:

- use `build_stats_filter_state(...)`
- require residue selection for meaningful output
- keep run, branch, rank, method, target search, and length-range controls
  aligned with the existing stats pages
- keep the page useful without JavaScript through server-rendered fallbacks

Exit criteria:

- the route resolves
- the page renders a stable filter shell and current-scope summary
- empty states are residue-aware and consistent with the codon-composition page

### Slice `CL1.2`: Define the shared bundle and payload boundaries

Goal:

- make the page data model explicit before implementing charts

Scope:

- define the backend bundle shape in `apps/browser/stats/queries.py`
- define any companion payload shaping in `apps/browser/stats/payloads.py`
- keep the page contract centered on one summarized bundle

Required behavior:

- one shared visible taxon set drives overview, browse, and table fallbacks
- visible codon order is fixed by the backend
- visible bin order is fixed by the backend
- support metadata is present in every occupied taxon-bin state

Exit criteria:

- the new builder has a documented return shape
- the view can build context from the bundle without requerying for the same
  visible taxon/bin state

### Slice `CL1.3`: Add tests for contract shape and empty-state semantics

Goal:

- lock the page boundary before adding rendering complexity

Scope:

- stats-layer tests for bundle shape
- browser-view tests for residue-required behavior
- template-context tests for empty states and current-scope details

Exit criteria:

- failing fast on contract drift becomes easy
- no future chart work can silently change the backend shape

## Phase 2: Live Grouped Backend

### Slice `CL2.1`: Reuse the existing visible-taxon selection path

Goal:

- avoid recomputing the visible taxon set through a second ranking algorithm

Scope:

- reuse the codon-composition summary selection rules for:
  - residue scope
  - rank
  - `min_count`
  - `top_n`
- preserve lineage ordering after selection

Required behavior:

- visible taxa are selected once
- the same visible taxa feed overview, browse, and fallback tables
- the page does not rank taxa differently in different sections

Exit criteria:

- the visible taxon list is derived from one source of truth

### Slice `CL2.2`: Add grouped live query for `taxon x length-bin x codon`

Goal:

- fetch only the grouped rows needed for the current visible taxon set

Scope:

- add a grouped query builder in `apps/browser/stats/queries.py`
- filter first, then annotate display taxa, then group
- group by:
  - display taxon
  - length bin
  - codon

Recommended live query output:

- `display_taxon_id`
- `length_bin_start`
- `codon`
- `codon_fraction_sum`
- `observation_count`
- `species_count`

Implementation rule:

- do not expand every repeat call into a Python-side nested structure before
  grouping
- compute grouped rows in SQL and only assemble the compact bundle in Python

Exit criteria:

- the live path can build the page bundle without loading raw repeat-call-level
  codon usage into Python

### Slice `CL2.3`: Summarize grouped rows into the shared bundle

Goal:

- translate grouped SQL output into one reusable page object

Scope:

- add summarization helpers in `apps/browser/stats/summaries.py`
- build:
  - visible bins
  - taxon rows
  - ordered codon shares per occupied bin
  - support metadata
  - dominant codon and margin

Required behavior:

- codon shares remain normalized within each taxon-length bin
- absent codons are represented as zero using the fixed visible codon order
- sparse bins remain sparse rather than being silently dropped from the support
  model

Exit criteria:

- one summarized bundle is enough to render:
  - composition overview
  - dominant-codon overview
  - shift overview
  - browse small multiples
  - fallback tables

### Slice `CL2.4`: Profile the live path before adding frontend work

Goal:

- make sure the page is not already too slow before UI layers hide the problem

Scope:

- time the new builder on the real Compose/Postgres dataset
- measure:
  - visible taxon selection
  - grouped live query
  - Python summarization

Required behavior:

- profile with realistic residue-scoped default settings
- record whether the grouped live path is already acceptable or clearly needs a
  rollup before broad frontend work

Exit criteria:

- there is a measured baseline for the live grouped path

## Phase 3: Overview Matrix

### Slice `CL3.1`: Extract shared non-pairwise chart helpers

Goal:

- reuse the proven browser chart shell behavior without forcing a pairwise
  abstraction onto the wrong chart type

Scope:

- extract generic pieces from `static/js/pairwise-overview.js`:
  - chart sizing
  - visible-window row zoom
  - taxonomy gutter reservation and attachment
  - wheel and slider behavior
- keep pairwise-specific matrix semantics in place for existing pages

Required behavior:

- no regression to codon or length pairwise overviews
- the new viewer can reuse shared row-window and gutter mechanics

Exit criteria:

- generic chart shell utilities exist without breaking the current pairwise
  code

### Slice `CL3.2`: Implement primary `Composition matrix` mode

Goal:

- ship the composition-first landing state described in the overview

Scope:

- render `Taxon x Length-bin` cells from the shared bundle
- for 2-codon residues:
  - use a compact split tile or internal proportion bar
- for 3+ codon residues:
  - use a tiny fixed-order stacked bar inside each cell

Required behavior:

- taxonomy gutter stays attached to the y-axis
- visible rows are lineage-ordered
- x-axis uses the backend-defined shared bins
- low-support bins are visually downweighted or flagged

Exit criteria:

- the page lands on composition, not scalar summaries

Retry note:

- the previous `CL3.2` attempt was reverted
- the retry should begin with a deliberately simpler matrix than originally
  described here:
  - stable `Taxon x Length-bin` binding first
  - no taxonomy gutter on the first rendering pass
  - no custom-series cell glyphs on the first rendering pass
  - add gutter and richer composition encoding only after the base matrix is
    proven correct

### Slice `CL3.3`: Implement `Dominant codon` companion mode

Goal:

- make codon dominance flips easy to scan at lineage scale

Scope:

- derive dominant codon and dominance margin from the shared bundle
- render the same `Taxon x Length-bin` geometry with alternate cell emphasis

Required behavior:

- do not issue a new backend query for this mode
- tooltip/reporting still exposes the underlying composition and support
- weak dominance remains visually distinguishable from clear domination

Exit criteria:

- users can scan where codon winners change with length without leaving the
  overview layer

### Slice `CL3.4`: Implement `Composition shift` companion mode

Goal:

- reveal where codon composition changes sharply between adjacent bins

Scope:

- derive adjacent-bin transitions from the shared bundle
- for 2-codon residues:
  - use absolute change in one codon share
- for 3+ codon residues:
  - use L1 distance between normalized composition vectors

Required behavior:

- reuse the same visible taxa and the same bin order
- do not compute shift through a separate query
- empty or missing adjacent bins should not fabricate transitions

Exit criteria:

- the page highlights transition points rather than only static mixtures

## Phase 4: Browse Layer

### Slice `CL4.1`: Implement per-taxon small multiples

Goal:

- move from lineage-scale scanning to per-taxon trajectory reading

Scope:

- build one panel per visible taxon
- reuse the shared summarized bundle
- for 2-codon residues:
  - line or area view
- for 3+ codon residues:
  - stacked bars or stacked areas

Required behavior:

- fixed codon order across all panels
- fixed x-axis bin order across all panels
- bounded visible taxa only

Exit criteria:

- users can compare multiple taxa without overlay clutter

### Slice `CL4.2`: Add support strips under each panel

Goal:

- keep sparse long bins biologically honest in the browse layer

Scope:

- render a simple count strip or dot strip from per-bin support metadata
- expose support in tooltips and the server-rendered fallback table

Required behavior:

- support remains visible even when codon mixtures look dramatic
- low-support long bins do not read as equally reliable as dense central bins

Exit criteria:

- browse panels preserve both mixture and support

### Slice `CL4.3`: Add server-rendered grouped fallback output

Goal:

- preserve no-JS usefulness and simplify test coverage

Scope:

- render a grouped HTML table based on the shared bundle
- include at minimum:
  - taxon
  - length bin
  - observation count
  - species count
  - codon shares
  - dominant codon

Required behavior:

- fallback output describes the same visible taxa and bins as the JS browse
  layer
- pagination, if needed, should reuse the grouped summary pagination pattern

Exit criteria:

- the page remains analytically useful without JavaScript

## Phase 5: Inspect Layer

### Slice `CL5.1`: Add branch-scoped inspect activation

Goal:

- match the current viewer-family inspect contract before broadening it

Scope:

- activate inspect only when branch scope is active
- reuse the same residue and filter-state handling as the page shell

Required behavior:

- inspect does not create a separate filter system
- branch scope remains the primary detail handoff from overview and browse

Exit criteria:

- the new viewer fits the current overview/browse/inspect page family

### Slice `CL5.2`: Add focused detailed chart and exact table

Goal:

- expose the full composition-across-length story for one focused lineage

Scope:

- render a detailed composition-across-length chart
- render a server-side exact table with:
  - length bin
  - observation count
  - species count
  - codon shares
  - dominant codon
  - dominance margin
  - optional delta from previous bin

Required behavior:

- inspect reuses the same codon order as overview and browse
- inspect reuses the same length-bin contract
- inspect does not fall back to raw per-call browsing

Exit criteria:

- one lineage can be inspected in detail without leaving the viewer contract

### Slice `CL5.3`: Add optional comparison summary

Goal:

- provide context without turning inspect into a large dashboard

Scope:

- optionally compare the focused branch against:
  - parent branch aggregate
  - sibling mean
- keep this as a compact companion, not a second main chart family

Exit criteria:

- inspect gains lineage context without exploding scope

## Phase 6: Default-Path Rollup Optimization

### Slice `CL6.1`: Add a dedicated rollup model and migration

Goal:

- make the default residue-scoped page fast without depending on expensive live
  grouped aggregation

Recommended rollup grain:

- `repeat_residue`
- `display_rank`
- `display_taxon`
- `length_bin_start`
- `observation_count`
- `species_count`
- `codon`
- `codon_share`

Scope:

- add a new canonical summary model and migration
- add browse-oriented indexes for:
  - residue
  - rank
  - observation count ordering
  - display taxon lookup
  - taxon-plus-bin lookup

Required behavior:

- the rollup preserves the same biological meaning as the live grouped path
- one row grain is sufficient to reconstruct composition, dominance, support,
  and shift at request time

Exit criteria:

- the database can answer the default page path from precomputed grouped rows

### Slice `CL6.2`: Add rollup rebuild command

Goal:

- give the browser an explicit backfill path like the codon-composition viewer

Scope:

- add a rebuild helper in `apps/browser/stats/`
- add a management command under `apps/browser/management/commands/`

Required behavior:

- support PostgreSQL-first rebuild logic
- retain a Python fallback if the project still expects test/database
  portability

Exit criteria:

- rollup rows can be rebuilt intentionally and repeatably

### Slice `CL6.3`: Add safe rollup eligibility logic

Goal:

- use the rollup only when it actually matches the request semantics

Recommended rollup-eligible scope:

- residue selected
- no explicit run filter
- no branch scope
- no target search
- no method filter
- no purity filter
- no custom length range

Required behavior:

- default unscoped path uses rollup
- narrower filtered paths fall back to the live grouped query
- rollup and live paths produce the same visible contract

Exit criteria:

- the hot path is fast and correctness-preserving

### Slice `CL6.4`: Add parity tests and timing checks

Goal:

- prevent the optimized path from silently drifting from the live path

Scope:

- rollup/live parity tests for visible codons, bins, support counts, and codon
  shares
- timing checks against the Compose/Postgres dataset

Exit criteria:

- the optimized default path is both faster and meaningfully equivalent

## Phase 7: Final Integration And Stabilization

### Slice `CL7.1`: Add browser navigation and handoffs

Goal:

- make the page discoverable only after its core semantics are stable

Scope:

- add links from the browser home or related viewer surfaces
- preserve taxon detail and branch drill-down handoffs

Exit criteria:

- the page is discoverable without changing its core contract

### Slice `CL7.2`: Harden browser performance and rendering behavior

Goal:

- keep the viewer usable at realistic visible-taxa sizes

Scope:

- clamp any page-specific `top_n` maximum if needed
- reduce expensive per-cell styling for large windows
- verify chart resize, wheel, and gutter behavior on desktop and mobile widths

Exit criteria:

- the page remains responsive under the intended bounded load

### Slice `CL7.3`: Freeze the shipped contract

Goal:

- document what the first shipped version actually is

Scope:

- update the overview and slice docs once implementation settles
- mark deferred items explicitly rather than leaving them implied

Exit criteria:

- future work starts from a clear shipped contract instead of a half-open plan

## Recommended Delivery Order

If this work is done incrementally, the recommended order is:

1. `CL1.1` to `CL1.3`
2. `CL2.1` to `CL2.4`
3. `CL3.1` and `CL3.2`
4. `CL4.1` to `CL4.3`
5. `CL3.3` and `CL3.4`
6. `CL5.1` to `CL5.3`
7. `CL6.1` to `CL6.4`
8. `CL7.1` to `CL7.3`

Reasoning:

- get the shared data contract correct before building specialized modes
- prove the live grouped semantics before adding the rollup
- make composition mode work before dominance and shift
- let inspect and navigation follow the stable page contract

## High-Risk Areas

These slices are most likely to need extra care:

- `CL2.2`
  - grouped query design can become too expensive if it joins and expands
    call-level codon rows carelessly
- `CL3.1`
  - frontend extraction can regress the existing pairwise pages if it is too
    broad
- `CL6.1`
  - a rollup with the wrong grain will either lose biological meaning or still
    force too much request-time work

## Non-Negotiable Invariants

- residue is required for the page's main contract
- codon order stays fixed across all tiers
- length bins come from shared backend helpers
- visible taxa stay lineage-ordered
- support metadata remains first-class
- dominant-codon and shift views are derived companions, not separate biological
  contracts
- default-path optimization must preserve the live grouped meaning
