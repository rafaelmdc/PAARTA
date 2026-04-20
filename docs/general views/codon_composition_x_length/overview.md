# Codon Composition x Length Viewer Overview

## Purpose

This is the flagship comparison viewer for the first wave.

It is a **composition-first** viewer, not a scalar codon-ratio page. Its job is
to preserve codon mixtures across repeat length instead of collapsing each
taxon-length state into a single number.

Planned route:

- `/browser/codon-composition-length/`

Core questions:

- how codon mixtures change across repeat length bins
- how those composition-length trajectories differ by lineage
- where codon preference stays stable versus shifts across length
- which taxa show distinct codon-composition structure across length
- whether observed patterns remain well-supported across sparse long-length bins

## Why it matters

This viewer combines the two biological signals that motivate the first-wave
family:

- repeat length
- codon composition

It should become the main comparison viewer once the shared codon-usage
contract and codon-composition browse layer exist.

Biologically, the value is not only in seeing the codon mixture at one bin.
The important signal is often:

- whether one codon becomes dominant as length increases
- whether codon composition stays stable or transitions across bins
- whether related taxa share similar composition-length trajectories
- whether long-bin composition differences are supported or are based on sparse counts

This viewer should therefore emphasize **trajectory, dominance, transition, and
support**, not just static composition snapshots.

## Dependencies

This viewer should not invent new infrastructure. It depends on:

- the implemented length-view stats foundation
- the normalized codon-usage contract from the codon-composition plan
- shared lineage-order helpers
- shared length-bin helpers
- the same normalized stats filter state used by the other viewers

## Design principles

- composition must remain the default biological unit
- lineage-aware taxon ordering is required
- low-support long bins must not read as equally trustworthy as dense central bins
- codon order must stay fixed across all views
- overview should show both composition and where composition changes
- scalar summaries may exist as companions, but should not replace the
  composition-first landing state

## Target 3-tier structure

### `Tier 1 - Overview`

Tier 1 should be an overview shell with multiple tightly related modes rather
than a single overloaded chart.

Shared structure:

- taxonomy-first matrix
- y-axis: lineage-aware taxon ordering
- x-axis: shared repeat length bins
- each cell represents one taxon and one length bin
- each mode preserves the idea that codon mixtures, not scalar summaries, are
  the primary biological object

#### Primary mode: `Composition matrix`

Primary chart:

- `Taxon x Length-bin` matrix with per-cell codon-composition glyphs

Meaning:

- each cell preserves codon mixtures rather than collapsing them to one number
- this is the main landing view for the page
- users should be able to scan across rows to see composition trajectories with
  increasing length
- users should be able to scan down columns to compare taxa at the same length bin

Recommended encoding:

- for 2-codon residues:
  - use a simple split tile or compact internal proportion bar
  - do not overcomplicate with miniature stacked bars when one fraction implies the other
- for 3+ codon residues:
  - use a tiny stacked composition bar with fixed codon order across all cells

Support awareness:

- every cell should carry support metadata
- low-count bins should be visually downweighted or flagged
- acceptable support encodings include:
  - reduced opacity
  - subtle corner marker or warning dot
  - optional low-support toggle or legend state

This matters biologically because sparse long bins may look dramatic while being
based on very few observations.

#### Companion mode: `Dominant codon`

Primary chart:

- same `Taxon x Length-bin` matrix layout
- each cell emphasizes which codon is dominant in that bin

Meaning:

- lets users quickly see which codon “wins” across length
- makes codon-dominance flips easy to spot
- provides a more interpretable lineage-level scan than raw mixtures alone

Recommended encoding:

- cell color or symbol indicates dominant codon
- saturation, border strength, or secondary mark indicates dominance margin

This mode is especially useful for questions like:

- where does codon dominance switch with length?
- do related taxa share the same dominant-codon regime?
- are long bins compositionally mixed or clearly dominated?

#### Companion mode: `Composition shift`

Primary chart:

- `Taxon x Adjacent-length-transition` matrix

Meaning:

- each cell measures how much codon composition changes from one length bin to the next
- this highlights transition points rather than raw composition
- it is often more biologically informative than raw composition when the goal
  is to find where codon usage starts to diverge with increasing repeat length

Axes:

- y-axis: taxa
- x-axis: adjacent-bin transitions such as `1-2`, `2-3`, `3-4`, etc.

Recommended statistics:

- for 2-codon residues:
  - use absolute difference in one codon fraction between adjacent bins
- for 3+ codon residues:
  - use L1 distance or JSD between adjacent-bin composition vectors

Default preference:

- prefer L1 distance when simplicity and interpretability matter most
- JSD is acceptable for 3+ codon full-mixture comparison, but should not be
  introduced where a simpler measure is sufficient

This mode should answer:

- where along the length axis composition shifts sharply
- which taxa are stable versus transition-heavy
- whether shifts cluster by lineage

### `Tier 2 - Browse`

Tier 2 should move from matrix scanning to per-taxon trajectory reading.

Primary chart family:

- per-taxon composition-across-length panels
- one panel per selected or visible taxon
- fixed axes and fixed codon order across panels

Meaning:

- users should be able to compare how codon mixtures evolve across length for
  several taxa without forcing all taxa into one unreadable overlaid plot

Recommended view rules:

- for 2-codon residues:
  - line or area views are acceptable and often clearer
- for 3+ codon residues:
  - stacked bars or stacked areas are preferred
  - avoid cluttered multi-line overlays when too many codons are present

Support display:

- add a small support strip under each panel
- this can be a tiny count bar series or dot strip by length bin
- sparse long bins should remain visible as sparse, not visually equivalent to dense bins

Tier 2 should answer:

- how does this taxon’s codon mixture evolve across length?
- how does that compare with neighboring taxa or selected peers?
- are apparent long-bin differences well supported?

### `Tier 3 - Inspect`

Tier 3 is for one selected taxon, branch, or filtered subset.

Primary views:

- detailed composition-across-length chart
- exact supporting table
- optional comparison against branch or parent aggregate

Meaning:

- this is the analytical close-up layer
- users should be able to inspect exact fractions, support, dominance, and
  transitions for one focused lineage

Recommended inspect components:

- one detailed composition-across-length chart
- one table with:
  - length bin
  - codon fractions
  - count / support
  - dominant codon
  - entropy or evenness
  - optional delta from previous bin
- optional comparison line or summary against:
  - parent branch aggregate
  - sibling mean
  - selected reference lineage

## Deferred companion views

Secondary scalar summaries can still be useful, but only as companion analytical
views.

Examples:

- dominance margin
- entropy / evenness
- support-aware uncertainty summary

These may support interpretation, but should not replace the
composition-first landing state.

## Statistical guidance

### Composition representation

- codon composition vectors should remain normalized within each taxon-length bin
- no mixed-residue codon aggregation by default
- codon order must remain fixed across all tiers and all residues

### Shift statistics

For adjacent-bin composition change:

- 2-codon residues:
  - use absolute change in one codon fraction
  - the second codon is implied, so no heavier divergence is needed
- 3+ codon residues:
  - use L1 distance or JSD between normalized codon-composition vectors

Default bias:

- prefer simple, transparent measures unless a more complex one is clearly justified

### Support handling

Every taxon-length bin should retain support metadata such as:

- observation count
- optional count tier classification

Support should inform rendering and interpretation throughout the page.

## Constraints

- no mixed-residue codon aggregation by default
- no unbounded all-taxa trend plots
- no second filter architecture
- no overview page without lineage-aware ordering
- no scalar color encoding as the primary representation of codon mixtures
- no support-blind rendering of sparse long bins
- no changing codon order between cells or views

## Recommended first-wave outcome

The first-wave version of this viewer should aim for:

### Tier 1
- composition matrix
- dominant codon mode
- composition shift mode
- lineage-aware taxon ordering
- support-aware cells

### Tier 2
- per-taxon small multiples across length
- residue-aware chart choice:
  - line/area for 2-codon residues
  - stacked bars/areas for 3+ codon residues
- support strip under each panel

### Tier 3
- focused detailed chart
- exact table
- optional lineage comparison

## Summary

This viewer should not try to force codon composition x length into one scalar
overview.

Its job is to preserve codon mixtures while still making biological structure
readable at scale. The most important signals are:

- what the codon mixture is
- which codon dominates
- where composition shifts across length
- whether long-bin patterns are well supported
- how these behaviors align with lineage structure

That makes this viewer a composition-first comparison system, not just a more
complex codon-ratio heatmap.
