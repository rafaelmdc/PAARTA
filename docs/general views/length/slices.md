# Length Viewer Slices

## Status

The current branch already ships the length browse baseline at
`/browser/lengths/`.

This implementation track adds the missing overview and inspect layers while
reusing as much of the codon-composition browser stack as possible.

Core decisions:

- overview is a codon-style pairwise `Taxon x Taxon` heatmap
- visible taxa are presented in lineage order across overview, browse, and
  grouped table
- inspect is branch-scoped only in the first pass
- inspect uses a CCDF as the first chart

Boundary rule:

- keep one browser stats stack in `apps/browser/stats/`
- do not build a length-only tree widget or a second heatmap framework
- only extract shared helpers that codon and length both consume immediately

## Phase 1: Reuse Seams First

### `L1` Freeze the current length browse baseline

Goal:

- treat the live length page as the correct Tier 2 baseline

Scope:

- keep the current boxplot browse chart
- keep the grouped HTML table
- keep current branch drill-down and taxon-detail handoffs

Exit criteria:

- no product rewrite of browse happens before overview work

### `L2` Extract a shared backend pairwise-overview payload seam

Goal:

- reuse one bounded pairwise matrix payload contract across codon and length

Scope:

- extract a private shared helper in `apps/browser/stats/payloads.py`
- keep the common pairwise shell in that helper:
  - `mode`
  - `taxa`
  - `divergenceMatrix`
  - visible-taxa metadata
  - value range metadata
- keep the current codon payload shape stable

Exit criteria:

- codon still emits the same public overview payload
- length can build on the same pairwise payload seam

### `L3` Extract a shared frontend pairwise-overview renderer

Goal:

- reuse the codon overview shell instead of cloning it into length JS

Scope:

- extract the pairwise overview rendering path from
  `static/js/repeat-codon-ratio-explorer.js`
- keep shared behavior in the extracted seam:
  - square matrix layout
  - y-axis zoom
  - visible-window matrix slicing
  - wheel navigation
  - large-window styling fallback
  - taxonomy-gutter attachment hooks
- continue using `static/js/taxonomy-gutter.js` unchanged

Exit criteria:

- codon still renders through the shared seam
- length can mount the same pairwise shell with a different payload

## Phase 2: Length Overview Backend

### `L4` Build bounded per-taxon length profile vectors

Goal:

- represent each visible taxon as one normalized length-distribution profile

Scope:

- start from the same visible taxa selected by the length summary bundle
- build one bounded length profile per visible taxon in `apps/browser/stats/`
- keep the length-bin definition internal to the stats layer

Exit criteria:

- each visible taxon has one stable vector suitable for pairwise comparison

### `L5` Build the length pairwise overview payload

Goal:

- emit the length overview through the shared pairwise payload seam

Scope:

- compute pairwise divergence from the bounded length profiles
- expose similarity as `1 - Jensen-Shannon divergence`
- emit the same taxon metadata shape expected by the shared frontend renderer
- build the taxonomy gutter payload from the same visible lineage-ordered rows

Exit criteria:

- the backend can emit a complete pairwise overview payload for length

### `L6` Wire overview context into `RepeatLengthExplorerView`

Goal:

- expose the new overview contract to the length template

Scope:

- add overview payload context
- add overview taxonomy-gutter payload context
- keep the existing browse payload and links intact

Exit criteria:

- the length template receives overview data without changing route or filter
  semantics

## Phase 3: Length Page Shell

### `L7` Add the overview section to the length template

Goal:

- give the length page the same top-level overview card pattern as codon

Scope:

- add overview card copy
- add overview payload script tag
- add overview taxonomy-gutter payload script tag
- add overview chart container
- include the taxonomy-gutter script

Exit criteria:

- the template is ready to mount the pairwise overview

### `L8` Mount the shared pairwise overview renderer on the length page

Goal:

- render the pairwise overview using the codon-style shell

Scope:

- mount the shared pairwise heatmap renderer from `repeat-length-explorer.js`
- reuse left and bottom taxonomy trees
- reuse visible-window rendering for large matrices

Exit criteria:

- the length overview renders with the same behavioral shell as codon

## Phase 4: Browse Alignment And Overview Freeze

### `L9` Make lineage order the shared visible-order contract

Goal:

- align the visible order across all length page layers

Scope:

- use lineage order for:
  - overview axes
  - taxonomy gutter
  - browse chart rows
  - grouped table rows
- keep any count-ranked selection internal to candidate selection only

Exit criteria:

- overview, browse, and table describe the same visible taxon ordering

### `L10` Freeze overview plus browse behavior

Goal:

- stabilize the shared overview shell before adding inspect

Scope:

- keep the codon-style pairwise overview as the fixed reuse baseline
- avoid mixing inspect work into unresolved overview behavior

Exit criteria:

- overview and browse are stable enough to build inspect on top

## Phase 5: Length Inspect Backend

### `L11` Add a branch-scoped length inspect bundle

Goal:

- add one cached inspect bundle that matches the existing stats-page pattern

Scope:

- add a bundle builder in `apps/browser/stats/queries.py`
- add a payload builder in `apps/browser/stats/payloads.py`
- activate only when branch scope is active
- expose:
  - scope label
  - observation count
  - CCDF points
  - median
  - upper quantiles
  - max

Exit criteria:

- the backend can emit one bounded inspect contract without sending raw repeat
  rows to the page

### `L12` Add small shared numeric inspect helpers

Goal:

- keep inspect shaping out of the view and keep it reusable

Scope:

- add narrow helpers for CCDF point shaping and metric normalization in
  `apps/browser/stats/`
- keep extraction small enough that it does not become a generic chart
  framework

Exit criteria:

- inspect bundle shaping is reusable and stays in the stats layer

### `L13` Wire inspect context into `RepeatLengthExplorerView`

Goal:

- expose inspect state through the same pattern already used by codon

Scope:

- add:
  - `inspect_scope_active`
  - `inspect_payload`
  - `inspect_payload_id`
  - `inspect_chart_container_id`
  - inspect summary values
  - inspect empty reason
- reuse existing branch-scope label conventions

Exit criteria:

- the length template can render inspect only when branch scope is active

## Phase 6: Length Inspect UI

### `L14` Add the inspect section to the length template

Goal:

- add a lightweight Tier 3 shell without changing the page contract

Scope:

- place inspect after the grouped taxa section
- render it only when branch scope is active
- include:
  - one CCDF chart container
  - a small metric row
  - a fallback HTML table
  - a clear empty state

Exit criteria:

- inspect has a server-rendered fallback and a stable mount point

### `L15` Add the CCDF inspect renderer to `repeat-length-explorer.js`

Goal:

- render the first inspect chart with minimal new frontend code

Scope:

- add one payload parser path
- add one CCDF mount function
- add page-local resize handling
- keep the first inspect chart single-series and branch-scoped

Exit criteria:

- the length page renders one tail-aware inspect chart when inspect payload is
  present

### `L16` Freeze the first inspect MVP

Goal:

- stop the inspect layer before scope creep

Scope:

- keep inspect at:
  - branch-scoped CCDF
  - summary metrics
  - fallback table
- defer:
  - histogram companion chart
  - parent/global comparison overlays
  - richer inspect controls

Exit criteria:

- the first length inspect layer is complete and bounded

## Test Plan

- Codon regression checks:
  - shared payload extraction does not change codon overview payload shape
  - shared overview extraction does not change codon taxonomy-gutter behavior
  - codon inspect behavior remains unchanged
- Length overview checks:
  - overview uses the same bounded visible taxa selected by the page filters
  - visible taxa are lineage-ordered
  - the pairwise matrix is square and stable for empty and small result sets
  - grouped table, browse chart, overview, and gutter all use the same visible
    taxon order
- Length inspect checks:
  - inspect activates only under branch scope
  - inspect payload stays aggregated and bounded
  - CCDF payload is valid for empty, small, and larger branch scopes
  - inspect summary values match the filtered branch subset
  - no-JS fallback remains meaningful
- Frontend checks:
  - overview uses the same visible-window strategy as codon for large matrices
  - left and bottom taxonomy gutters stay aligned during zoom and resize
  - inspect chart mounts only when payload exists
  - `node --check` passes for affected JS files

## Deferred After This Track

- length inspect comparison overlays against parent or global scope
- histogram companion inspect chart
- additional browse controls beyond the current boxplot baseline
- any redesign away from the codon-style pairwise overview shell
