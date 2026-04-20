# Session Log

**Date:** 2026-04-20

## Objective
- Freeze the codon-composition browser behavior at its current MVP boundary in
  the docs.
- Make the codon-composition docs describe the page that actually ships now,
  not the earlier target design.

## What happened
- Reviewed the current codon-composition route, template, backend payload, and
  frontend chart behavior to confirm the live browser contract.
- Rewrote the codon-composition overview doc so it now describes the shipped
  composition-first route, the current pairwise overview behavior, the stacked
  browse layer, the branch-scoped inspect layer, and the explicit MVP freeze.
- Replaced the old codon-composition implementation-plan slices doc with a
  status document that separates shipped MVP behavior from deferred post-MVP
  work.
- Updated the shared foundation and general-view plan docs so they record the
  current codon-composition exception:
  the shared target remains taxonomy-first overview shells, but codon
  composition is intentionally frozen on the current pairwise `Taxon x Taxon`
  overview for the MVP.
- Recorded that lineage-aware ordering now includes the curated Metazoa
  sibling order used to keep root-linked phyla biologically coherent.

## Files touched
- `docs/general views/codon_composition/overview.md`
  Reframed the viewer as the frozen codon-composition MVP contract.
- `docs/general views/codon_composition/slices.md`
  Replaced the old forward implementation plan with shipped-vs-deferred MVP
  status.
- `docs/general views/shared_foundation.md`
  Added the current codon-composition overview exception and the Metazoa
  sibling-order note.
- `docs/general views/general_plan.txt`
  Updated the top-level general-views plan to reflect the frozen codon
  composition MVP state.

## Validation
- No code validation run.
- Docs-only update based on the current inspected browser view, payload, JS,
  and existing browser tests.

## Current status
- Done.
- Codon composition is now documented as frozen at its current MVP browser
  behavior.

## Open issues
- Route, template, and asset names still use `codon_ratio` in the
  implementation surface.
- The current overview remains a pairwise `Taxon x Taxon` heatmap rather than
  the original `Taxon x Codon` target.

## Next step
- Treat further codon-composition changes as post-MVP work unless they are
  small correctness or stability fixes.

---

# Session Log

**Date:** 2026-04-20

## Objective
- Re-ground the length-view plan on the correct branch where the codon-style
  taxonomy gutter and pairwise overview code actually exist.
- Rewrite the length docs around that reality, then start implementing the
  reuse-first slices for the length overview backend.

## What happened
- Confirmed the previous branch context was wrong and re-inspected the live
  codon-composition browser, including the shared taxonomy gutter and pairwise
  overview behavior.
- Rewrote `docs/general views/length/overview.md` so the length overview is now
  explicitly planned as a codon-style pairwise `Taxon x Taxon` heatmap rather
  than a `Taxon x Length-bin` chart.
- Recreated `docs/general views/length/slices.md` with a phased plan that
  prioritizes reusing the codon overview shell, taxonomy gutter, and stats
  seams, and includes an inspect track.
- Implemented `L2` by extracting the shared backend pairwise-overview payload
  seam in `apps/browser/stats/payloads.py` without changing the codon payload
  contract.
- Implemented `L3` by moving the codon pairwise overview renderer into the new
  shared frontend module `static/js/pairwise-overview.js`, then rewiring the
  codon page to call it.
- Implemented `L4` by adding `build_length_profile_vector_bundle(...)` and
  `summarize_length_profile_vectors(...)`, reusing the existing visible taxa and
  shared 5-aa length bins to build bounded normalized per-taxon profiles.
- Implemented `L5` by adding `build_length_overview_payload(...)` on top of the
  shared pairwise payload seam so the length viewer now has a backend payload
  builder for the future pairwise overview.

## Files touched
- `docs/general views/length/overview.md`
  Reframed the length overview as codon-style pairwise taxon similarity and
  narrowed the inspect MVP to branch-scoped CCDF.
- `docs/general views/length/slices.md`
  Recreated the full phased implementation plan with overview, browse
  alignment, and inspect phases.
- `static/js/pairwise-overview.js`
  New shared frontend module for pairwise overview rendering, including
  visible-window painting and taxonomy-gutter attachment.
- `static/js/repeat-codon-ratio-explorer.js`
  Reduced the codon page to a wrapper that mounts the shared pairwise overview
  renderer.
- `templates/browser/codon_ratio_explorer.html`
  Loads the new shared pairwise overview script.
- `apps/browser/stats/summaries.py`
  Added normalized length-profile vector shaping over the shared length bins.
- `apps/browser/stats/queries.py`
  Added `build_length_profile_vector_bundle(...)`.
- `apps/browser/stats/payloads.py`
  Added the shared pairwise payload seam and `build_length_overview_payload(...)`.
- `apps/browser/stats/__init__.py`
  Exported the new length overview/profile helpers.
- `web_tests/test_browser_stats.py`
  Added direct backend coverage for codon payload shape, length profile vectors,
  and the length pairwise overview payload.

## Validation
- `python manage.py test web_tests.test_browser_stats`
- `python manage.py test web_tests.test_browser_codon_ratios`
- `node --check static/js/pairwise-overview.js`
- `node --check static/js/repeat-codon-ratio-explorer.js`
- `python -m py_compile apps/browser/stats/payloads.py`
- `python -m py_compile apps/browser/stats/queries.py apps/browser/stats/summaries.py`

## Current status
- In progress.
- Docs are updated and backend/frontend reuse seams for the length overview are
  now in place through `L5`.

## Open issues
- The length page still does not consume the new overview payload; `L6` is the
  next wiring step.
- The length template and JS still reflect the old browse-only page shell.
- Inspect work has only been planned so far; no inspect implementation has
  started.

## Next step
- Implement `L6` by wiring the length overview payload and taxonomy-gutter
  payload into `RepeatLengthExplorerView` without changing the page shell yet.
