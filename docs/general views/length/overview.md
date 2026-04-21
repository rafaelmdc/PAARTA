# Length Viewer Overview

## Purpose

The length viewer is the first implemented browser stats page and the baseline
for the rest of the viewer family.

It already exists technically at:

- route: `/browser/lengths/`
- view: `RepeatLengthExplorerView`

This document explains how that implementation should be treated inside the
general-views architecture on the current branch.

## Current baseline

The live length explorer already provides:

- normalized filter handling through the shared stats layer
- grouped taxon summaries over `CanonicalRepeatCall`
- a server-rendered grouped HTML table
- a page-local ECharts browse chart
- branch drill-down and taxon-detail handoffs
- targeted tests for routing, filtering, drill-down, payload shape, and UX

Relevant existing docs:

- `docs/lengthview/plan.md`
- `docs/lengthview/implementation_plan.md`
- `docs/lengthview/session-log-2026-04-16.md`

Current branch reality:

- `Tier 2 - Browse` already exists
- there is no live `Tier 1 - Overview` yet
- there is no live `Tier 3 - Inspect` yet

## Where it fits in the 3-tier model

### `Tier 1 - Overview`

Target state:

- pairwise `Taxon x Taxon` length-distribution similarity heatmap
- both axes use the same lineage-ordered visible taxa
- left and bottom taxonomy trees come from the shared taxonomy gutter
- frontend behavior should match the codon-composition overview shell:
  - square matrix layout
  - visible-window rendering
  - shared zoom and wheel behavior
  - reduced styling for larger visible windows

Default metric:

- pairwise similarity using `1 - Jensen-Shannon divergence`
- each visible taxon is represented by one bounded normalized length profile
- the internal length-bin profile is a backend implementation detail, not the
  public chart contract

This overview is intentionally not a `Taxon x Length-bin` map. The current
branch already has a proven pairwise heatmap shell with taxonomy gutters in the
codon viewer, so the length overview should reuse that path instead of starting
from a second overview design.

### `Tier 2 - Browse`

Current baseline:

- the existing length explorer at `/browser/lengths/`
- grouped taxon distributions with min, quartiles, median, and max
- boxplot-style multi-taxon browsing over the filtered result set

This is the part of the viewer that already works and should be preserved as
the browse baseline instead of being rewritten.

Implementation direction:

- keep the current boxplot-style browse chart as the primary Tier 2 view
- keep the grouped HTML table as the no-JS fallback
- keep branch drill-down and taxon-detail handoffs unchanged
- once overview lands, switch presentation order to lineage order so overview,
  browse, table, and taxonomy gutter all describe the same visible taxon set

Tier 2 should remain the cross-taxon comparison layer: compact, bounded, and
usable across many taxa at once.

### `Tier 3 - Inspect`

Target state for this track:

- branch-scoped only in the first implementation pass
- one tail-aware chart for the active branch subset
- small summary metrics and a server-rendered fallback table
- no raw repeat-call browser and no multi-panel inspect dashboard

Recommended first inspect shape:

- `CCDF / survival curve` as the primary chart
- summary statistics panel with count, median, upper quantiles, and max
- optional sampled/fallback table for the inspect distribution contract

Why this is the right first inspect layer:

- length distributions are often heavy-tailed
- inspect should reveal tail behavior rather than repeat the browse boxplot
- a branch-scoped CCDF stays small, biologically meaningful, and easy to wire
  into the existing stats page pattern

Deferred beyond the first inspect pass:

- parent-vs-branch-vs-global comparison overlays
- log-binned histogram companion chart
- richer inspect controls or multi-series comparison UI

## Reuse strategy

- keep the existing length explorer as the source of truth for stats-page
  structure
- reuse the codon viewer's pairwise overview shell instead of inventing a
  length-only overview framework
- reuse the shared taxonomy gutter for any taxon-oriented overview or browse
  axis
- extract only the pieces already proven and needed by both viewers:
  - pairwise overview payload shaping
  - pairwise overview frontend rendering
  - taxonomy gutter attachment
  - bounded visible-window behavior
- keep length-specific distribution logic in the stats layer rather than in
  view or JS code

## Design constraints

- do not regress the current length explorer while generalizing it
- keep the page meaningful without JavaScript
- keep visible result sets bounded through rank, `top_n`, `min_count`, and
  branch scope
- keep lineage order as the visible presentation order once overview lands
- never ship unbounded raw repeat-call rows to the page
- preserve a clear distinction between:
  - overview for broad lineage-level pattern discovery
  - browse for grouped multi-taxon comparison
  - inspect for focused branch-scoped tail-aware analysis
