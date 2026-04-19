# Session Log

**Date:** 2026-04-19

## Objective
- Fix the codon taxonomy gutter alignment bug where the cladogram stayed
  vertically offset from the overview heatmap rows and browse stacked-bar rows.
- Preserve the rooted visible-tree backend payload and the current codon viewer
  behavior while replacing only the unstable frontend rendering path.

## What happened
- Confirmed the visible taxon order was already correct, so the remaining bug
  was not a row-order mismatch.
- Tried several narrower frontend fixes first:
  - visible-subtree reprojection for clipped zoom windows
  - explicit zoom-window row clipping
  - switching back from the separated panel to the old ECharts overlay path
  - different y-position sources (`convertToPixel`, grid-rect band math, direct
    axis-object coordinates)
- The bug remained a stable vertical offset across zoom levels, which strongly
  suggested an ECharts layout-contract mismatch rather than a simple math bug.
- Pivoted the taxonomy gutter off ECharts rendering entirely:
  - kept the rooted-tree backend payload
  - kept the shared gutter-width calculation and zoom/window logic
  - replaced the ECharts gutter renderer with a DOM `SVG` overlay anchored to
    the chart container
  - passed explicit chart `top`, `bottom`, and `gutterWidth` values from the
    codon chart config into the gutter renderer
- The SVG gutter now draws connectors, nodes, labels, and braces from one
  explicit visible-row model, using one visible row = one row center.
- After the SVG pivot, the gutter aligned correctly against both codon charts.

## Files touched
- `static/js/taxonomy-gutter.js`
  Replaced the practical gutter rendering path with a DOM `SVG` overlay and
  kept the rooted-tree projection plus shared width/layout helpers.
- `static/js/repeat-codon-ratio-explorer.js`
  Stopped using the ECharts-driven gutter render paths and passed explicit
  layout bounds into the new SVG overlay renderer for overview and browse.
- `docs/general views/taxonomy_gutter_plan.md`
  Updated the frontend contract to describe the SVG overlay approach instead of
  ECharts `graphic`/`custom` series rendering.
- `docs/general views/taxonomy_gutter_cladogram_refactor.md`
  Updated the renderer/refactor notes to record the practical pivot away from
  ECharts-driven gutter geometry.

## Validation
- `node --check static/js/taxonomy-gutter.js`
- `node --check static/js/repeat-codon-ratio-explorer.js`
- `python manage.py test web_tests.test_browser_codon_ratios`
- Manual browser confirmation from the user:
  the SVG gutter alignment works after the pivot.

## Current status
- Done.
- Codon overview and browse now use the rooted taxonomy gutter through a stable
  SVG overlay instead of ECharts-driven gutter rendering.

## Open issues
- The SVG gutter path is currently wired only into the codon overview and
  browse charts.
- Spacing/readability polish may still be worth a follow-up pass now that the
  alignment bug is closed.

## Next step
- Treat the SVG overlay renderer as the default shared gutter path and only
  generalize/reuse it in other viewers after a small polish pass.
