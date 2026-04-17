# Codon Composition Viewer Slices

## Goal

Replace the scalar codon-ratio browser direction with a composition-first
viewer built on normalized codon-usage rows.

## Phase 1: Replace the data contract

### `CC1` Publish merged codon usage as a canonical browser artifact

Goal:

- make codon browser work depend on normalized composition rows rather than
  blank compatibility fields

Scope:

- add canonical `publish/calls/codon_usage.tsv` to the pipeline output surface
- keep finalized per-batch codon-usage files for audit and debugging
- expose the merged artifact through runtime manifest metadata

Tests:

- merged codon-usage artifact exists
- merged rows equal the union of finalized codon-usage rows

Exit criteria:

- downstream browser import has one canonical codon-usage source

### `CC2` Add imported and canonical codon-usage models

Goal:

- make codon composition first-class in the browser schema

Scope:

- raw imported codon-usage rows linked to imported repeat calls
- canonical/current-catalog codon-usage rows linked to canonical repeat calls
- preserve the normalized fields already emitted by codon usage

Tests:

- schema-level coverage
- canonical-sync coverage

Exit criteria:

- the browser can query codon mixtures without overloading repeat-call scalar
  fields

### `CC3` Import and sync codon-usage rows

Goal:

- populate composition data during normal import and canonical sync

Scope:

- ingest merged `publish/calls/codon_usage.tsv`
- align canonical codon-usage rows with current canonical repeat calls
- keep missing codon-usage data as an explicit empty-state path

Tests:

- successful import into raw and canonical codon-usage tables
- missing artifact does not break repeat-call import

Exit criteria:

- browser composition queries have real imported data

## Phase 2: Add composition query support

### `CC4` Add normalized filter support for composition views

Goal:

- keep codon composition inside the shared stats page contract

Scope:

- residue stays first-class
- remove scalar codon metric selection from the hot path
- keep branch, rank, run, `min_count`, and `top_n` semantics aligned with the
  rest of the viewer family

Tests:

- residue-scoped behavior
- branch- and run-scoped behavior

Exit criteria:

- composition pages use the same normalized stats state shape as length

### `CC5` Add grouped codon-composition queries and summaries

Goal:

- support grouped taxon composition before chart work

Scope:

- grouped codon shares by display taxon
- equal call weight aggregation
- visible codon discovery inside the current residue scope

Tests:

- 2-codon residue grouping
- 4-codon residue grouping
- equal-call-weight behavior

Exit criteria:

- the backend can produce one bounded composition row per visible taxon

## Phase 3: Replace the current route with composition browse behavior

### `CC6` Replace the existing codon-ratio page shell

Goal:

- make `/browser/codon-ratios/` represent codon composition rather than a
  broken scalar contract

Scope:

- rewrite page copy and scope language around codon composition
- remove scalar codon metric selection and scalar summary language
- keep the route for continuity during the redesign

Tests:

- route resolution remains stable
- new copy and empty states render correctly

Exit criteria:

- the existing route no longer implies a single-value codon metric

### `CC7` Add the grouped composition fallback table

Goal:

- keep the page useful without JavaScript

Scope:

- grouped HTML table with visible codon shares and call counts
- explicit empty states for no codon-usage data vs no visible taxa
- taxon detail and branch drill-down links

Tests:

- grouped table output
- branch-link preservation

Exit criteria:

- codon composition is browseable without JavaScript

### `CC8` Add the shared `Tier 1 - Overview`

Goal:

- deliver the taxonomy-first overview while preserving codon mixtures

Scope:

- `Taxon x Codon` hex overview for one selected residue
- lineage-aware taxonomy axis
- equal-weight codon fraction as the cell value

Tests:

- payload shape
- empty-state behavior
- page-local asset loading

Exit criteria:

- codon composition has the shared Tier 1 overview shell

### `CC9` Add the stacked browse chart

Goal:

- make the grouped composition rows visually comparable across many taxa

Scope:

- stacked taxon composition chart
- same visible set as the server-rendered grouped table
- branch drill-down and taxon detail handoffs

Tests:

- payload shape
- chart/table visible-set parity

Exit criteria:

- codon composition has a real Tier 2 browse layer

### `CC10` Add composition inspect views

Goal:

- support detailed analysis for one branch or taxon

Scope:

- selected branch or taxon composition detail
- optional per-call composition preview where needed
- no scalar histogram or boxplot as the default inspect model

Tests:

- inspect-state render
- inspect payload shape

Exit criteria:

- codon composition spans all three tiers

### `CC11` Add discoverability and handoffs

Goal:

- make the composition viewer part of the browser family rather than a legacy
  compatibility route

Scope:

- browser home entry and copy updates
- branch handoffs from taxon detail
- residue-preserving handoffs from protein and repeat-call detail when valid

Exit criteria:

- codon composition is reachable through the same browser pathways as length
